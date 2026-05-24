# Spec: Instalación y Primera Ejecución

## Historia de usuario

Como usuario, quiero tener una checklist clara para instalar JobHunter, configurar Google Drive, ejecutar el primer scraping y ver el CSV en Google Drive, para validar que todo funciona antes de automatizar.

## Asunciones acordadas

1. El README incluye los pasos detallados de la checklist. Esta tarea es el documento de verificación/apoyo.
2. Las instrucciones de Google Cloud Console van en `Documentacion/setup_google_drive.md` (separadas del README).
3. Se crea también `Documentacion/setup_google_drive.md` (sin incluir el contenido en el README).
4. Las "acciones manuales" son ejecutadas por el usuario — no se automatizan en código.
5. Después de la instalación, el usuario tiene: `config.yaml` válido, `credentials.json` descargado, sesión LinkedIn activa, y Drive con el primer CSV.

## Criterios de aceptación

### AC-1: Checklist de instalación
- Cuando el usuario abre `Documentacion/checklist_instalacion.md`, entonces ve pasos numerados y verificables.
- Cada paso tiene un checkbox o campo para marcar completado.
- Cada paso indica el resultado esperado (ej: "ver versión de Python", "ver ayuda de jobhunter").

### AC-2: Documento de Google Drive separado
- Cuando el usuario necesita configurar Google Drive, entonces lee `Documentacion/setup_google_drive.md` sin tener que consultar el README.
- El README tiene un solo enlace a ese documento.

### AC-3: Primera ejecución exitosa
- Cuando el usuario completa todos los pasos de la checklist, entonces ejecuta `jobhunter run` y ve un CSV nuevo en su Google Drive con las ofertas recolectadas.

### AC-4: Validación de archivos de instalación
- Cuando el usuario ejecuta `python --version`, entonces ve `Python 3.11+`.
- Cuando ejecuta `jobhunter --help`, entonces ve los 5 comandos disponibles.
- Cuando ejecuta `playwright --version`, entonces ve una versión >= 1.40.

### AC-5: Credenciales de Google Drive
- Cuando el usuario tiene `credentials.json` en el directorio del proyecto, entonces ejecutar `jobhunter run` no falla por falta de credenciales.
- Cuando el token de Google Drive expira o falta, entonces el flujo OAuth2 se ejecuta automáticamente.

## Escenarios BDD

### Escenario 1: Checklist de instalación completa
```gherkin
Given el usuario clona el repositorio y sigue la checklist de instalación
When completa todos los pasos sin errores
Then logra ejecutar `jobhunter run` exitosamente
And ve un nuevo archivo CSV en su Google Drive
```

### Escenario 2: Credenciales de Google Drive ausentes
```gherkin
Given el usuario ejecuta `jobhunter run` sin tener credentials.json
When el flujo de upload a Drive se ejecuta
Then se imprime "No se encontró credentials.json" con enlace a setup_google_drive.md
And el scraper no se detiene (error solo en la fase de upload)
```

### Escenario 3: Primera ejecución termina sin duplicados
```gherkin
Given el usuario ejecuta `jobhunter run` por primera vez
And no existe historial de ofertas
When la ejecución completa
Then se crea offers_history.json con las ofertas recolectadas
And se sube un CSV con nombre ofertas_YYYYMMDD_HHMMSS.csv a Drive
And todas las ofertas del CSV son nuevas (sin duplicados locales)
```

### Escenario 4: Segunda ejecución con deduplicación
```gherkin
Given el usuario ejecutó `jobhunter run` y recolectó 50 ofertas
When ejecuta `jobhunter run` de nuevo
Then el CSV de Drive solo contiene ofertas nuevas (las 50 anteriores se filtran)
And offers_history.json se actualiza con las nuevas ofertas
```

### Escenario 5: Scheduler automático
```gherkin
Given el usuario configuró frequency="daily" y hour="09:00" en config.yaml
And ejecutó `jobhunter schedule`
When pasan las 09:00 de un día
Then el flujo completo se ejecuta automáticamente
And se sube un nuevo CSV a Drive
```

## Detalles de implementación

### Checklist de instalación paso a paso

```
== INICIO —
□ 1. Verificar Python 3.11+
   python --version  → debe mostrar Python 3.11.x o superior

□ 2. Clonar o ubicarse en el directorio del proyecto
   cd /data/data/com.termux/files/home/proyectos/JobHunter

□ 3. Instalar dependencias
   pip install -e .

□ 4. Instalar navegador de Playwright
   playwright install chromium
   playwright --version  → debe mostrar versión >= 1.40

□ 5. Verificar instalación
   jobhunter --help  → debe mostrar 5 comandos: init, login, run, schedule, status

□ 6. Obtener credenciales de Google Drive (ver Documentacion/setup_google_drive.md)
   □ 6a. Crear cuenta en Google Cloud Console
   □ 6b. Crear proyecto → habilitar Drive API
   □ 6c. Crear credenciales OAuth2 (Desktop App) → descargar credentials.json
   □ 6d. Guardar credentials.json en el directorio del proyecto

□ 7. Crear config.yaml
   jobhunter init  → crea config.yaml desde config.example.yaml
   Editar config.yaml con tus palabras clave, ubicación y credenciales de Drive

□ 8. Login en LinkedIn
   jobhunter login  → abre navegador, ingresa credenciales, espera a llegar a feed
   Deja la sesión activa hasta que diga "Sesión guardada exitosamente".

□ 9. Ejecución de prueba
   jobhunter run
   Verifica que el output muestre: ofertas encontradas, deduplicadas y subidas a Drive.

□ 10. Verificar Drive
   Abre https://drive.google.com → busca archivo ofertas_*.csv → ábrelo en Sheets.

== FIN —
□ 11. Automatizar (opcional)
   Editar config.yaml → schedule habilitado o agregar entrada en crontab.
   O ejecutar: jobhunter schedule (loop Python)
```

### Contenido de `Documentacion/setup_google_drive.md`

```markdown
# Configuración de Google Drive API

## Paso 1: Crear proyecto en Google Cloud Console

1. Ve a https://console.cloud.google.com
2. Crea un proyecto nuevo (ej: `jobhunter-drive-<tu-nombre>`).
3. En la barra de búsqueda, escribe "Google Drive API" y habilítalo.

## Paso 2: Crear credenciales OAuth2

1. Menú izquierdo → "APIs & Services" → "Credentials".
2. Click "Create Credentials" → "OAuth 2.0 Client ID".
3. Application type: **Desktop app**.
4. Name: `JobHunter Desktop`.
5. Click "Create" → descarga el JSON.
6. Renombra el archivo descargado a `credentials.json`.
7. Colócalo en el directorio raíz de JobHunter.

## Paso 3: Verificar funcionamiento

Ejecuta `jobhunter run`. La primera vez:
1. Se imprimirá una URL de Google en la terminal.
2. Abre esa URL en tu navegador, autoriza el acceso.
3. Pega el código de verificación en la terminal.
4. Se crea `token.json` automáticamente.

Las próximas ejecuciones ya no pedirán autorización.
```

### Contenido de `Documentacion/checklist_instalacion.md`

```markdown
# Checklist de Instalación — JobHunter

Sigue estos pasos en orden. Marca cada casilla cuando lo completes.

[Ver documentación en la sección "Detalles de implementación" de esta spec]
```

## Tareas derivadas (del plan de acción)

- Paso 11.1: Crear README.md (ya cubierta en Tarea 11)
- Paso 12.1: Crear checklist_instalacion.md y Documentacion/setup_google_drive.md
- Paso 12.1: Definir schedule y cron en README
