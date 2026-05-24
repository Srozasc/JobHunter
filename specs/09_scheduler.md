# Spec: Scheduler (scheduler.py)

## Historia de usuario

Como usuario, quiero que JobHunter ejecute todo el flujo completo automáticamente con la periodicidad que yo defina (diaria, semanal o cada N horas), sin tener que recordar correr `jobhunter run` manualmente.

## Asunciones acordadas

1. Usa librería `schedule` con loop `while True: schedule.run_pending(); time.sleep(60)`.
2. Para `every_Xh`, el usuario escribe `every_3h`, `every_6h`, etc. Se extrae el número con regex.
3. En modo `weekly`, se ejecuta los lunes a la hora configurada.
4. `run_job()` envuelve todo el flujo en try/except — cualquier excepción se loguea como error pero NO rompe el loop.
5. `run_job()` registra tiempo de ejecución: log de inicio, fin (`"JobHunter finalizado — N ofertas nuevas subidas"`), y excepciones.
6. Si `schedule.enabled == false` → imprime `"Scheduler deshabilitado en config.yaml"` y no inicia el loop.

## Criterios de aceptación

### AC-1: Ejecución única (`jobhunter run`)
- Cuando el usuario ejecuta `jobhunter run`, entonces se ejecuta el flujo completo una vez: auth → scrape → dedup → upload.
- Cuando termina (éxito o error), entonces retorna al prompt de la terminal.

### AC-2: Scheduler diario
- Cuando `schedule.frequency == "daily"` y `hour == "09:00"`, entonces el scheduler ejecuta el flujo todos los días a las 09:00.
- Si el usuario ejecuta `jobhunter schedule` a las 08:59, entonces espera 1 minuto y ejecuta.

### AC-3: Scheduler semanal
- Cuando `schedule.frequency == "weekly"`, entonces el scheduler ejecuta solo los lunes a la hora configurada.

### AC-4: Scheduler cada N horas
- Cuando `schedule.frequency == "every_3h"` (o `every_6h`, etc.), entonces el scheduler ejecuta cada N horas sin importar la hora del día.
- La primera ejecución empieza inmediatamente.

### AC-5: Tolerancia a fallos
- Cuando el scraper falla en una ejecución (ej: LinkedIn caído), entonces el scheduler loguea el error y espera a la próxima ejecución sin detenerse.
- Cuando Google Drive falla (cuota agotada), entonces el scheduler loguea el error y espera la próxima ejecución.

### AC-6: Deshabilitado flag
- Cuando `schedule.enabled == false` y el usuario ejecuta `jobhunter schedule`, entonces imprime `"Scheduler deshabilitado en config.yaml"` y no inicia el loop.

## Escenarios BDD

### Escenario 1: jobhunter run (ejecución manual)
```gherkin
Given config.yaml con SearchConfig válido
And sesión de LinkedIn válida
When llamo run_job(config)
Then se ejecuta el flujo completo: auth → scrape → dedup → upload
And se loguea "JobHunter iniciado" al comienzo
And se loguea "JobHunter finalizado — N ofertas nuevas subidas" al final
And se retorna None (sin entrada al scheduler)
```

### Escenario 2: Scheduler diario a las 09:00
```gherkin
Given config con schedule.frequency="daily" y schedule.hour="09:00"
When llamo start_scheduler(config)
Then schedule.every().day.at("09:00") está registrado
And el loop espera y ejecuta el flujo a las 09:00 horas
```

### Escenario 3: Scheduler semanal (lunes)
```gherkin
Given config con schedule.frequency="weekly" y schedule.hour="10:00"
When llamo start_scheduler(config)
Then schedule.every().monday.at("10:00") está registrado
And el flujo solo se ejecuta los lunes
```

### Escenario 4: Scheduler cada 3 horas
```gherkin
Given config con schedule.frequency="every_3h"
When llamo start_scheduler(config)
Then schedule.every(3).hours está registrado
And la primera ejecución es inmediata
And las siguientes son cada 3 horas
```

### Escenario 5: Scheduler deshabilitado
```gherkin
Given config con schedule.enabled=false
When llamo start_scheduler(config)
Then se imprime "Scheduler deshabilitado en config.yaml"
And no se inicia el loop de schedule
And la función retorna sin error
```

### Escenario 6: Tolerancia a fallos
```gherkin
Given scheduler en ejecución
Y run_job() lanza una excepción no capturada durante el scraping
When el loop de scheduler captura la excepción
Then se loguea "Error en ejecución: {exception}"
And se loguea "Esperando próxima ejecución... ⌛"
And el scheduler continúa corriendo sin detenerse
```

## Detalles de implementación

### Tipos de frecuencia

```python
import re
from enum import Enum

class FrequencyType(str, Enum):
    daily = "daily"
    weekly = "weekly"

def parse_every_hours(frequency: str) -> int | None:
    """Extrae el número de horas de strings tipo 'every_3h', 'every_6h'."""
    match = re.fullmatch(r"every_(\d+)h", frequency)
    if match:
        return int(match.group(1))
    return None
```

