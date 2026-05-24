# JobHunter — Especificación de Características

## Sistema de Archivos

```
JobHunter/
├── config.yaml                      # Configuración del usuario (búsqueda, frecuencia, Google Drive)
├── jobhunter/
│   ├── __init__.py
│   ├── main.py                      # Entry point CLI (Typer app)
│   ├── config.py                    # Carga y validación de config.yaml (pydantic)
│   ├── linkedin/
│   │   ├── __init__.py
│   │   ├── auth.py                  # Login y gestión de sesión/cookies
│   │   ├── scraper.py               # Scraping de ofertas desde LinkedIn Jobs
│   │   └── selectors.py             # Selectores DOM con fallbacks
│   ├── dedup.py                     # Lógica de deduplicación contra historial
│   ├── drive/
│   │   ├── __init__.py
│   │   ├── auth.py                  # Autenticación OAuth2 Google Drive
│   │   └── uploader.py              # Creación de CSV en Google Drive
│   └── scheduler.py                 # Programación de ejecuciones (schedule library)
├── data/
│   ├── session/                     # Cookies de LinkedIn (gitignore)
│   │   └── linkedin_session.json
│   └── history/
│       └── offers_history.json      # Historial de URLs recolectadas (dedup)
├── specs/
│   └── ...
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_dedup.py
│   ├── test_scraper.py
│   ├── test_drive.py
│   └── conftest.py
├── pyproject.toml
├── README.md
└── Documentacion/inicial/
    ├── arquitectura.md
    ├── especificacion_caracteristicas.md
    └── plan_accion.md
```

---

## Especificaciones de Funcionalidades

### Funcionalidad 1: Configuración (`config.py`)

**Objetivo**: Cargar y validar el archivo `config.yaml` del usuario, proporcionando valores por defecto para todos los parámetros opcionales.

**Relaciones con APIs**:
- Lee `config.yaml` desde el directorio raíz del proyecto.
- Sin dependencias externas de API. Es el punto de entrada de configuración para todo el sistema.

**Requisitos Detallados**:
- Usar Pydantic (v2) para validación tipada con valores por defecto.
- Estructura YAML:

```yaml
linkedin:
  session_file: data/session/linkedin_session.json

search:
  keywords: "python developer"
  location: "Chile"
  experience_level: ["associate", "mid_senior"]  # opcional, se mapea a filtros URL
  date_posted: "past_week"                        # opcional: past_24h, past_week, past_month
  job_type: ["full_time"]                         # opcional: full_time, part_time, contract, remote
  max_results: 100                                 # opcional, default: 100
  sort_by: "recent"                                # recent | relevant

schedule:
  enabled: true
  frequency: "daily"      # "daily", "weekly", "every_Xh"
  hour: "09:00"           # hora de ejecución si daily/weekly

google_drive:
  credentials_file: "credentials.json"   # OAuth2 credentials de Google Cloud Console
  token_file: "token.json"               # Token persistente (auto-generado)
  folder_id: ""                          # ID de carpeta en Drive (vacío = raíz)
  filename_prefix: "ofertas"

dedup:
  history_file: data/history/offers_history.json
```

- Generar `config.example.yaml` con todos los campos documentados.
- Si `config.yaml` no existe, la CLI debe informar al usuario y sugerir copiar el example.

**Guía de Implementación**:
1. Crear clase `AppConfig` con nested models (`LinkedInConfig`, `SearchConfig`, `ScheduleConfig`, `GDriveConfig`, `DedupConfig`).
2. Función `load_config(path: str) -> AppConfig` que lee YAML, valida con Pydantic, y lanza errores descriptivos.
3. En `main.py`, cargar config al inicio de cada comando CLI.

---

### Funcionalidad 2: Autenticación LinkedIn (`linkedin/auth.py`)

**Objetivo**: Gestionar la sesión de LinkedIn del usuario, permitiendo login una vez y reutilización indefinida.

**Relaciones con APIs**:
- Usa Playwright para abrir Chromium/Chrome headless.
- Persiste `storage_state` (cookies + localStorage) en archivo JSON.
- No usa API privada de LinkedIn; opera sobre el navegador.

**Requisitos Detallados**:
- Función `ensure_session(session_file: str) -> BrowserContext`:
  - Si `session_file` existe y es válido, lo reutiliza.
  - Si no existe o la sesión expiró, abre navegador para login manual.
- Función `_is_session_valid(context) -> bool`:
  - Navega a `https://www.linkedin.com/feed/`
  - Verifica que URL final no redirige a login (detecta sesión expirada).
  - Detecta CAPTCHA y alerta al usuario.
