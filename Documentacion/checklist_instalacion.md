# Checklist de Instalación — JobHunter

Sigue estos pasos en orden. Marca cada casilla cuando lo completes.

---

## Pre-requisitos

- [ ] **1. Verificar Python 3.11+**
  ```bash
  python --version
  ```
  → Debe mostrar `Python 3.11.x` o superior.

- [ ] **2. Ubicarse en el directorio del proyecto**
  ```bash
  cd /ruta/a/JobHunter
  ```

## Instalación

- [ ] **3. Instalar dependencias**
  ```bash
  pip install -e .
  ```
  → Sin errores.

- [ ] **4. Instalar navegador Chromium (Playwright)**
  ```bash
  playwright install chromium
  ```
  → Descarga e instala Chromium.

- [ ] **5. Verificar instalación de la CLI**
  ```bash
  jobhunter --help
  ```
  → Debe mostrar 5 comandos: `init`, `login`, `run`, `schedule`, `status`.

## Google Cloud Console (una sola vez)

- [ ] **6. Configurar Google Drive API**
  Lee [`Documentacion/setup_google_drive.md`](Documentacion/setup_google_drive.md) y completa:
  - [ ] 6a. Crear proyecto en [Google Cloud Console](https://console.cloud.google.com)
  - [ ] 6b. Habilitar **Google Drive API**
  - [ ] 6c. Crear credenciales OAuth2 tipo **Desktop App**
  - [ ] 6d. Descargar JSON → renombrar a `credentials.json` → copiar a la raíz del proyecto

## Primera ejecución

- [ ] **7. Crear config.yaml**
  ```bash
  jobhunter init
  ```
  → Mensaje: "config.yaml creado exitosamente."
  - [ ] Edita `config.yaml` con tus keywords, ubicación y búsqueda deseada.

- [ ] **8. Login en LinkedIn**
  ```bash
  jobhunter login
  ```
  → Se abre un navegador. Inicia sesión en LinkedIn.
  → Mensaje: "Sesión de LinkedIn guardada exitosamente."

- [ ] **9. Ejecución de prueba**
  ```bash
  jobhunter run
  ```
  → Debe mostrar: ofertas encontradas, deduplicadas, y link al CSV en Drive.

- [ ] **10. Verificar Google Drive**
  Abre [https://drive.google.com](https://drive.google.com) → busca `ofertas_*.csv`.
  → Ábrelo con Google Sheets para verificar datos.

## Automatización (opcional)

- [ ] **11. Configurar automatización**
  **Opción A — Scheduler Python:**
  ```bash
  jobhunter schedule
  ```

  **Opción B — Crontab del sistema:**
  ```bash
  crontab -e
  # Agregar para ejecución diaria a las 09:00:
  0 9 * * * cd /ruta/a/JobHunter && jobhunter run >> ~/jobhunter.log 2>&1
  ```

---

✅ **¡Listo!** JobHunter está configurado y recolectando ofertas automáticamente.
