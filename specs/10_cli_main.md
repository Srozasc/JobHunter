# Spec: CLI Principal (main.py)

## Historia de usuario

Como usuario, quiero tener una interfaz de línea de comando simple y clara para ejecutar todas las acciones de JobHunter: inicializar config, hacer login, correr scraping, iniciar scheduler y ver estado.

## Asunciones acordadas

1. `main.py` define: `app = typer.Typer(name="jobhunter", add_completion=True)`.
2. `jobhunter --help` incluye: `init`, `login`, `run`, `schedule`, `status` (cada uno con `--help` propio).
3. `jobhunter init` — si `config.yaml` ya existe, pregunta confirmación (input) o usa flag `--force`.
4. `jobhunter login` — llama a `ensure_session()` y al finalizar muestra `"Sesión de LinkedIn guardada exitosamente."`.
5. `jobhunter status` — muestra: número de ofertas en historial, última ejecución registrada, ruta de `config.yaml` usada, estado de Google Drive (token válido/inválido).
6. Errores no capturados se capturan nivel superior y se imprimen con `rich.traceback` (si `rich` está instalado) o traceback estándar.

## Criterios de aceptación

### AC-1: App Typer inicializada
- Cuando el usuario ejecuta `jobhunter --help`, entonces ve el nombre de la app, versión (si se define) y la lista de comandos disponibles.

### AC-2: jobhunter init
- Cuando no existe `config.yaml` y se ejecuta `jobhunter init`, entonces se copia `config.example.yaml` → `config.yaml`.
- Cuando `config.yaml` ya existe, entonces pide confirmación: `"ya existe config.yaml, sobrescribir? (s/N)"`.
- Cuando el usuario responde `s` o usa `--force`, entonces se sobrescribe.

### AC-3: jobhunter login
- Cuando se ejecuta `jobhunter login`, entonces se abre navegador visible para login de LinkedIn.
- Cuando el login es exitoso, entonces muestra `"Sesión de LinkedIn guardada exitosamente."`.
- Cuando el archivo de sesión ya existe y es válido, entonces muestra `"Sesión de LinkedIn ya válida. No es necesario volver a loguearse."`.

### AC-4: jobhunter run
- Cuando se ejecuta `jobhunter run`, entonces se ejecuta el flujo completo una vez (`run_job(config)`).
- Cuando termina, entonces muestra la cantidad de ofertas nuevas subidas y el link a Drive.

### AC-5: jobhunter schedule
- Cuando se ejecuta `jobhunter schedule`, entonces inicia el loop del scheduler.
- Cuando `schedule.enabled == false`, entonces imprime `"Scheduler deshabilitado en config.yaml"` y sale.

### AC-6: jobhunter status
- Cuando se ejecuta `jobhunter status`, entonces muestra en formato tabla o líneas:
  - Config en uso (ruta del archivo)
  - Ofertas en historial (cantidad)
  - Última ejecución registrada (timestamp de última oferta `last_seen` o del archivo de historial)
  - Estado de Google Drive (token válido/no existe/expirado)
  - Estado de sesión de LinkedIn (válida/expirada/no existe)

## Escenarios BDD

### Escenario 1: jobhunter init (archivo inexistente)
```gherkin
Given no existe config.yaml
When ejecuto jobhunter init
Then se copia config.example.yaml → config.yaml
And se imprime "config.yaml creado exitosamente."
```

### Escenario 2: jobhunter init (archivo existente, sin force)
```gherkin
Given existe config.yaml
When ejecuto jobhunter init
Then pregunta "ya existe config.yaml, sobrescribir? (s/N)"
And si el usuario responde N, entonces NO se modifica config.yaml
```

### Escenario 3: jobhunter login (primera vez)
```gherkin
Given no existe sesión de LinkedIn
When ejecuto jobhunter login
Then se abre navegador visible
And se espera a que el usuario se loguee
And al finalizar se imprime "Sesión de LinkedIn guardada exitosamente."
```