- Login flow:
  1. Abre Chromium headed (visible) para que el usuario ingrese credenciales manualmente.
  2. Espera navegación exitosa al feed (`linkedin.com/feed`).
  3. Guarda `storage_state` en `session_file`.
  4. Permite re-usar headed o headless según config (`headless: bool`).
- Permisos de archivo: `session_file` debe tener permisos `0600` (solo lectura propietario).

**Guía de Implementación**:
1. Usar `async_playwright()` como context manager.
2. Lanzar browser con `chromium.launch(headless=False)` para login inicial.
3. Crear contexto con `browser.new_context()`, navegar a LinkedIn login.
4. Esperar manualmente (poll) hasta que el usuario complete login y llegue al feed.
5. Guardar con `context.storage_state(path=session_file)`.
6. En siguientes ejecuciones, cargar con `browser.new_context(storage_state=session_file)`.

---

### Funcionalidad 3: Scraping de Ofertas (`linkedin/scraper.py` + `linkedin/selectors.py`)

**Objetivo**: Navegar a LinkedIn Jobs con los filtros configurados, extraer ofertas y retornar structured data.

**Relaciones con APIs**:
- Recibe `BrowserContext` autenticado desde `auth.py`.
- Recibe `SearchConfig` desde `config.py`.
- Entrega lista de `Offer` dicts a `dedup.py`.
- Define selectores DOM en `selectors.py`.

**Requisitos Detallados**:

**`selectors.py`** define selectores CSS/XPath con lista de fallbacks:
```python
SELECTORS = {
    "job_card": [
        "div.job-card-container",
        "li.jobs-search-results__list-item",
        "div.base-card",
    ],
    "title": [
        "a.job-card-list__title",
        "h3.base-search-card__title",
    ],
    "company": [
        "a.job-card-container__company-name",
        "h4.base-search-card__subtitle",
    ],
    "location": [
        "span.job-card-container__metadata-item",
        "span.job-search-card__location",
    ],
    "url": [
        "a.job-card-list__title",
        "a.base-card__full-link",
    ],
    "description": [
        "div.jobs-description__content",
        "div.job-details",
    ],
    "next_page_btn": [
        "button[aria-label='Next']",
        "button.artdeco-pagination__button--next",
    ],
}
```

**`scraper.py`** flujo principal:
1. Construir URL de búsqueda a partir de `SearchConfig`:
   - Base: `https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}`
   - Agregar parámetros URL según filtros: `f_TPR=` (fecha), `f_E=` (experiencia), `f_JT=` (tipo), `f_WT=` (remoto).
2. Navegar a la URL, esperar carga de resultados (wait for selector `job_card`).
3. Loop de paginación:
   - Extraer todas las ofertas de la página actual.
   - Click en "Siguiente" / verificar existencia de siguiente página.
   - Hasta alcanzar `max_results` o agotar páginas.
4. Rate limiting: `await asyncio.sleep(random.uniform(1.5, 3.5))` entre páginas.
5. Para cada oferta, navegar a la URL de detalle y extraer descripción.
6. Retornar lista de dicts:

```python
{
    "id": str,            # URL normalizada como ID único
    "title": str,
    "company": str,
    "location": str,
    "url": str,
    "description": str,
    "date_posted": str,   # texto tal como aparece o None
    "scraped_at": str,    # ISO timestamp
}
```

**Guía de Implementación**:
1. `async def scrape_offers(ctx: BrowserContext, search: SearchConfig) -> list[dict]`.
2. Función auxiliar `_try_selectors(page, key)` que itera sobre la lista de selectores hasta encontrar uno válido.
3. Función `_extract_offer(card_element, page)` que extrae campos de un job card.
4. Función `_extract_description(page, url)` que navega al detalle y espera contenido.
5. Logging con progreso: loguru `logger.info("Página {n}: {x} ofertas extraídas")`.
6. Timeout por página: 30s. Si timeout, log warning y continua.

---

### Funcionalidad 4: Deduplicación (`dedup.py`)

**Objetivo**: Cruzar ofertas nuevas contra historial local para no duplicar URLs ya recolectadas.

**Relaciones con APIs**:
- Lee el `history_file` desde configuración.
- Recibe lista cruda de ofertas desde `scraper.py`.
- Entrega lista filtrada (solo nuevas) al flujo principal y al uploader de Drive.
- Actualiza el archivo de historial.

**Requisitos Detallados**:
- Historial como JSON: `{"url": {"title": ..., "company": ..., "first_seen": ...}, ...}`.
- Función `filter_new_offers(offers: list[dict], history_file: str) -> tuple[list[dict], dict]`:
  - Carga historial desde disco (o dict vacío si no existe).
  - Filtra ofertas cuya URL ya existe en el historial.
  - Retorna (nuevas_ofertas, historial_actualizado).
- Función `save_history(history: dict, history_file: str)`:
  - Escribe JSON con indent=2, crea directorio si no existe.
