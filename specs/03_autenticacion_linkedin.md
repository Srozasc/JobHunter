# Spec: Autenticación LinkedIn (linkedin/auth.py)

## Historia de usuario

Como usuario, quiero loguearme a LinkedIn una sola vez en un navegador visible, para que JobHunter reutilice mi sesión en todas las ejecuciones futuras sin pedirme credenciales de nuevo.

## Asunciones acordadas

1. Login inicial en modo `headless=False` (navegador visible) para ingreso manual de credenciales.
2. Re-ejecuciones usan `headless=True` por defecto (configurable vía `linkedin.headless`).
3. Sesión válida si al navegar a `linkedin.com/feed` la URL final NO contiene `/login` ni `/checkpoint`.
4. Sesión expirada → borra archivo y re-abre headed para re-login.
5. Archivo de sesión con permisos `0600`.
6. Implementación async con `async_playwright()`.

## Criterios de aceptación

### AC-1: ensure_session retorna contexto auténticado
- Cuando se llama `ensure_session(session_file, headless)`, entonces retorna un `BrowserContext` con cookies de LinkedIn válidas.

### AC-2: Persistencia entre ejecuciones
- Cuando la sesión ya fue guardada y es válida, entonces NO se abre navegador visible en re-ejecuciones.

### AC-3: Detección de sesión expirada
- Cuando las cookies expiraron, entonces se detecta redirección a login, se borra el archivo de sesión y se solicita re-login.

### AC-4: Login visible
- Cuando es la primera vez (o sesión expurada), entonces se abre un navegador visible para que el usuario ingrese credenciales.

### AC-5: Permisos seguros
- Cuando se guarda el archivo de sesión, entonces tiene permisos `0600` (solo lectura propietario).

## Escenarios BDD

### Escenario 1: Primera ejecución (sin sesión)
```gherkin
Given no existe data/session/linkedin_session.json
When llamo ensure_session("data/session/linkedin_session.json", headless=False)
Then se abre un navegador Chromium visible
And se navega a https://www.linkedin.com/login
And se espera a que el usuario complete el login manualmente
And se detecta navegación exitosa a linkedin.com/feed
And se guarda storage_state en data/session/linkedin_session.json
And el archivo tiene permisos 0600
And retorna BrowserContext autenticado
```

### Escenario 2: Re-ejecución con sesión válida
```gherkin
Given existe data/session/linkedin_session.json con cookies válidas
When llamo ensure_session("data/session/linkedin_session.json", headless=True)
Then NO se abre navegador visible
And se carga storage_state desde el archivo
And se verifica que la sesión es válida (feed carga sin redirect a login)
And retorna BrowserContext autenticado
```

### Escenario 3: Sesión expirada
```gherkin
Given existe data/session/linkedin_session.json con cookies expiradas
When llamo ensure_session("data/session/linkedin_session.json", headless=True)
Then se carga storage_state
And se navega a linkedin.com/feed
And se detecta redirección a /login
And se borra data/session/linkedin_session.json
Then se re-intenta con headless=False
And se abre navegador visible para re-login
```

### Escenario 4: Sesión válida + headless forzado
```gherkin
Given existe sesión válida
And config.linkedin.headless == True
When llamo ensure_session con headless=True
Then se reutiliza sesión sin abrir ventana
And retorna BrowserContext
```

### Escenario 5: Verificación de permisos
```gherkin
Given sesión guardada exitosamente
When verifico permisos del archivo
Then os.stat(session_file).st_mode & 0o777 == 0o600
```

## Detalles de implementación

### Flujo principal

```
ensure_session(session_file, headless)
  ├─ session_file existe?
  │   ├─ No → _login_flow(headless=False) → guardar → return ctx
  │   └─ Sí → cargar sesión → _is_session_valid(ctx)
  │       ├─ Válido → return ctx
  │       └─ Expirado → borrar session_file → _login_flow(headless=False)
  └─ return ctx
```

### Implementación

```python
import asyncio
import os
import stat
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext
from loguru import logger

LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"
LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"

async def ensure_session(
    session_file: str = "data/session/linkedin_session.json",
    headless: bool = True,
) -> BrowserContext:
    """Asegura una sesión válida de LinkedIn, reutilizando o creando una nueva."""
    session_path = Path(session_file)

    if session_path.exists():
        logger.info("Sesión existente encontrada, validando...")
        ctx = await _load_session(session_file, headless=headless)
        if await _is_session_valid(ctx):
            logger.info("Sesión válida, reutilizando.")
            return ctx
        else:
            logger.warning("Sesión expirada. Solicitando re-login...")
            session_path.unlink(missing_ok=True)
    else:
        logger.info("No se encontró sesión existente.")

    return await _login_flow(session_file, headless=False)


async def _load_session(session_file: str, headless: bool) -> BrowserContext:
    """Carga sesión desde archivo storage_state."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    ctx = await browser.new_context(storage_state=session_file)
    return ctx


async def _is_session_valid(ctx: BrowserContext) -> bool:
    """Verifica si la sesión actual es válida navegando al feed."""
    page = await ctx.new_page()
    try:
        await page.goto(LINKEDIN_FEED_URL, wait_until="networkidle", timeout=30000)
        final_url = page.url
        is_valid = "/login" not in final_url and "/checkpoint" not in final_url
        if not is_valid:
            logger.debug(f"Sesión inválida: redirigido a {final_url}")
        return is_valid
    except Exception as e:
        logger.error(f"Error validando sesión: {e}")
        return False
    finally:
        await page.close()


async def _login_flow(session_file: str, headless: bool) -> BrowserContext:
    """Abre navegador para login manual del usuario."""
    logger.info("Abriendo navegador para login de LinkedIn...")
    logger.info("Por favor, inicia sesión en la ventana del navegador.")

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    ctx = await browser.new_context()

    page = await ctx.new_page()
    await page.goto(LINKEDIN_LOGIN_URL)

    # Esperar a que el usuario complete el login
    logger.info("Esperando login manual... (máximo 5 minutos)")
    try:
        await page.wait_for_url("**/feed/**", timeout=300_000)  # 5 min
        logger.info("Login exitoso detectado.")
    except Exception:
        logger.error("Timeout esperando login. Cerrando.")
        await browser.close()
        raise RuntimeError("Login timeout: no se detectó inicio de sesión en 5 minutos.")

    # Guardar sesión
    session_path = Path(session_file)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    await ctx.storage_state(path=session_file)
    os.chmod(session_file, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    logger.info(f"Sesión guardada en {session_file} (permisos 0600)")

    await page.close()
    return ctx
```

## Tareas derivadas (del plan de acción)

- Paso 3.1: Implementar flujo de login con Playwright
- Paso 3.2: Tests de autenticación (mock)
