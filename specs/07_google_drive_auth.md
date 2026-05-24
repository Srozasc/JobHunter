# Spec: Google Drive — Autenticación (drive/auth.py)

## Historia de usuario

Como usuario, quiero que JobHunter se autentique con Google Drive una sola vez usando OAuth2 Desktop Flow, para que las ejecuciones futuras suban CSVs sin pedir credenciales de nuevo.

## Asunciones acordadas

1. Se usa `InstalledAppFlow` con `flow.run_console()` por defecto (para entornos sin navegador gráfico como Termux/SSH). Si hay navegador disponible, cae back a `run_local_server()`.
2. Scopes: `['https://www.googleapis.com/auth/drive.file']` (acceso solo a archivos creados por la app).
3. Si `token.json` existe y no está expirado → se carga directamente. Si está expirado pero tiene `refresh_token` → se refresca automáticamente.
4. Si `credentials_file` no existe → error claro: `"No se encontró credentials.json. Descarga las credenciales desde Google Cloud Console."` + enlace a la guía de setup.
5. Directorio de guardado es relativo al cwd.
6. Token guardado con permisos `0600`.

## Criterios de aceptación

### AC-1: Flujo de autorización inicial
- Cuando el usuario ejecuta por primera vez, entonces se abre el flujo de consola (ingresa URL de autorización en navegador, pega código de verificación).
- Cuando el flujo completa, entonces se guarda `token.json` y se retorna el servicio de Drive.

### AC-2: Reutilización de token
- Cuando `token.json` existe y no está expirado, entonces no se pide autorización de nuevo, se retorna el servicio directamente.

### AC-3: Refresco automático
- Cuando `token.json` está expirado pero tiene `refresh_token`, entonces se refresca el access token automáticamente, se actualiza `token.json` y se retorna el servicio.

### AC-4: Credenciales faltantes
- Cuando `credentials_file` no existe, entonces se lanza `FileNotFoundError` con mensaje acciónable que incluye enlace a la guía de setup.

### AC-5: Permisos de token
- Cuando se guarda `token.json`, entonces tiene permisos `0600` (solo lectura propietario).

## Escenarios BDD

### Escenario 1: Autorización inicial (flujo consola)
```gherkin
Given no existe token.json
And credentials.json existe y es válido
When llamo get_drive_service(credentials_file, token_file)
Then se imprime "Por favor, visita esta URL para autorizar:"
And el usuario ingresa el código de verificación
And se crea token.json
And se retorna servicio de Drive como googleapiclient.discovery.Resource
```

### Escenario 2: Token válido existente
```gherkin
Given existe token.json con token no expirado
When llamo get_drive_service(credentials_file, token_file)
Then NO se imprime ninguna URL de autorización
And se carga el token desde token.json y se retorna el servicio
```

### Escenario 3: Refresco de token expirado
```gherkin
Given existe token.json con access token expirado pero refresh_token válido
When llamo get_drive_service(credentials_file, token_file)
Then se refresca el access token automáticamente
And se actualiza token.json con el nuevo access token y nueva fecha de expiración
And se retorna el servicio
```

### Escenario 4: Credenciales faltantes
```gherkin
Given no existe credentials.json
When llamo get_drive_service("credentials.json", "token.json")
Then se lanza FileNotFoundError
And el mensaje incluye "No se encontró credentials.json"
And el mensaje incluye enlace a Documentacion/setup_google_drive.md
```

### Escenario 5: Permisos de token
```gherkin
Given flujo de autorización completado exitosamente
When verifico permisos de token.json
Then os.stat("token.json").st_mode & 0o777 == 0o600
```

## Detalles de implementación

### Dependencias

```python
# pyproject.toml
google-api-python-client>=2.100
google-auth-oauthlib>=1.0
google-auth>=2.0
```

### Implementación

```python
import os
import stat
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from loguru import logger

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service(
    credentials_file: str = "credentials.json",
    token_file: str = "token.json",
) -> Resource:
    """Obtiene servicio autenticado de Google Drive API v3."""
    creds = _load_or_refresh_credentials(credentials_file, token_file)
    return build('drive', 'v3', credentials=creds)

def _load_or_refresh_credentials(credentials_file: str, token_file: str) -> Credentials:
    """Carga credenciales, refresca si necesario, o inicia flujo de autorización."""
    creds = _load_token(token_file)

    if creds and creds.valid:
        logger.info("Token válido cargado, reutilizando.")
        return creds
    elif creds and creds.expired and creds.refresh_token:
        logger.info("Token expirado, refrescando...")
        creds.refresh(Request())
        _save_token(creds, token_file)
        return creds
    else:
        logger.info("Iniciando flujo de autorización OAuth2...")
        creds = _perform_oauth_flow(credentials_file, token_file)
        return creds

def _load_token(token_file: str) -> Credentials | None:
    """Carga token desde archivo, retorna None si no existe o es inválido."""
    token_path = Path(token_file)
    if not token_path.exists():
        logger.debug(f"No existe {token_file}, se necesitará autorización inicial.")
        return None
    try:
        return Credentials.from_authorized_user_file(token_file, SCOPES)
    except Exception as e:
        logger.warning(f"Error cargando token: {e}. Se solicitará re-autorización.")
        return None

def _perform_oauth_flow(credentials_file: str, token_file: str) -> Credentials:
    """Ejecta flujo OAuth2 de consola."""
    creds_path = Path(credentials_file)
    if not creds_path.exists():
        msg = (
            f"No se encontró '{credentials_file}'.\n"
            "Descarga las credenciales OAuth2 desde Google Cloud Console:\n"
            "https://console.cloud.google.com/apis/credentials → 'Create Credentials' → 'OAuth 2.0 Client ID' → Type: 'Desktop app'. "
            "Luego guarda el archivo JSON descargado como 'credentials.json' en el directorio del proyecto."
        )
        raise FileNotFoundError(msg)

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    try:
        # Intentar flujo de consola si no hay navegador disponible
        creds = flow.run_console()
    except OSError:
        # Fallback a flujo con servidor local si está disponible
        creds = flow.run_local_server(port=0)
    _save_token(creds, token_file)
    logger.info(f"Token guardado en {token_file}")
    return creds

def _save_token(creds: Credentials, token_file: str) -> None:
    """Guarda token en archivo con permisos restrictivos."""
    token_path = Path(token_file)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
```

### Manejo de escenarios de flujo

```
get_drive_service()
  └─ _load_or_refresh_credentials()
       ├─ _load_token() → existe?
       │    ├─ No → _perform_oauth_flow()
       │    │       ├─ run_console() → ingresa URL + código
       │    │       ├─ _save_token()
       │    │       └─ return creds
       │    ├─ Sí, válido → return creds
       │    ├─ Sí, expirado + refresh_token → refrescar → guardar → return
       │    └─ Sí, expirado sin refresh → _perform_oauth_flow()
       └─ return build('drive', 'v3', credentials=creds)
```

## Tareas derivadas (del plan de acción)

- Paso 7.1: Implementar flujo OAuth2
- Paso 7.2: Documentar configuración de Google Cloud Console