- La URL se normaliza (strip query params tracking como `?position=`) antes de comparar.

**Guía de Implementación**:
1. `def load_history(path) -> dict` — lee JSON o retorna `{}`.
2. `def normalize_url(url) -> str` — remueve params de tracking.
3. `def filter_new_offers(offers, history) -> tuple[list, dict]` — lógica principal.
4. `def save_history(history, path)` — escritura atómica (write temp + rename).

---

### Funcionalidad 5: Exportación a Google Drive (`drive/auth.py` + `drive/uploader.py`)

**Objetivo**: Autenticarse con Google Drive API y subir un archivo CSV con las ofertas nuevas.

**Relaciones con APIs**:
- Google Drive API v3 (`google-api-python-client`).
- Google OAuth2 (`google-auth-oauthlib`, `google-auth`).
- Recibe ofertas filtradas desde el flujo principal.
- Usa `GDriveConfig` para credenciales y carpeta destino.

**Requisitos Detallados**:

**`drive/auth.py`**:
- Función `get_drive_service(credentials_file, token_file) -> googleapiclient.discovery.Resource`:
  - Si `token_file` existe, carga credenciales desde ahí.
  - Si token expiró pero hay refresh_token, refresca automáticamente.
  - Si no hay token válido, inicia flujo OAuth2 de consola (`flow.run_console()` o `flow.run_local_server()`).
  - Guarda token en `token_file` para siguientes ejecuciones.
  - Retorna servicio de Drive v3.

**`drive/uploader.py`**:
- Función `upload_csv(offers: list[dict], drive_service, config: GDriveConfig) -> str`:
  - Genera CSV en memorio (`io.StringIO`) con columnas: `titulo,empresa,ubicacion,descripcion,url,fecha_extraccion`.
  - Nombre archivo: `{prefix}_{YYYYMMDD_HHMMSS}.csv`.
  - Sube a Google Drive usando `drive_service.files().create()` con `MediaInMemoryUpload`.
  - Si `folder_id` está configurado, lo usa como parent.
  - Retorna el ID del archivo creado y el URL público.
  - Encoding UTF-8 con BOM para compatibilidad con Excel/Sheets.

**Guía de Implementación**:
1. Crear proyecto en Google Cloud Console → habilitar Drive API → crear credenciales OAuth2 (Desktop App) → descargar `credentials.json`.
2. `google-auth-oauthlib` con scopes: `['https://www.googleapis.com/auth/drive.file']`.
3. CSV generado con `csv.DictWriter` sobre `io.StringIO`.
4. Upload con `MediaInMemoryUpload` (no escribe archivo temporal en disco).

---

### Funcionalidad 6: Scheduler (`scheduler.py`)

**Objetivo**: Ejecutar el flujo completo de JobHunter con la periodicidad configurada.

**Relaciones con APIs**:
- Orquesta: `config.py` → `auth.py` → `scraper.py` → `dedup.py` → `uploader.py`.
- Lee `ScheduleConfig` para determinar frecuencia.

**Requisitos Detallados**:
- Función `run_job(config: AppConfig)`:
  - Ejecuta el flujo completo: auth → scrape → dedup → upload.
  - Log de inicio, fin, cantidad de ofertas nuevas, errores.
  - Manejo de excepciones: si falla, log error pero no rompe el scheduler.
- Función `start_scheduler(config: AppConfig)`:
  - Si `frequency == "daily"`: ejecuta a la hora configurada cada día.
  - Si `frequency == "weekly"`: ejecuta a la hora configurada cada lunes.
  - Si `frequency == "every_Xh"`: ejecuta cada X horas.
  - Usa `schedule` library con loop `while True: schedule.run_pending(); time.sleep(60)`.
- Modo alternativo: generar entrada de cron (`crontab`) para el usuario.

**Guía de Implementación**:
1. `schedule.every().day.at("09:00").do(run_job, config)` para daily.
2. `schedule.every(2).hours.do(run_job, config)` para cada N horas.
3. Comando CLI `jobhunter run` (ejecución inmediata) y `jobhunter schedule` (modo continuo).
4. En `main.py`, Typer commands: `run` y `schedule`.

---

### Funcionalidad 7: CLI Principal (`main.py`)

**Objetivo**: Punto de entrada unificado con comandos claros.

**Comandos**:
- `jobhunter run` — Ejecuta un ciclo completo de scraping + upload.
- `jobhunter schedule` — Inicia el scheduler en modo continuo.
- `jobhunter login` — Abre navegador para login de LinkedIn (crea/renueva sesión).
- `jobhunter init` — Crea `config.yaml` desde el template de ejemplo.
- `jobhunter status` — Muestra estadísticas: ofertas en historial, última ejecución, etc.