### run_job()

```python
import time
from loguru import logger
from datetime import datetime

def run_job(config: AppConfig) -> None:
    """Ejecuta el flujo completo de JobHunter: auth → scrape → dedup → upload."""
    logger.info("=" * 50)
    logger.info("JobHunter iniciado")
    start = time.time()

    try:
        # 1. Auth
        ctx = asyncio.run(ensure_session(
            session_file=config.linkedin.session_file,
            headless=config.linkedin.headless,
        ))

        # 2. Scrape
        offers = asyncio.run(scrape_offers(ctx, config.search))

        if not offers:
            logger.warning("No se encontraron ofertas en esta ejecución.")
            return

        logger.info(f"{len(offers)} ofertas encontradas en LinkedIn.")

        # 3. Dedup
        history = load_history(config.dedup.history_file)
        new_offers, history = filter_new_offers(offers, history)

        if not new_offers:
            logger.info("Todas las ofertas ya estaban en el historial (0 nuevas).")
            save_history(history, config.dedup.history_file)
            return

        logger.info(f"{len(new_offers)} ofertas nuevas detectadas (de {len(offers)} totales).")

        # 4. Upload a Drive
        drive_service = get_drive_service(
            credentials_file=config.google_drive.credentials_file,
            token_file=config.google_drive.token_file,
        )
        file_id, web_view_link = upload_csv(new_offers, drive_service, config.google_drive)

        # 5. Guardar historial actualizado
        save_history(history, config.dedup.history_file)

        elapsed = time.time() - start
        logger.info("=" * 50)
        logger.info(f"JobHunter finalizado en {elapsed:.1f}s")
        logger.info(f"✅ {len(new_offers)} ofertas nuevas subidas a Google Drive")
        logger.info(f"   Archivo: {web_view_link}")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"❌ Error en ejecución de JobHunter (después de {elapsed:.1f}s): {e}")
        logger.exception(e)
```

### Flujo de programación de schedule

```python
import schedule
import time

def start_scheduler(config: AppConfig) -> None:
    """Configura y ejecuta el loop del scheduler según ScheduleConfig."""
    if not config.schedule.enabled:
        logger.info("Scheduler deshabilitado en config.yaml")
        return

    logger.info("Configurando scheduler...")

    # Configurar job(s) según frecuencia
    if config.schedule.frequency == FrequencyType.daily:
        schedule.every().day.at(config.schedule.hour).do(run_job_wrapper, config)
        logger.info(f"🕙 Scheduler activado: ejecución diaria a las {config.schedule.hour}")

    elif config.schedule.frequency == FrequencyType.weekly:
        schedule.every().monday.at(config.schedule.hour).do(run_job_wrapper, config)
        logger.info(f"🕙 Scheduler activado: ejecución semanal los lunes a las {config.schedule.hour}")

    elif config.schedule.frequency.startswith("every_") and config.schedule.frequency.endswith("h"):
        hours = parse_every_hours(config.schedule.frequency)
        schedule.every(hours).hours.do(run_job_wrapper, config)
        logger.info(f"🕙 Scheduler activado: ejecución cada {hours} horas (inmediata primera vez)")

    else:
        logger.error(f"Frecuencia no soportada: {config.schedule.frequency}")
        return

    # Ejecutar job inmediatamente en modo every_Xh
    if config.schedule.frequency.startswith("every_"):
        logger.info("Ejecutando primera corrida inmediata...")
        run_job(config)

    # Loop principal
    logger.info("Scheduler corriendo... (Ctrl+C para detener)")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler detenido por el usuario.")


def run_job_wrapper(config: AppConfig) -> None:
    """Wrapper seguro de run_job para que el loop de schedule no se rompa."""
    try:
        run_job(config)
    except Exception as e:
        logger.error(f"Error en ejecución programada: {e}")
        logger.exception(e)
```

### Alternativa: generador de crontab

```python
def generate_crontab(config: AppConfig) -> str:
    """
    Genera la entrada de crontab para el usuario (alternativa al scheduler Python).
    Crudeza: usa el comando CLI jobhunter run.
    """
    if not config.schedule.enabled:
        return "# Scheduler deshabilitado"

    hour, minute = config.schedule.hour.split(":")
    command = f"cd $(dirname $0) && /usr/bin/env jobhunter run >> /var/log/jobhunter.log 2>&1"

    if config.schedule.frequency == FrequencyType.daily:
        return f"{minute} {hour} * * * {command}"

    elif config.schedule.frequency == FrequencyType.weekly:
        return f"{minute} {hour} * * 1 {command}"  # 1 = lunes

    elif config.schedule.frequency.startswith("every_"):
        hours = parse_every_hours(config.schedule.frequency)
        step = f"*/{hours}"
        return f"{minute} {hour} * * * {step} {command}"

    return f"# Frecuencia no soportada: {config.schedule.frequency}"
```

## Tareas derivadas (del plan de acción)

- Paso 9.1: Implementar función `run_job()`
- Paso 9.2: Implementar loop del scheduler
