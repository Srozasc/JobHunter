# Spec: Google Drive — Uploader (drive/uploader.py)

## Historia de usuario

Como usuario, quiero que JobHunter suba automáticamente un archivo CSV con las ofertas nuevas a mi Google Drive, con un nombre que incluya la fecha de ejecución, para tener un historial versionado y accesible.

## Asunciones acordadas

1. El CSV tiene columnas fijas: `titulo,empresa,ubicacion,descripcion,url,fecha_extraccion`.
2. Nombre archivo: `{prefix}_{YYYYMMDD_HHMMSS}.csv`.
3. UTF-8 con BOM (`\ufeff`) para compatibilidad con Excel/Sheets.
4. Si `folder_id` vacío → carpeta raíz de Drive. Si definido → `parents: [folder_id]`.
5. La función retorna `(file_id, web_view_link)` del archivo creado.
6. Se permite descripción vacía o muy corta (no se salta por eso).

## Criterios de aceptación

### AC-1: Estructura CSV correcta
- Cuando se generan 3 ofertas de prueba, entonces el CSV tiene exactamente las columnas: `titulo,empresa,ubicacion,descripcion,url,fecha_extraccion`.
- Y la primer línea del CSV es el encabezado (sin BOM visible para el usuario, pero presente en el archivo).
- Y todas las ofertas están en filas separadas.

### AC-2: BOM UTF-8
- Cuando se abre el CSV en Excel, entonces el encoding se detecta como UTF-8 automáticamente.
- Y los caracteres especiales (tildes, eñes, acentos) no se corrompen.

### AC-3: Nombre con timestamp
- Cuando se ejecuta el 15 de enero de 2026 a las 10:30:00 UTC, entonces el nombre del archivo es `ofertas_20260115_103000.csv`.
- Y el nombre no incluye caracteres inválidos para sistemas de archivos.

### AC-4: Subida a carpeta específica
- Cuando `folder_id="abc123folder"` está configurado, entonces la subida incluye el parámetro `parents: ["abc123folder"]`.
- Cuando `folder_id=""`, entonces no se envía el campo `parents` y el archivo va a raíz.

### AC-5: Retorno de metadatos
- Cuando la subida es exitosa, entonces se retorna una tupla `(file_id, web_view_link)`.
- Y `file_id` es un string no vacío (ID de Google Drive).
- Y `web_view_link` es una URL válida que empieza con `https://drive.google.com/file/d/`.

### AC-6: Manejo de descripción vacía
- Cuando una oferta tiene `description=""`, entonces se genera de todas formas en el CSV con cadena vacía.
- Cuando una oferta tiene descripción muy larga (>2000 chars, recortada en el scraping), entonces se guarda el texto recortado sin error.

## Escenarios BDD

### Escenario 1: Generación de CSV válido
```gherkin
Given una lista de ofertas con título, empresa, ubicación, descripción, url y fecha
When llamo generate_csv(offers)
Then retorna un StringIO con encoding UTF-8-BOM
And el encabezado es "titulo,empresa,ubicacion,descripcion,url,fecha_extraccion"
And cada oferta ocupa una línea
```

### Escenario 2: Subida a Drive con folder_id
```gherkin
Given ofertas = 5 ofertas nuevas
And GDriveConfig con folder_id="1a2b3c4d5e"
When llamo upload_csv(offers, drive_service, config)
Then se crea un archivo en Google Drive
And el archivo tiene parents: ["1a2b3c4d5e"]
And el archivo se llama ofertas_YYYYMMDD_HHMMSS.csv
And se retorna (file_id, web_view_link)
```

### Escenario 3: Subida a raíz de Drive
```gherkin
Given ofertas = 3 ofertas nuevas
And GDriveConfig con folder_id=""
When llamo upload_csv(offers, drive_service, config)
Then se crea un archivo en Google Drive
And el archivo NO tiene campo parents en la metadata
And el archivo aparece en la raíz del Drive del usuario
```

