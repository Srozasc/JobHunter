# JobHunter — Plan de Acción

---

## Tarea 1: Inicialización del Proyecto

### Paso 1.1. Crear estructura de paquetes Python

**Explicación técnica**: Crear la estructura de directorios y archivos `__init__.py` para que Python reconozca los paquetes.

##### Desglose de Tareas

###### Crear directorios de paquetes
* Crear los directorios `jobhunter/`, `jobhunter/linkedin/`, `jobhunter/drive/`, `data/session/`, `data/history/`, `tests/`, `specs/`
* `Crear` Directorios del proyecto

###### Crear `__init__.py` en cada paquete
* Archivos vacíos que marcan directorios como paquetes Python
* `jobhunter/__init__.py` — Crear
* `jobhunter/linkedin/__init__.py` — Crear
* `jobhunter/drive/__init__.py` — Crear
* `tests/__init__.py` — Crear

---

### Paso 1.2. Crear `pyproject.toml`

**Explicación técnica**: Definir dependencias, metadata y entry points del proyecto para poder instalarlo con `pip install -e .`.

##### Desglose de Tareas

###### Crear `pyproject.toml`
* Definir proyecto con `setuptools` o `hatchling`, dependencias: `playwright`, `pydantic`, `pyyaml`, `typer`, `loguru`, `google-api-python-client`, `google-auth-oauthlib`, `schedule`, `aiohttp`. Dev deps: `pytest`, `pytest-asyncio`, `pytest-mock`.
* `pyproject.toml` — Crear

---

### Paso 1.3. Crear `config.example.yaml`

**Explicación técnica**: Template de configuración que el usuario copia como `config.yaml` y personaliza.

##### Desglose de Tareas

###### Crear `config.example.yaml`
* Todos los campos documentados en la especificación de `config.py`, con comentarios explicativos y valores de ejemplo.
* `config.example.yaml` — Crear

---

### Paso 1.4. Crear `.gitignore`

**Explicación técnica**: Evitar subir credenciales, tokens, sesiones y archivos sensibles al repositorio.

##### Desglose de Tareas

###### Crear `.gitignore`
* Ignorar: `config.yaml`, `credentials.json`, `token.json`, `data/`, `*.pyc`, `__pycache__/`, `.venv/`, `dist/`, `build/`
* `.gitignore` — Crear

---

## Tarea 2: Configuración y Validación (`config.py`)

### Paso 2.1. Definir modelos Pydantic

**Explicación técnica**: Crear los modelos de validación con Pydantic v2 que representan la estructura de `config.yaml`.

##### Desglose de Tareas

###### Crear `jobhunter/config.py`
* Clases: `LinkedInConfig`, `SearchConfig`, `ScheduleConfig`, `GDriveConfig`, `DedupConfig`, `AppConfig`.
* Cada campo con tipo, valor por defecto y descripción.
* `jobhunter/config.py` — Crear

---

### Paso 2.2. Implementar `load_config()`

**Explicación técnica**: Función que lee el YAML, lo valida con Pydantic y retorna el objeto de configuración.

##### Desglose de Tareas

###### Implementar función `load_config(path: str) -> AppConfig`
* Lee archivo YAML con `yaml.safe_load()`.
* Valida con `AppConfig.model_validate()`.
* Maneja errores descriptivos (archivo no encontrado, campo inválido).
* `jobhunter/config.py` — Actualizar

---

### Paso 2.3. Tests de configuración

##### Desglose de Tareas

###### Crear `tests/test_config.py`
* Test: carga exitosa con config válida.
* Test: error con archivo inexistente.
* Test: valores por defecto se aplican correctamente.
* Test: validación rechaza tipos incorrectos.
* `tests/test_config.py` — Crear

---

## Tarea 3: Autenticación LinkedIn (`linkedin/auth.py`)

### Paso 3.1. Implementar flujo de login con Playwright

**Explicación técnica**: Abrir navegador para login manual del usuario y persistir la sesión.

##### Desglose de Tareas

###### Crear `jobhunter/linkedin/auth.py`
* Función `async def ensure_session(headless=False) -> BrowserContext`.
* Función `async def _is_session_valid(ctx) -> bool`.
* Login flow: abrir navegador → esperar feed → guardar storage_state.
* Permisos `0600` en archivo de sesión.
* `jobhunter/linkedin/auth.py` — Crear

---

### Paso 3.2. Tests de autenticación (mock)

##### Desglose de Tareas

###### Crear tests con mock de Playwright
* Test: sesión válida se reutiliza sin abrir navegador.
* Test: sesión inexistente abre navegador.
* Test: sesión expirada detecta redirección a login.
* `tests/test_auth.py` — Crear

---

## Tarea 4: Selectores DOM (`linkedin/selectors.py`)

### Paso 4.1. Definir selectores con fallbacks

**Explicación técnica**: Centralizar todos los selectores CSS/XPath en un diccionario con listas de fallback para resistir cambios de UI de LinkedIn.

