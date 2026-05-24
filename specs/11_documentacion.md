# Spec: Documentación y README.md

## Historia de usuario

Como usuario nuevo en el proyecto, quiero leer un `README.md` completo que me explique qué es JobHunter, cómo instalarlo, configurarlo, usarlo y automatizarlo, para poder empezar a usarlo sin leer el código fuente.

## Asunciones acordadas

1. El README incluye secciones en este orden: Descripción, Características, Instalación, Configuración, Uso (comandos CLI), Programación (cron + scheduler Python), Solución de Problemas, y Requisitos.
2. Incluye sección "Primeros pasos" paso a paso: `pip install -e .` → `playwright install chromium` → `jobhunter init` → editar `config.yaml` → `jobhunter login` → `jobhunter run`.
3. Incluye un ejemplo completo de `config.yaml` (campos comentados) para que el usuario copie y adapte.
4. Las instrucciones para Google Cloud Console van en `Documentacion/setup_google_drive.md` (no en el README).
5. Incluye sección "Solución de Problemas" con errores comunes: sesión expirada, selectores rotos, cuota agotada en Drive, timeout scraping.
6. Incluye enlaces a `Documentacion/inicial/` para quien quiera profundizar en arquitectura.

## Criterios de aceptación

### AC-1: README existe y tiene todas las secciones
- Cuando el usuario abre `README.md`, entonces ve las secciones en este orden mínimo:
  - Descripción
  - Características
  - Instalación
  - Configuración
  - Uso
  - Automatización
  - Solución de Problemas
  - Requisitos

### AC-2: Primeros pasos funcionales
- Cuando el usuario sigue los pasos de "Primeros pasos", entonces llega a `jobhunter run` sin tener que consultar código fuente.
- El orden es: `pip install -e .` → `playwright install chromium` → `jobhunter init` → editar `config.yaml` → `jobhunter login` → `jobhunter run`.

### AC-3: Configuración por ejemplo
- Cuando el usuario lee `config.yaml` en el README, entonces ve TODOS los campos con valores de ejemplo y comentarios explicativos.
- Puede copiar y modificar según su perfil.

### AC-4: Enlace a Documentación
- Cuando el usuario busca detalles técnicos, entonces el README le redirige a `Documentacion/inicial/` con enlaces claros a cada documento.

### AC-5: Troubleshooting accionable
- Cada error listado en troubleshooting tiene: título del error, causa probable, solución paso a paso.
- Errores cubiertos: sesión expirada, selectores rotos, cuota Drive agotada, timeout scraping.

### AC-6: Enlace a setup_google_drive.md
- Cuando el usuario necesita configurar Google Drive, entonces el README le indica "Lee `Documentacion/setup_google_drive.md`" sin incluir las instrucciones en el propio README.

## Escenarios BDD

### Escenario 1: Usuario nuevo completa primeros pasos
```gherkin
Given un usuario que clona el repo y lee README.md
When sigue la sección "Primeros pasos" paso a paso
Then logra ejecutar `jobhunter run` sin consultar código fuente
And ve el resultado en Google Drive
```

### Escenario 2: Usuario busca troubleshooting por sesión expirada
```gherkin
Given el usuario recibe error "Sesión expirada"
When busca "LinkedIn" en la sección Troubleshooting
Then encuentra el error con causa y solución
And la solución le permite resolverlo sin abrir issue
```

### Escenario 3: Usuario busca cómo configurar Google Drive
```gherkin
Given el usuario necesita configurar Google Drive
When busca "Google" en el README
Then el único enlace encontrado es a Documentacion/setup_google_drive.md
```

### Escenario 4: Usuario copia config.yaml del README
```gherkin
Given el usuario ve el ejemplo de config.yaml en el README
When copia el bloque de código completo
And lo pega en su config.yaml
Then tiene un archivo válido sin errores de validación
```

### Escenario 5: Usuario decide automatizar con cron
```gherkin
Given el usuario quiere ejecución diaria a las 09:00
When lee la sección "Automatización"
Then encuentra ambos métodos: scheduler Python y entrada crontab
And puede elegir el que prefiera
```

## Detalles de implementación

### Estructura del README

```markdown
# JobHunter

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
- Google Cloud Console (para Google Drive API)
- Cuenta de LinkedIn

## Instalación

```bash
pip install -e .
playwright install chromium
```

## Primeros pasos

1. **Inicializar configuración**:
   ```bash
   jobhunter init
   ```

2. **Editar `config.yaml`** con tus parámetros de búsqueda y credenciales de Drive:
   ```yaml
   search:
     keywords: "python developer"
     location: "Remote"
     date_posted: "past_week"
     max_results: 100

   schedule:
     enabled: true
     frequency: "daily"
     hour: "09:00"

   google_drive:
     credentials_file: "credentials.json"
     folder_id: ""
   ```
   *(Documentación completa → `Documentacion/inicial/arquitectura.md`)*

3. **Login en LinkedIn**:
   ```bash
   jobhunter login
   ```

4. **Primera ejecución**:
   ```bash
   jobhunter run
   ```

5. **Ver estado**:
   ```bash
   jobhunter status
   ```

## Uso

### Comandos CLI

| Comando | Descripción |
|---|---|
| `jobhunter init [--force]` | Crea `config.yaml` desde el template de ejemplo |
| `jobhunter login [--force]` | Inicia sesión en LinkedIn |
| `jobhunter run [--dry-run]` | Ejecuta scraping + upload una vez |
| `jobhunter schedule` | Inicia el scheduler en modo continuo |
| `jobhunter status` | Muestra estado del proyecto |

## Automatización

### Scheduler Python (integrado)

```yaml
# config.yaml
schedule:
  enabled: true
  frequency: "daily"   # "daily", "weekly", "every_3h"
  hour: "09:00"
```

```bash
jobhunter schedule
```

### Crontab (alternativa)

```bash
# Agrega esta línea (edita con crontab -e)
0 9 * * * cd $(dirname $0) && jobhunter run >> ~/jobhunter_job.log 2>&1
```

*(Para más detalles → `Documentacion/inicial/arquitectura.md`)*

## Solución de Problemas

**LinkedIn: sesión expirada**  
Causa: LinkedIn detectó actividad inusual o ya pasaron meses desde el login.  
Solución: Ejecutar `jobhunter login` y validar de nuevo en el navegador.

**Selectores DOM rotos**  
Causa: LinkedIn cambió su UI.  
Solución: Ejecutar `python scripts/verify_selectors.py` para diagnosticar, luego editar `jobhunter/linkedin/selectors.py` y actualizar la fecha de verificación.

**Cuota de Google Drive agotada**  
Causa: Has alcanzado el límite gratuito de Google Drive API.  
Solución: Esperar 24h o solicitar aumento de cuota en Google Cloud Console.

**Timeout durante scraping**  
Causa: LinkedIn está lento o bloqueando la IP.  
Solución: Aumentar el timeout en `config.yaml` o reducir `max_results`.

## Documentación técnica

- [Arquitectura](Documentacion/inicial/arquitectura.md)
- [Especificación de Características](Documentacion/inicial/especificacion_caracteristicas.md)
- [Plan de Acción](Documentacion/inicial/plan_accion.md)
```

## Tareas derivadas (del plan de acción)

- Paso 11.1: Crear README.md completo
