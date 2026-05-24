"""Scheduler y orquestador del flujo completo de JobHunter."""

import asyncio
import re
import time
from datetime import datetime, timezone

import schedule
from loguru import logger

from jobhunter.config import AppConfig
from jobhunter.dedup import filter_new_offers, load_history, save_history
from jobhunter.drive.auth import get_drive_service
from jobhunter.drive.uploader import upload_csv
from jobhunter.linkedin.auth import ensure_session
from jobhunter.linkedin.scraper import scrape_offers


def parse_every_hours(frequency: str) -> int | None:
    """Extrae horas de strings tipo 'every_3h', 'every_6h'. Retorna None si no coincide."""
    match = re.fullmatch(r"every_(\d+)h", frequency)
    if match:
        return int(match.group(1))
    return None


def run_job(config: AppConfig) -> None:
    """Ejecuta el flujo completo: auth → scrape → dedup → upload."""
    logger.info("=" * 50)
    logger.info(f"JobHunter iniciado — {datetime.now(timezone.utc).isoformat()}")
    start = time.time()

    try:
        # 1. Autenticación LinkedIn
        logger.info("Paso 1/4: Autenticación LinkedIn...")
        ctx = asyncio.run(
            ensure_session(
                session_file=config.linkedin.session_file,
                headless=config.linkedin.headless,
            )
        )

        # 2. Scraping
        logger.info("Paso 2/4: Scraping de ofertas...")
        offers = asyncio.run(scrape_offers(ctx, config.search))

        # Cerrar contexto del browser
        try:
            asyncio.run(ctx.close())
        except Exception:
            pass

        if not offers:
            logger.warning("No se encontraron ofertas en esta ejecución.")
            return

        logger.info(f"  {len(ofertas)} ofertas encontradas en LinkedIn.")

        # 3. Deduplicación
        logger.info("Paso 3/4: Deduplicación...")
        history = load_history(config.dedup.history_file)
        new_offers, history = filter_new_offers(offers, history)

        if not new_offers:
            logger.info("Todas las ofertas ya estaban en el historial (0 nuevas).")
            save_history(history, config.dedup.history_file)
            return

        logger.info(
            f"  {len(new_offers)} ofertas nuevas de {len(offers)} totales."
        )

        # 4. Upload a Google Drive
        logger.info("Paso 4/4: Subida a Google Drive...")
        drive_service = get_drive_service(
            credentials_file=config.google_drive.credentials_file,
            token_file=config.google_drive.token_file,
        )
        file_id, web_view_link = upload_csv(
            new_offers, drive_service, config.google_drive
        )

        # Guardar historial actualizado
        save_history(history, config.dedup.history_file)

        elapsed = time.time() - start
        logger.info("=" * 50)
        logger.info(f"JobHunter finalizado en {elapsed:.1f}s")
        logger.info(f"✅ {len(new_offers)} ofertas nuevas subidas a Google Drive")
        logger.info(f"   Archivo: {web_view_link}")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(
            f"❌ Error en ejecución de JobHunter (después de {elapsed:.1f}s): {e}"
        )
        logger.exception(e)


def start_scheduler(config: AppConfig) -> None:
    """Configura y ejecuta el loop del scheduler según ScheduleConfig."""
    if not config.schedule.enabled:
        logger.info("Scheduler deshabilitado en config.yaml")
        return

    freq = config.schedule.frequency
    hour = config.schedule.hour

    logger.info("Configurando scheduler...")

    if freq == "daily":
        schedule.every().day.at(hour).do(_run_job_safe, config)
        logger.info(f"🕙 Scheduler activado: ejecución diaria a las {hour}")

    elif freq == "weekly":
        schedule.every().monday.at(hour).do(_run_job_safe, config)
        logger.info(
            f"🕙 Scheduler activado: ejecución semanal los lunes a las {hour}"
        )

    elif freq.startswith("every_") and freq.endswith("h"):
        hours = parse_every_hours(freq)
        if hours is None:
            logger.error(f"Frecuencia no soportada: {freq}")
            return
        schedule.every(hours).hours.do(_run_job_safe, config)
        logger.info(
            f"🕙 Scheduler activado: ejecución cada {hours}h (primera inmediata)"
        )
        # Primera ejecución inmediata
        logger.info("Ejecutando primera corrida inmediata...")
        _run_job_safe(config)

    else:
        logger.error(f"Frecuencia no soportada: {freq}")
        return

    logger.info("Scheduler corriendo... (Ctrl+C para detener)")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler detenido por el usuario.")


def _run_job_safe(config: AppConfig) -> None:
    """Wrapper seguro de run_job para que el loop no se rompa."""
    try:
        run_job(config)
    except Exception as e:
        logger.error(f"Error en ejecución programada: {e}")
        logger.info("Esperando próxima ejecución... ⌛")


def generate_crontab(config: AppConfig) -> str:
    """Genera entrada de crontab como alternativa al scheduler Python."""
    if not config.schedule.enabled:
        return "# Scheduler deshabilitado"

    hour, minute = config.schedule.hour.split(":")
    cmd = "cd $(dirname $0) && jobhunter run >> /tmp/jobhunter.log 2>&1"

    if config.schedule.frequency == "daily":
        return f"{minute} {hour} * * * {cmd}"
    elif config.schedule.frequency == "weekly":
        return f"{minute} {hour} * * 1 {cmd}"
    elif config.schedule.frequency.startswith("every_"):
        hours = parse_every_hours(config.schedule.frequency)
        if hours:
            return f"{minute} {hour} * * * {cmd}  # cada {hours}h"

    return f"# Frecuencia no soportada: {config.schedule.frequency}"