##### Desglose de Tareas

###### Crear `jobhunter/linkedin/selectors.py`
* Diccionario `SELECTORS` con claves: `job_card`, `title`, `company`, `location`, `url`, `description`, `next_page_btn`.
* Cada clave mapea a lista de selectores CSS ordenados por prioridad.
* Función `async def find_element(page, key)` que itera fallbacks.
* `jobhunter/linkedin/selectors.py` — Crear

---

## Tarea 5: Scraping de Ofertas (`linkedin/scraper.py`)

### Paso 5.1. Construir URL de búsqueda desde configuración

**Explicación técnica**: Traducir los filtros del `config.yaml` a parámetros de URL de LinkedIn Jobs.

##### Desglose de Tareas

###### Implementar `_build_search_url(search: SearchConfig) -> str`
* Mapeo de `date_posted` → `f_TPR` (r86400, r604800, r2592000).
* Mapeo de `experience_level` → `f_E` (1,2,3,4,5,6).
* Mapeo de `job_type` → `f_JT` (F,P,C,T,I).
* Mapeo de `remote` → `f_WT` (1,2,3).
* `jobhunter/linkedin/scraper.py` — Crear

---

### Paso 5.2. Implementar extracción de ofertas por página

**Explicación técnica**: Iterar sobre job cards en la página de resultados y extraer datos básicos.

##### Desglose de Tareas

###### Implementar `_extract_offers_from_page(page) -> list[dict]`
* Esperar a que carguen job cards.
* Iterar sobre cada card, extraer: title, company, location, url.
* Usar `find_element()` de `selectors.py` para cada campo.
* `jobhunter/linkedin/scraper.py` — Actualizar

---

### Paso 5.3. Implementar extracción de descripción

**Explicación técnica**: Navegar a cada oferta individual para extraer la descripción completa.

##### Desglose de Tareas

###### Implementar `_extract_description(page, url) -> str`
* Navegar a la URL de la oferta.
* Esperar selector de descripción.
* Extraer texto limpio.
* `jobhunter/linkedin/scraper.py` — Actualizar

---

### Paso 5.4. Implementar paginación y flujo principal

**Explicación técnica**: Orquestar la navegación por múltiples páginas hasta alcanzar `max_results`.

##### Desglose de Tareas

###### Implementar `async def scrape_offers(ctx, search) -> list[dict]`
* Loop: extraer página → siguiente página → hasta `max_results` o sin más páginas.
* Rate limiting: `asyncio.sleep(random.uniform(1.5, 3.5))`.
* Logging de progreso por página.
* Manejo de timeout por página (30s).
* `jobhunter/linkedin/scraper.py` — Actualizar

---

### Paso 5.5. Tests de scraping (mock)

##### Desglose de Tareas

###### Crear `tests/test_scraper.py`
* Test: construcción de URL con todos los filtros.
* Test: construcción de URL con filtros mínimos.
* Test: extracción de oferta desde HTML mock.
* Test: paginación se detiene al alcanzar max_results.
* `tests/test_scraper.py` — Crear

---

## Tarea 6: Deduplicación (`dedup.py`)

### Paso 6.1. Implementar carga y guardado de historial

##### Desglose de Tareas

###### Crear `jobhunter/dedup.py`
* `def load_history(path) -> dict`
* `def save_history(history, path)` — escritura atómica (temp + rename).
* `def normalize_url(url) -> str` — remover params de tracking.
* `jobhunter/dedup.py` — Crear

---

### Paso 6.2. Implementar filtrado de ofertas nuevas

##### Desglose de Tareas

###### Implementar `def filter_new_offers(offers, history) -> tuple[list, dict]`
* Compara URL normalizada contra historial.
* Retorna solo ofertas nuevas + historial actualizado.
* `jobhunter/dedup.py` — Actualizar

---

### Paso 6.3. Tests de deduplicación

##### Desglose de Tareas

###### Crear `tests/test_dedup.py`
* Test: oferta nueva se incluye.
* Test: oferta duplicada se filtra.
* Test: historial se guarda correctamente.
* Test: normalize_url remueve tracking params.
* `tests/test_dedup.py` — Crear

---

## Tarea 7: Google Drive — Autenticación (`drive/auth.py`)

### Paso 7.1. Implementar flujo OAuth2

**Explicación técnica**: Autenticación con Google Drive API usando OAuth2 Desktop flow con token persistente.

##### Desglose de Tareas

###### Crear `jobhunter/drive/auth.py`
* Función `def get_drive_service(credentials_file, token_file)`.
* Carga token existente o inicia flujo OAuth2.
* Refresh automático si token expiró.
* Retorna `googleapiclient.discovery.Resource`.
* `jobhunter/drive/auth.py` — Crear

---

### Paso 7.2. Documentar configuración de Google Cloud Console

##### Desglose de Tareas