### Escenario 4: jobhunter run completo
```gherkin
Given config.yaml válido
And sesión de LinkedIn válida
And credenciales de Google Drive configuradas
When ejecuto jobhunter run
Then se ejecuta: auth → scrape → dedup → upload
And se imprime "JobHunter finalizado — 15 ofertas nuevas subidas a Google Drive"
And se muestra la URL del archivo de CSV en Drive
```

### Escenario 5: jobhunter status
```gherkin
Given historial con 42 ofertas
And última oferta registrada el 2026-05-20T08:30:00Z
When ejecuto jobhunter status
Then muestra sección "Config" con la ruta de config.yaml
And muestra sección "Historial" con "42 ofertas"
And muestra sección "Última ejecución" con "2026-05-20 05:30 CLT"
And muestra sección "Google Drive" con "✅ Token válido"
```

### Escenario 6: jobhunter schedule deshabilitado
```gherkin
Given config con schedule.enabled=false
When ejecuto jobhunter schedule
Then se imprime "Scheduler deshabilitado en config.yaml"
And NO se inicia el loop
```

## Detalles de implementación

### Estructura de main.py

```python
import sys
from pathlib import Path
from typing import Optional
import typer
from loguru import logger
from rich.console import Console
from rich.traceback import install as rich_install

# Instalar traceback bonito con Rich si está disponible
try:
    rich_install(show_locals=False, word_wrap=True, extra_lines=3)
except ImportError:
    pass

console = Console()
app = typer.Typer(
    name="jobhunter",
    add_completion=True,
    no_args_is_help=True,
)

# Estado global (cargado en cada comando)
def get_config() -> AppConfig:
    """Carga y retorna la configuración. Se llama al inicio de cada comando."""
    from jobhunter.config import load_config
    return load_config()


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Sobrescribir config.yaml sin preguntar"),
):
    """Crea config.yaml desde el template de ejemplo."""
    example = Path("config.example.yaml")
    target = Path("config.yaml")

    if target.exists() and not force:
        confirm = typer.confirm("ya existe config.yaml, sobrescribir?", default=False)
        if not confirm:
            console.print("[yellow]Cancelado. config.yaml no modificado.[/yellow]")
            raise typer.Exit(0)

    if not example.exists():
        console.print("[red]config.example.yaml no encontrado.[/red]")
        raise typer.Exit(1)

    shutil.copy2(example, target)
    target.chmod(0o600)
    console.print("[green]config.yaml creado exitosamente.[/green]")


@app.command()
def login(
    force: bool = typer.Option(False, "--force", "-f", help="Forzar re-login ignorando sesión existente"),
):
    """Inicia sesión en LinkedIn y guarda la sesión en disco."""
    import asyncio
    from jobhunter.linkedin.auth import ensure_session
    from jobhunter.config import load_config

    config = load_config()
    session_file = config.linkedin.session_file
    headless = config.linkedin.headless

    # Si existe y es válida y no es --force, no hacer nada
    if not force and Path(session_file).exists():
        # Verificar validez sin pedir login
        try:
            asyncio.run(ensure_session(session_file, headless=True))
            console.print("[green]Sesión de LinkedIn ya válida. No es necesario volver a loguearse.[/green]")
            raise typer.Exit(0)
        except Exception:
            pass  # Sesión inválida, proceder

    console.print("[blue]Abriendo navegador para login de LinkedIn...[/blue]")
    try:
        asyncio.run(ensure_session(session_file, headless=False))
        console.print("[green]Sesión de LinkedIn guardada exitosamente.[/green]")
    except Exception as e:
        console.print(f"[red]Error en login: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo muestra lo que haría, sin subir a Drive"),
):
    """Ejecuta un ciclo completo de scraping + subida a Google Drive."""
    from jobhunter.scheduler import run_job
    from jobhunter.config import load_config

    config = load_config()

    if dry_run:
        console.print("[yellow]Modo dry-run — No se subirá a Drive.[/yellow]")
        # Implementar dry run en run_job (omite upload, solo scrape + dedup + guardar historial)
        # TODO: dry_run pasarse por args a run_job o separar lógica

    try:
        run_job(config)
    except Exception as e:
        console.print(f"[red]Error en ejecución: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def schedule():
    """Inicia el scheduler en modo continuo."""
    from jobhunter.scheduler import start_scheduler
    from jobhunter.config import load_config

    config = load_config()
    start_scheduler(config)


@app.command()
def status():
    """Muestra el estado actual del proyecto: historial, última ejecución, Drive."""
    from jobhunter.dedup import load_history
    from jobhunter.drive.auth import _load_token
    from jobhunter.config import load_config
    from datetime import datetime, timezone

    config = load_config()

    # Config
    console.print("[bold cyan]=== Config ===")
    console.print(f"  📄 config.yaml: [green]{Path('config.yaml').resolve()}[/green]")
    console.print(f"  🔍 keywords: '{config.search.keywords}'")
    console.print(f"  📍 location: '{config.search.location}'")
    console.print(f"  📅 frecuencia: {config.schedule.frequency} a las {config.schedule.hour}")

    # Historial
    console.print("\n[bold cyan]=== Historial ===")
    history = load_history(config.dedup.history_file)
    console.print(f"  📊 Ofertas en historial: [green]{len(history)}[/green]")

    if history:
        # Última oferta registrada por last_seen
        times = [
            entry.get("last_seen", "")
            for entry in history.values()
            if entry.get("last_seen")
        ]
        if times:
            # Asumiendo ISO format; parsear correctamente
            latest = max(times)
            try:
                dt = datetime.fromisoformat(str(latest))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                local = dt.astimezone()
                console.print(f"  🕐 Última actividad: [green]{local.strftime('%Y-%m-%d %H:%M %Z')}[/green]")
            except Exception:
                console.print(f"  🕐 Última actividad: {times}")

    # Google Drive Token
    console.print("\n[bold cyan]=== Google Drive ===")
    token_path = Path(config.google_drive.token_file)
    creds_path = Path(config.google_drive.credentials_file)
    if token_path.exists():
        creds = _load_token(config.google_drive.token_file)
        if creds:
            exp = creds.expiry
            if exp:
                in_hours = (exp - datetime.now(timezone.utc)).total_seconds() / 3600
                if in_hours < 0:
                    console.print(f"  🔴 Token expirado hace {abs(int(in_hours))}h – se refrescará automáticamente.")
                else:
                    console.print(f"  ✅ Token válido (expira en {int(in_hours)}h).")
            else:
                console.print("  ✅ Token válido.")
        else:
            console.print("  🔴 Token inválido o corrupto.")
    else:
        console.print("  ⚪ Token no encontrado – ejecuta 'jobhunter run' para autenticarte.")

    # LinkedIn Sesion
    console.print("\n[bold cyan]=== LinkedIn ===")
    session_path = Path(config.linkedin.session_file)
    if not session_path.exists():
        console.print("  ⚪ Sesión no encontrada – ejecuta 'jobhunter login'.")
    else:
        import asyncio
        from jobhunter.linkedin.auth import _is_session_valid, ensure_session
        try:
            ctx = asyncio.run(ensure_session(str(session_path), headless=True))
            console.print("  ✅ Sesión válida.")
            asyncio.run(ctx.close())
        except Exception:
            console.print("  🔴 Sesión inválida o expirada – ejecuta 'jobhunter login'.")


def main():
    """Entry point de la CLI."""
    app()


if __name__ == "__main__":
    main()
```

### Comandos

| Comando | Descripción |
|---|---|
| `jobhunter --help` | Muestra todos los comandos disponibles |
| `jobhunter init [--force]` | Crea `config.yaml` desde el template |
| `jobhunter login [--force]` | Inicia sesión en LinkedIn |
| `jobhunter run [--dry-run]` | Ejecuta scraping + upload una vez |
| `jobhunter schedule` | Inicia el scheduler en loop continuo |
| `jobhunter status` | Muestra estado completo del proyecto |

## Tareas derivadas (del plan de acción)

- Paso 10.1: Implementar comandos CLI con Typer
