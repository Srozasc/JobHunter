# JobHunter 🎯

Recopilador automatizado de ofertas de empleo desde LinkedIn Jobs, con deduplicación y sincronización a Google Drive.

---

## Características

- ✅ Scraping parametrizable de LinkedIn Jobs (keywords, ubicación, experiencia, fecha, tipo, remoto)
- ✅ Login persistente — una sola vez por usuario
- ✅ Deduplicación automática por URL — no repite ofertas
- ✅ Exportación a Google Drive en CSV con timestamp
- ✅ Scheduler integrado — ejecución diaria, semanal o cada N horas
- ✅ CLI simple — `jobhunter run`, `jobhunter login`, `jobhunter status`

## Requisitos

- Python 3.11+
- Cuenta de LinkedIn
- Proyecto en Google Cloud Console (para Google Drive API) → [`Documentacion/setup_google_drive.md`](Documentacion/setup_google_drive.md)

## Instalación

```bash
pip install -e .
playwright install chromium
```

## Primeros pasos

1. **Configurar Google Drive API** (una sola vez):
   Lee [`Documentacion/setup_google_drive.md`](Documentacion/setup_google_drive.md) para obtener `credentials.json`.

2. **Inicializar configuración**:
   ```bash
   jobhunter init
   ```

3. **Editar `config.yaml`** con tus parámetros y el path a `credentials.json`:
   ```yaml
   linkedin:
     session_file: data/session/linkedin_session.json
     headless: true

   search:
     keywords: "python developer"
     location: "Remote"
     experience_level:
       - associate
       - mid_senior
     date_posted: past_week
     job_type:
       - full_time
     max_results: 100
     sort_by: recent

   schedule:
     enabled: true
     frequency: daily       # daily | weekly | every_3h
     hour: "09:00"

   google_drive:
     credentials_file: "credentials.json"
     token_file: "token.json"
     folder_id: ""
     filename_prefix: "ofertas"

   dedup:
     history_file: data/history/offers_history.json
   ```

4. **Login en LinkedIn** (una sola vez):
   ```bash
   jobhunter login
   ```
   Se abrirá un navegador. Inicia sesión en LinkedIn y espera la confirmación.

5. **Primera ejecución**:
   ```bash
   jobhunter run
   ```

6. **Ver resultado en Drive**:
   Abre [Google Drive](https://drive.google.com) → busca `ofertas_*.csv`.

7. **Ver estado**:
   ```bash
   jobhunter status
   ```

## Uso

### Comandos CLI

| Comando | Descripción |
|---|---|
| `jobhunter init [--force]` | Crea `config.yaml` desde el template de ejemplo |
| `jobhunter login [--force]` | Inicia sesión en LinkedIn (abre navegador) |
| `jobhunter run` | Ejecuta scraping + upload una vez |
| `jobhunter schedule` | Inicia el scheduler en modo continuo (loop) |
| `jobhunter status` | Muestra estado del proyecto |

## Automatización

### Scheduler Python (integrado)

Configura en `config.yaml`:
```yaml
schedule:
  enabled: true
  frequency: "daily"   # "daily", "weekly", "every_3h"
  hour: "09:00"
```

Luego ejecuta:
```bash
jobhunter schedule
```

Frecuencias soportadas:
- `"daily"` — todos los días a la hora configurada
- `"weekly"` — solo los lunes a la hora configurada
- `"every_3h"`, `"every_6h"`, etc. — cada N horas (primera ejecución inmediata)

### Crontab (alternativa)

Para ejecución diaria a las 09:00:
```bash
crontab -e
# Agregar:
0 9 * * * cd /ruta/a/JobHunter && jobhunter run >> ~/jobhunter.log 2>&1
```

Cada N horas (ej: cada 6h):
```bash
0 */6 * * * cd /ruta/a/JobHunter && jobhunter run >> ~/jobhunter.log 2>&1
```

## Solución de Problemas

### 🔴 LinkedIn: sesión expirada
**Causa:** LinkedIn cerró la sesión o detectó actividad inusual.
**Solución:** Ejecuta `jobhunter login` para re-autenticarte.

### 🟡 Selectores DOM rotos (no se extraen ofertas)
**Causa:** LinkedIn cambió su interfaz.
**Solución:** Ejecuta `python scripts/verify_selectors.py` para diagnosticar. Luego edita `jobhunter/linkedin/selectors.py` y actualiza los selectores. La fecha de última verificación está en el header del archivo.

### 🔴 Cuota de Google Drive API agotada
**Causa:** Límite gratuito de Google Drive API superado.
**Solución:** Esperar 24h o solicitar aumento de cuota en [Google Cloud Console](https://console.cloud.google.com/).

### 🟡 Timeout durante scraping
**Causa:** Reddit/ LinkedIn lento o bloqueando requests.
**Solución:** La ejecución continúa. Revisa la conexión. Si es frecuente, reduce `max_results` en `config.yaml`.

### ⚪ Token de Google Drive no encontrado
**Causa:** Primera ejecución — es normal.
**Solución:** Se creará automáticamente al ejecutar `jobhunter run`. Sigue el flujo de autorización en consola.

## Estructura del proyecto

```
JobHunter/
├── config.yaml              # Configuración del usuario
├── config.example.yaml      # Template de configuración
├── credentials.json         # OAuth2 credentials de GCP (manual)
├── token.json               # Token auto-generado (no subir)
├── jobhunter/
│   ├── main.py              # Entry point CLI (Typer)
│   ├── config.py            # Modelos Pydantic + load_config()
│   ├── dedup.py             # Deduplicación contra historial
│   ├── scheduler.py         # Scheduler + run_job()
│   ├── linkedin/
│   │   ├── auth.py          # Login persistente con Playwright
│   │   ├── selectors.py     # Selectores DOM con fallbacks (mayo 2026)
│   │   └── scraper.py       # Scraping de ofertas + paginación
│   └── drive/
│       ├── auth.py          # OAuth2 Google Drive
│       └── uploader.py      # Generación CSV + upload a Drive
├── data/
│   ├── session/             # Cookies de LinkedIn (gitignore)
│   └── history/             # Historial de URLs (dedup)
├── tests/                   # Pytest suite
├── Documentacion/
│   ├── inicial/             # Arquitectura, specs, plan de acción
│   └── setup_google_drive.md
└── specs/                   # Specs detalladas del proyecto
```

## Documentación técnica

- [Arquitectura](Documentacion/inicial/arquitectura.md) — visión general del sistema
- [Especificación de Características](Documentacion/inicial/especificacion_caracteristicas.md) — detalle funcional completo
- [Plan de Acción](Documentacion/inicial/plan_accion.md) — tareas de implementación
- [Configuración Google Drive](Documentacion/setup_google_drive.md) — paso a paso GCP
