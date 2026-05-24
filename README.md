# JobHunter

Recopilador automatizado de ofertas de empleo desde LinkedIn Jobs.
Extrae ofertas, las deduplica y las sube como CSV a Google Drive.

## Instalación

```bash
pip install -e .
playwright install chromium
```

## Configuración

1. Copia `config.example.yaml` → `config.yaml` y ajusta tus parámetros.
2. Crea un proyecto en [Google Cloud Console](https://console.cloud.google.com/),
   habilita Drive API y descarga las credenciales OAuth2 (Desktop App) como `credentials.json`.

## Uso

```bash
# Crear config.yaml desde el template
jobhunter init

# Iniciar sesión en LinkedIn (abre navegador)
jobhunter login

# Ejecutar un ciclo de scraping
jobhunter run

# Iniciar el scheduler en modo continuo
jobhunter schedule

# Ver estadísticas
jobhunter status
```

## Programación con cron

Para ejecutar `jobhunter run` todos los días a las 9:00:

```cron
0 9 * * * cd /ruta/a/JobHunter && jobhunter run >> /tmp/jobhunter.log 2>&1
```
