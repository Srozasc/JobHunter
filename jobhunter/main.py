"""CLI principal de JobHunter con Typer."""

import shutil
import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

console = Console()

app = typer.Typer(
    name="jobhunter",
    add_completion=True,
    no_args_is_help=True,
    help="🎯 JobHunter — Recopilador automatizado de ofertas de empleo desde LinkedIn",
)


def _get_config():
    """Carga y retorna la configuración."""
    from jobhunter.config import load_config

    return load_config()


# ── Comandos ───────────────────────────────────────────────────


@app.command()
def init(
    force: bool = typer.Option(
        False, "--force", "-f", help="Sobrescribir config.yaml sin preguntar"
    ),
):
    """Crea config.yaml desde el template de ejemplo."""
    example = Path("config.example.yaml")
    target = Path("config.yaml")

    if target.exists() and not force:
        overwrite = typer.confirm(
            "ya existe config.yaml, sobrescribir?", default=False
        )
        if not overwrite:
            console.print("[yellow]Cancelado. config.yaml no modificado.[/yellow]")
            raise typer.Exit(0)

    if not example.exists():
        console.print("[red]config.example.yaml no encontrado.[/red]")
        raise typer.Exit(1)

    shutil.copy2(example, target)
    console.print("[green]✅ config.yaml creado exitosamente.[/green]")


@app.command()
def login(
    force: bool = typer.Option(
        False, "--force", "-f", help="Forzar re-login ignorando sesión existente"
    ),
):
    """Inicia sesión en LinkedIn y guarda la sesión en disco."""
    import asyncio

    from jobhunter.linkedin.auth import ensure_session

    config = _get_config()
    session_file = config.linkedin.session_file
    headless = config.linkedin.headless

    # Si existe y es válida y no es --force, no hacer nada
    if not force and Path(session_file).exists():
        try:
            asyncio.run(ensure_session(session_file, headless=True))
            console.print(
                "[green]✅ Sesión de LinkedIn ya válida. "
                "No es necesario volver a loguearse.[/green]"
            )
            raise typer.Exit(0)
        except Exception:
            pass  # Sesión inválida, proceder

    console.print("[blue]Abriendo navegador para login de LinkedIn...[/blue]")
    try:
        asyncio.run(ensure_session(session_file, headless=False))
        console.print("[green]✅ Sesión de LinkedIn guardada exitosamente.[/green]")
    except Exception as e:
        console.print(f"[red]Error en login: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def run():
    """Ejecuta un ciclo completo de scraping + subida a Google Drive."""
    from jobhunter.scheduler import run_job

    config = _get_config()
    run_job(config)


@app.command()
def schedule():
    """Inicia el scheduler en modo continuo."""
    from jobhunter.scheduler import start_scheduler

    config = _get_config()
    start_scheduler(config)


@app.command()
def status():
    """Muestra el estado actual del proyecto."""
    from datetime import datetime, timezone

    from jobhunter.dedup import load_history

    config = _get_config()

    # Config
    console.print("[bold cyan]=== Config ===")
    console.print(f"  📄 config.yaml: [green]{Path('config.yaml').resolve()}[/green]")
    console.print(f"  🔍 keywords: '{config.search.keywords}'")
    console.print(f"  📍 location: '{config.search.location}'")
    console.print(
        f"  📅 schedule: {config.schedule.frequency} @ {config.schedule.hour}"
    )
    if config.google_drive.enabled:
        console.print(f"  🗂  destino: ☁️ Google Drive (folder: {config.google_drive.folder_id or 'raíz'})")
    else:
        console.print("  🗂  destino: 💾 local (data/output/)")

    # Historial
    console.print("\n[bold cyan]=== Historial ===")
    history = load_history(config.dedup.history_file)
    console.print(f"  📊 Ofertas en historial: [green]{len(history)}[/green]")

    if history:
        first_seens = [
            entry.get("first_seen", "")
            for entry in history.values()
            if entry.get("first_seen")
        ]
        if first_seens:
            latest = max(first_seens)
            try:
                dt = datetime.fromisoformat(str(latest))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                local = dt.astimezone()
                console.print(
                    f"  🕐 Última oferta: [green]{local.strftime('%Y-%m-%d %H:%M %Z')}[/green]"
                )
            except Exception:
                console.print(f"  🕐 Última oferta: {latest}")

    # Google Drive
    console.print("\n[bold cyan]=== Google Drive ===")
    token_path = Path(config.google_drive.token_file)
    creds_path = Path(config.google_drive.credentials_file)
    if not creds_path.exists():
        console.print(
            "  ⚪ credentials.json no encontrado — "
            "revisa Documentacion/setup_google_drive.md"
        )
    elif token_path.exists():
        try:
            from google.oauth2.credentials import Credentials

            creds = Credentials.from_authorized_user_file(
                str(token_path),
                ["https://www.googleapis.com/auth/drive.file"],
            )
            if creds.valid:
                exp = creds.expiry
                if exp:
                    remaining = (exp - datetime.now(timezone.utc)).total_seconds() / 3600
                    console.print(
                        f"  ✅ Token válido (expira en {int(remaining)}h)."
                    )
                else:
                    console.print("  ✅ Token válido.")
            elif creds.expired and creds.refresh_token:
                console.print(
                    "  🟡 Token expirado pero con refresh_token — se refrescará automáticamente."
                )
            else:
                console.print("  🔴 Token inválido o expirado sin refresh.")
        except Exception:
            console.print("  🔴 Token ilegible o corrupto.")
    else:
        console.print(
            "  ⚪ Token no encontrado — se creará al ejecutar 'jobhunter run'."
        )

    # LinkedIn
    console.print("\n[bold cyan]=== LinkedIn ===")
    session_path = Path(config.linkedin.session_file)
    if not session_path.exists():
        console.print("  ⚪ Sesión no encontrada — ejecuta 'jobhunter login'.")
    else:
        stat = session_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        console.print(
            f"  📁 Archivo de sesión: {session_path} (modificado: {mtime.strftime('%Y-%m-%d %H:%M')})"
        )
        console.print(
            "  ℹ️  Valida la sesión con 'jobhunter login' si tienes errores."
        )


def main():
    """Entry point de la CLI."""
    app()


if __name__ == "__main__":
    main()
