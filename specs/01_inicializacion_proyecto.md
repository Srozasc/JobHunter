# Spec: Inicialización del Proyecto

## Historia de usuario

Como desarrollador, quiero que el proyecto JobHunter tenga una estructura de paquetes Python funcional desde el inicio, con dependencias declaradas en `pyplanticl.toml`, un template de configuración y un `.gitignore` completo, para poder instalarlo con `pip install -e .` y comenzar a iterar.

## Asunciones acordadas

1. Build backend: `hatchling`.
2. Python mínimo: `>=3.11`.
3. Entry point: `jobhunter = "jobhunter.main:app"`.
4. `.gitignore` incluye: `data/`, `specs/`, `Documentacion/`, `config.yaml`, `credentials.json`, `token.json`, `*.pyc`, `__pycache__/`, `.venv/`, etc.
5. `config.example.yaml` usa placeholders descriptivos sin datos sensibles.
6. `README.md` básico (título + descripción breve) se crea en este paso.

## Criterios de aceptación

### AC-1: Estructura de directorios
- Cuando el usuario ejecute `ls -R jobhunter/`, entonces debe ver los directorios `jobhunter/`, `jobhunter/linkedin/`, `jobhunter/drive/`, `data/session/`, `data/history/`, `tests/`, `specs/`.
- Todos los directorios de paquete (`jobhunter/`, `jobhunter/linkedin/`, `jobhunter/drive/`, `tests/`) contienen `__init__.py` vacío.

### AC-2: `pyproject.toml` válido
- Cuando el usuario ejecute `pip install -e .` desde la raíz del proyecto, entonces la instalación debe completarse sin errores.
- Cuando el usuario ejecute `jobhunter --help` tras la instalación, entonces debe ver la ayuda de Typer (aunque los comandos aún no estén implementados, el entry point debe existir).

### AC-3: `config.example.yaml`
- Cuando el usuario lea `config.example.yaml`, entonces debe ver todas las secciones: `linkedin`, `search`, `schedule`, `google_drive`, `dedup`.
- Todos los campos tienen comentarios explicativos y valores de ejemplo.

### AC-4: `.gitignore`
- Cuando el usuario verifique con `git status` después de crear `config.yaml`, entonces `config.yaml` no aparece como untracked.
- Cuando el usuario verifique con `git status`, entonces `data/`, `credentials.json`, `token.json` no aparecen como untracked.

### AC-5: `README.md`
- Cuando el usuario abra `README.md`, entonces ve el nombre del proyecto, descripción breve y secciones vacías: Instalación, Configuración, Uso.

## Escenarios BDD

### Escenario 1: Instalación limpia
```gherkin
Given el directorio del proyecto con estructura y pyproject.toml
When ejecuto `pip install -e .`
Then la instalación se completa con exit code 0
And el comando `jobhunter` existe en el PATH
```

### Escenario 2: Verificación de .gitignore
```gherkin
Given el archivo .gitignore creado
And un archivo config.yaml con credenciales de ejemplo
When ejecuto `git status --ignored`
Then config.yaml aparece en la lista de ignorados
And credentials.json aparece en la lista de ignorados
And toda la carpeta data/ está ignorada
```

### Escenario 3: Estructura de paquetes importable
```gherkin
Given pip install -e . completado
When ejecuto `python -c "import jobhunter"`
Then no hay ImportError
```

## Detalles de implementación

### Contenido de `pyproject.toml` (estructura objetivo)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "jobhunter"
version = "0.1.0"
description = "Recopilador automatizado de ofertas de empleo desde LinkedIn"
requires-python = ">=3.11"
dependencies = [
    "playwright>=1.40",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "typer>=0.9",
    "loguru>=0.7",
    "google-api-python-client>=2.100",
    "google-auth-oauthlib>=1.0",
    "schedule>=1.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
]

[project.scripts]
jobhunter = "jobhunter.main:app"
```

### Estructura de directorios objetivo

```
JobHunter/
├── config.example.yaml
├── config.yaml              ← (creado por usuario con `jobhunter init`)
├── credentials.json          ← (descargado por usuario desde GCP)
├── token.json                ← (auto-generado por OAuth2 flow)
├── pyproject.toml
├── README.md
├── .gitignore
├── jobhunter/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── dedup.py
│   ├── scheduler.py
│   ├── linkedin/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── scraper.py
│   │   └── selectors.py
│   └── drive/
│       ├── __init__.py
│       ├── auth.py
│       └── uploader.py
├── data/
│   ├── session/
│   │   └── linkedin_session.json
│   └── history/
│       └── offers_history.json
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_dedup.py
│   ├── test_scraper.py
│   └── test_drive.py
└── specs/
    └── (este archivo)
```

## Tareas derivadas (del plan de acción)

- Paso 1.1: Crear estructura de paquetes Python
- Paso 1.2: Crear `pyproject.toml`
- Paso 1.3: Crear `config.example.yaml`
- Paso 1.4: Crear `.gitignore`