###### Crear documento de setup
* Instrucciones paso a paso: crear proyecto en GCP → habilitar Drive API → crear credenciales OAuth2 Desktop → descargar `credentials.json`.
* Agregar a `README.md` o `Documentacion/setup_google_drive.md`.
* `Documentacion/setup_google_drive.md` — Crear

**⚠️ Acción manual requerida**: El usuario debe crear el proyecto en Google Cloud Console y descargar `credentials.json`.

---

## Tarea 8: Google Drive — Uploader (`drive/uploader.py`)

### Paso 8.1. Implementar generación de CSV en memoria

##### Desglose de Tareas

###### Crear `jobhunter/drive/uploader.py`
* Función `def generate_csv(offers) -> io.StringIO`.
* Columnas: `titulo,empresa,ubicacion,descripcion,url,fecha_extraccion`.
* Encoding UTF-8 con BOM.
* `jobhunter/drive/uploader.py` — Crear

---

### Paso 8.2. Implementar subida a Google Drive

##### Desglose de Tareas

###### Implementar `def upload_csv(offers, drive_service, config) -> str`
* Genera CSV en memoria.
* Nombre: `{prefix}_{YYYYMMDD_HHMMSS}.csv`.
* Sube con `files().create()` + `MediaInMemoryUpload`.
* Configura parent folder si `folder_id` está definido.
* Retorna file_id y webViewLink.
* `jobhunter/drive/uploader.py` — Actualizar

---

### Paso 8.3. Tests de uploader (mock)

##### Desglose de Tareas

###### Crear `tests/test_drive.py`
* Test: CSV generado tiene columnas correctas.
* Test: upload con mock de Drive API retorna file_id.
* Test: nombre de archivo incluye timestamp.
* `tests/test_drive.py` — Crear

---

## Tarea 9: Scheduler (`scheduler.py`)

### Paso 9.1. Implementar función `run_job()`

**Explicación técnica**: Orquesta el flujo completo en orden: auth → scrape → dedup → upload.

##### Desglose de Tareas

###### Crear `jobhunter/scheduler.py`
* Función `def run_job(config: AppConfig)`.
* Flujo: ensure_session → scrape_offers → filter_new_offers → upload_csv → save_history.
* Logging de inicio, fin, cantidad de ofertas nuevas, errores.
* Manejo de excepciones: no rompe el scheduler.
* `jobhunter/scheduler.py` — Crear

---

### Paso 9.2. Implementar loop del scheduler

##### Desglose de Tareas

###### Implementar `def start_scheduler(config: AppConfig)`
* Configura `schedule` según `frequency` y `hour`.
* Loop: `while True: schedule.run_pending(); time.sleep(60)`.
* `jobhunter/scheduler.py` — Actualizar

---

## Tarea 10: CLI Principal (`main.py`)

### Paso 10.1. Implementar comandos CLI con Typer

##### Desglose de Tareas

###### Crear `jobhunter/main.py`
* `jobhunter init` — Copia `config.example.yaml` → `config.yaml` si no existe.
* `jobhunter login` — Ejecuta `ensure_session()` de `auth.py`.
* `jobhunter run` — Ejecuta `run_job(config)` una vez.
* `jobhunter schedule` — Ejecuta `start_scheduler(config)`.
* `jobhunter status` — Muestra: ofertas en historial, última ejecución, config actual.
* `jobhunter/main.py` — Crear

---

### Paso 10.2. Instalar Playwright browsers

##### Desglose de Tareas

###### Documentar instalación
* `playwright install chromium` — comando requerido tras instalar dependencias.
* Agregar a `README.md`.
* `README.md` — Actualizar

**⚠️ Acción manual requerida**: El usuario debe ejecutar `playwright install chromium`.

---

## Tarea 11: Documentación y README

### Paso 11.1. Crear README.md completo

##### Desglose de Tareas

###### Crear `README.md`
* Descripción del proyecto.
* Instalación: `pip install -e .`, `playwright install chromium`.
* Configuración: copiar `config.yaml`, configurar Google Cloud.
* Uso: comandos CLI con ejemplos.
* Programación con cron: ejemplo de entrada crontab.
* `README.md` — Crear

---

## Tarea 12: Instalación y Primera Ejecución

### Paso 12.1. Instalar dependencias y verificar funcionamiento

##### Desglose de Tareas

###### Instalar en modo desarrollo
* `pip install -e .` en el directorio del proyecto.
* `playwright install chromium`.

###### Primera ejecución
* `jobhunter init` — Crear config.yaml.
* Editar `config.yaml` con parámetros deseados.
* `jobhunter login` — Login de LinkedIn.
* `jobhunter run` — Primera ejecución de prueba.
* Verificar CSV en Google Drive.

**⚠️ Acciones manuales requeridas**:
1. Crear proyecto en Google Cloud Console y descargar `credentials.json`.
2. Ejecutar `playwright install chromium`.
3. Ejecutar `jobhunter login` e ingresar credenciales de LinkedIn en el navegador.