### Escenario 4: Oferta con descripción vacía
```gherkin
Given ofertas donde la oferta 2 tiene description=""
When llamo generate_csv(offers)
Then la fila de la oferta 2 existe en el CSV
And la columna descripcion para la oferta 2 está vacía
```

### Escenario 5: BOM detectado por Excel
```gherkin
Given generate_csv retorna un StringIO con BOM UTF-8
When el usuario abre el archivo en Microsoft Excel
Then Excel detecta automáticamente UTF-8
And los caracteres especiales (á, é, ñ, ü) se muestran correctamente sin corromperse
```

## Detalles de implementación

### Generación de CSV en memoria

```python
import csv
import io
from datetime import datetime, timezone
from googleapiclient.http import MediaInMemoryUpload
from loguru import logger

def generate_csv(offers: list[dict]) -> io.StringIO:
    """
    Genera CSV en memoria con formato UTF-8 + BOM.
    Columnas: titulo, empresa, ubicacion, descripcion, url, fecha_extraccion
    """
    # UTF-8 con BOM (byte order mark) para compatibilidad con Excel/Sheets
    output = io.StringIO()
    output.write("\ufeff")  # BOM

    writer = csv.DictWriter(
        output,
        fieldnames=["titulo", "empresa", "ubicacion", "descripcion", "url", "fecha_extraccion"],
        extrasaction="ignore",  # Ignora claves adicionales en el dict
        quoting=csv.QUOTE_ALL,   # Entrecomillar todo para protección
    )
    writer.writeheader()
    for offer in offers:
        writer.writerow({
            "titulo": (offer.get("title", "") or "")[:300],
            "empresa": (offer.get("company", "") or "")[:200],
            "ubicacion": (offer.get("location", "") or "")[:200],
            "descripcion": (offer.get("description", "") or "")[:2000],
            "url": offer.get("url", ""),
            "fecha_extraccion": offer.get("scraped_at", datetime.now(timezone.utc).isoformat()),
        })

    output.seek(0)
    return output


def upload_csv(
    offers: list[dict],
    drive_service,
    config,
) -> tuple[str, str]:
    """
    Genera CSV y lo sube a Google Drive.

    Args:
        offers: lista de ofertas nuevas (ya deduplicadas)
        drive_service: servicio autenticado de Google Drive
        config: GDriveConfig

    Returns:
        (file_id, web_view_link)
    """
    # Generar CSV en memoria
    csv_content = generate_csv(offers)
    csv_bytes = csv_content.getvalue().encode("utf-8-sig")  # BOM en bytes

    # Timestamp
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{config.filename_prefix}_{ts}.csv"

    # Preparar metadata de archivo
    file_metadata = {
        "name": filename,
        "mimeType": "text/csv",
    }
    if config.folder_id:
        file_metadata["parents"] = [config.folder_id]

    # Crear upload desde memoria
    media = MediaInMemoryUpload(csv_bytes, mimetype="text/csv; charset=utf-8")

    logger.info(f"Subiendo {filename} a Google Drive... ({len(csv_bytes):,} bytes)")
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webViewLink,webContentLink",
    ).execute()

    file_id = file.get("id")
    web_view_link = file.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")

    logger.info(f"✅ Subido exitosamente: {filename}")
    logger.info(f"   file_id: {file_id}")
    logger.info(f"   URL: {web_view_link}")

    return file_id, web_view_link
```

### Flujo de subida

```
offers (nuevas, deduplicadas)
  └─ generate_csv()
       └─ StringIO con UTF-8-BOM + filas CSV
  └─ upload_csv()
       ├─ Generar filename con timestamp
       ├─ Preparar metadata (name, mimetype, parents opcional)
       ├─ MediaInMemoryUpload (sin archivo temporal en disco)
       └─ drive_service.files().create()
            └─ Retorna (file_id, web_view_link)
```

## Tareas derivadas (del plan de acción)

- Paso 8.1: Implementar generación de CSV en memoria
- Paso 8.2: Implementar subida a Google Drive
- Paso 8.3: Tests de uploader (mock)
