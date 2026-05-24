# Configuración de Google Cloud Console para JobHunter

## Paso a paso para obtener `credentials.json`

### 1. Crear proyecto en Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Click en el selector de proyectos (barra superior) → **New Project**.
3. Nombre sugerido: `jobhunter`.
4. Click en **Create**.

### 2. Habilitar Google Drive API

1. En el menú lateral: **APIs & Services** → **Library**.
2. Busca **Google Drive API**.
3. Click en **Enable**.

### 3. Crear credenciales OAuth2 (Desktop App)

1. En el menú lateral: **APIs & Services** → **Credentials**.
2. Click en **+ Create Credentials** → **OAuth 2.0 Client ID**.
3. Si te pide configurar la **OAuth consent screen**:
   - User Type: **External**.
   - App name: `JobHunter`.
   - User support email: tu email.
   - Developer contact info: tu email.
   - Guardar y continuar hasta terminar.
4. Application type: **Desktop app**.
5. Nombre: `jobhunter-desktop`.
6. Click en **Create**.
7. Click en **Download JSON** en la notificación emergente.

### 4. Instalar credenciales

Renombra el archivo descargado a `credentials.json` y muévelo a la raíz del proyecto:

```bash
mv ~/Downloads/client_secret_*.json /ruta/a/JobHunter/credentials.json
```

### 5. Primera ejecución

Al ejecutar `jobhunter run` por primera vez, se abrirá un flujo de autorización en consola:

1. Se imprimirá una URL. Ábrela en tu navegador.
2. Selecciona tu cuenta de Google y autoriza la app.
3. Copia el código de verificación y pégalo en la terminal.
4. Se generará automáticamente el archivo `token.json`.

> **Seguridad**: `credentials.json` y `token.json` contienen secretos.
> Nunca los subas al repositorio (están en `.gitignore`).
