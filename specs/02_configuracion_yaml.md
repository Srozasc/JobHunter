# Spec: Configuración y Validación (config.py)

## Historia de usuario

Como usuario de JobHunter, quiero definir mis parámetros de búsqueda, schedule y credenciales de Google Drive en un archivo `config.yaml`, para que cada ejecución use mis preferencias sin modificar código.

## Asunciones acordadas

1. Ruta de `config.yaml` es relativa al directorio de trabajo (cwd), no absoluta.
2. Si no existe, mensaje: `"No se encontró config.yaml. Ejecuta 'jobhunter init' para crearlo."` + exit code 1.
3. Pydantic v2 con `model_validate()`.
4. Experience levels: `entry=1, associate=2, mid_senior=3, director=4, executive=5`.
5. Date posted: `past_24h=r86400, past_week=r604800, past_month=r2592000`.
6. `folder_id` vacío = carpeta raíz de Drive.

## Criterios de aceptación

### AC-1: Carga exitánica
- Cuando `config.yaml` existe y es válido, entonces `load_config()` retorna un objeto `AppConfig` con todos los campos accesibles por atributo.

### AC-2: Valores por defecto
- Cuando una sección opcional está ausente en el YAML, entonces los valores por defecto de Pydantic se aplican sin error.

### AC-3: Tipado estricto
- Cuando se define un valor inválido en un campo (ej: `frequency: "cada_rato"`), entonces Pydantic lanza un error legible indicando el campo, valor recibido y opciones válidas.

### AC-4: Errores humanos
- Cuando `config.yaml` no existe, entonces NO se muestra un stack trace sino un mensaje acciónable.
- Cuando un campo es inválido, entonces el error indica nombre del archivo, línea (si es posible) y campo problemático.

### AC-5: Rutas relativas
- Cuando un campo de tipo ruta (`session_file`, `history_file`, `credentials_file`, `token_file`) tiene un valor relativo, entonces se resuelve relativo al directorio de trabajo de la CLI.

## Escenarios BDD

### Escenario 1: Carga exitosa
```gherkin
Given un archivo config.yaml válido con todas las secciones
When llamo load_config("config.yaml")
Then retorna un objeto AppConfig
And config.search.keywords == "python developer"
And config.search.max_results == 100
And config.schedule.frequency == "daily"
```

### Escenario 2: Archivo inexistente
```gherkin
Given que no existe config.yaml en el directorio actual
When llamo load_config("config.yaml")
Then se lanza FileNotFoundError con mensaje "No se encontró config.yaml. Ejecuta 'jobhunter init' para crearlo."
And exit code es 1
```

### Escenario 3: Campo inválido
```gherkin
Given un config.yaml con frequency: "cada_rato"
When llamo load_config("config.yaml")
Then se lanza ValidationError
And el mensaje incluye "frequency"
And el mensaje indica opciones válidas: "daily", "weekly", "every_Xh"
```

### Escenario 4: Valores por defecto
```gherkin
Given un config.yaml mínimo con solo search.keywords
When llamo load_config("config.yaml")
Then config.search.max_results == 100 (default)
And config.schedule.enabled == true (default)
And config.dedup.history_file == "data/history/offers_history.json" (default)
```

### Escenario 5: Rutas relativas
```gherkin
Given un config.yaml con session_file: "data/session/linkedin.json"
When llamo load_config("config.yaml")
And el cwd es "/home/user/JobHunter"
Then config.linkedin.session_file se resuelve a "/home/user/JobHunter/data/session/linkedin.json"
```

## Detalles de implementación

### Modelos Pydantic

```python
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field

class ExperienceLevel(str, Enum):
    entry = "entry"
    associate = "associate"
    mid_senior = "mid_senior"
    director = "director"
    executive = "executive"

class DatePosted(str, Enum):
    past_24h = "past_24h"
    past_week = "past_week"
    past_month = "past_month"

class JobType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    temporary = "temporary"
    internship = "internship"

class Frequency(str, Enum):
    daily = "daily"
    weekly = "weekly"

class LinkedInConfig(BaseModel):
    session_file: str = "data/session/linkedin_session.json"
    headless: bool = True

class SearchConfig(BaseModel):
    keywords: str = Field(..., description="Términos de búsqueda")
    location: str = ""
    experience_level: list[ExperienceLevel] = []
    date_posted: DatePosted = DatePosted.past_week
    job_type: list[JobType] = []
    remote: bool = False
    max_results: int = Field(default=100, ge=1, le=500)
    sort_by: str = "recent"  # "recent" | "relevant"

class ScheduleConfig(BaseModel):
    enabled: bool = True
    frequency: Frequency = Frequency.daily
    every_hours: int = Field(default=24, ge=1, le=720)
    hour: str = "09:00"  # formato HH:MM

class GDriveConfig(BaseModel):
    credentials_file: str = "credentials.json"
    token_file: str = "token.json"
    folder_id: str = ""  # vacío = raíz
    filename_prefix: str = "ofertas"

class DedupConfig(BaseModel):
    history_file: str = "data/history/offers_history.json"

class AppConfig(BaseModel):
    linkedin: LinkedInConfig = LinkedInConfig()
    search: SearchConfig
    schedule: ScheduleConfig = ScheduleConfig()
    google_drive: GDriveConfig = GDriveConfig()
    dedup: DedupConfig = DedupConfig()
```

### Función principal

```python
from pathlib import Path
import yaml
from loguru import logger

def load_config(path: str = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        logger.error(f"No se encontró {path}. Ejecuta 'jobhunter init' para crearlo.")
        raise SystemExit(1)
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as e:
        logger.error(f"Error de validación en {path}:\n{e}")
        raise SystemExit(1)
```

## Tareas derivadas (del plan de acción)

- Paso 2.1: Definir modelos Pydantic
- Paso 2.2: Implementar load_config()
- Paso 2.3: Tests de configuración
