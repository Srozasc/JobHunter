# JobHunter — Arquitectura

## QUÉ
JobHunter es una herramienta CLI en Python que:
- Inicia sesión en LinkedIn guardando la sesión del usuario (cookies) para reutilizarla.
- Scraping parametrizable de ofertas de empleo desde LinkedIn Jobs.
- Sincroniza las ofertas encontradas a un archivo CSV en Google Drive, evitando duplicados.
- Se puede ejecutar manualmente o programar vía cron con periodicidad configurable.

## QUIÉN
- Usuarios técnicos que buscan empleo activamente y quieren automatizar la recopilación de ofertas.
- El usuario único (Job Seeker) configura sus parámetros de búsqueda y obtiene un CSV organizado en su Drive.

## POR QUÉ
- LinkedIn no ofrece alertas granulares ni exportación masiva de resultados.
- Existen costos de platforms premium (LinkedIn Premium, Indeed Premium) para alertas avanzadas.
- Google Drive + CSV = simple, accesible, portable, analizable externamente (Sheets, Notion, Airtable).

## CÓMO (diferenciador)
- **Zero-config auth**: login de LinkedIn se hace una vez; persiste cookies en disco.
- **Config declarativa**: archivo YAML define parámetros de búsqueda y comportamiento (filtros, volumen, frecuencia).
- **CSV versionado**: cada ejecución crea un archivo nuevo con timestamp, pero se cruza contra un historial local para no repetir ofertas ya capturadas.
- **Tecnologías estándar**: Python + Playwright (scraping) + Google Drive API v3 + schedule/cron.

---

## Funcionalidades de Lanzamiento (MVP)

### 1. Configuración de Búsqueda
Archivo YAML donde el usuario define todos los filtros de búsqueda de LinkedIn Jobs como parámetros opcionales.
* Keywords / cargo
* Ubicación (país, ciudad, "remoto")
* Nivel de experiencia
* Fecha de publicación
* Tipo de empleo (full-time, part-time, contrato)
* Límite de resultados configurable
* Configuración de periodicidad (para cron)

### 2. Autenticación Persistente de LinkedIn
Login único del usuario mediante Playwright (navegador real); las cookies se persisten en disco para reutilización en ejecuciones futuras.
* Reutilización de sesión sin re-login
* Detección de sesión expirada con re-login automático vía navegador
* Almacenamiento seguro de cookies en disco (archivo encriptado o con permisos restrictivos)

### 3. Scraping de Ofertas desde LinkedIn Jobs
Navegación automatizada con Playwright sobre la página de resultados de LinkedIn Jobs, aplicando los filtros configurados y paginando resultados.
* Selectores DOM robustos con selectores de fallback
* Paginación automática hasta alcanzar el límite configurado
* Extracción por oferta: título, empresa, ubicación, descripción completa, URL de la oferta
* Rate limiting respetuoso (pausas aleatorias entre requests)
* Logging detallado de progreso

### 4. Deduplicación de Ofertas
Antes de escribir en el CSV, cada oferta se compara contra un historial local de URLs ya recolectadas.
* Historial local persistente como archivo JSON (mapeo URL → datos de la oferta)
* Toda URL ya registrada se ignora silencioso
* Solo ofertas nuevas se incluyen en el CSV de salida

### 5. Exportación a Google Drive (CSV)
Autenticación con Google Drive API; generación de un archivo CSV nuevo por ejecución con las ofertas no duplicadas.
* Autenticación OAuth2 con flujo de consola (una vez) + token refresh automático
* Estructura CSV: título, empresa, ubicación, descripción, url_oferta, fecha_extraccion
* Archivo nombrado con timestamp: `ofertas_YYYYMMDD_HHMMSS.csv`
* Carpeta de Drive configurable

### 6. Scheduler / Automatización
Ejecución programable que corre el flujo completo con la periodicidad definida por el usuario.
* Modo CLI manual: `python jobhunter.py run`
* Modo programado vía `schedule` library o sistema cron
* Archivo YAML define `frecuencia: "daily" | "weekly" | "Xh"` y hora opcional al inicio

---

## Funcionalidades Futuras (Post MVP)

### 7. Filtros Avanzados Post-Scraping
* Filtrar por rango salarial (si está visible)
* Filtrar por empresa excluida/incluida (blocklist/allowlist)
* Scoring de relevancia basado en keywords del usuario

### 8. Notificaciones
* Envío de resumen por email/Telegram/Discord con nuevas ofertas encontradas
* Alertas cuando se superan umbrales mínimos de resultados

### 9. Dashboard Web Ligero
* Interfaz Flask/FastAPI para visualizar ofertas, configurar búsquedas y ver historial
* Gráficas de tendencias (ofertas por empresa, ubicación, etc.)

### 10. Multi-Plataforma
* Extensión a Indeed, Glassdoor, GetOnBoard
* Unificación de fuentes en un solo CSV

---

## Tecnologías Principales

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11+ |
| Scraping / Navegación | Playwright (Chromium headless) |
| Configuración | YAML (archivo `config.yaml`) |
| Persistencia de sesión | Playwright storage_state (JSON) |
| Historial / Dedup | JSON local (`history.json`) |
| Google Drive API | google-api-python-client + google-auth-oauthlib |
| CLI Framework | Typer (CLI elegante con `--help`) |
| Logging | loguru o logging estándar |
| Scheduling | schedule library o cron del sistema |
| Testing | pytest + pytest-mock |
| Empaquetado | pyproject.toml (pip install -e .) |
