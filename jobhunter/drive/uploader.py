"""Generación de CSV y subida a Google Drive."""

import csv
import io
from datetime import datetime, timezone

from googleapiclient.http import MediaInMemoryUpload
from loguru import logger


CSV_COLUMNS = [
    "titulo",
    "empresa",
    "ubicacion",
    "descripcion",
    "url",
    "fecha_extraccion",
]


def generate_csv(offers: list[dict]) -> io.StringIO:
    """Genera CSV en memoria con codificación UTF-8 + BOM.

    Columnas: titulo, empresa, ubicacion, descripcion, url, fecha_extraccion
    """
    output = io.StringIO()
    output.write("\ufeff")  # BOM para Excel/Sheets

    writer = csv.DictWriter(
        output,
        fieldnames=CSV_COLUMNS,
        extrasaction="ignore",
        quoting=csv.QUOTE_ALL,
    )
    writer.writeheader()
    for offer in offers:
        writer.writerow({
            "titulo": (offer.get("title", "") or "")[:300],
            "empresa": (offer.get("company", "") or "")[:200],
            "ubicacion": (offer.get("location", "") or "")[:200],
            "descripcion": (offer.get("description", "") or "")[:2000],
            "url": offer.get("url", ""),
            "fecha_extraccion": offer.get(
                "scraped_at", datetime.now(timezone.utc).isoformat()
            ),
        })

    output.seek(0)
    return output


def upload_csv(
    offers: list[dict],
    drive_service,
    config,
) -> tuple[str, str]:
    """Genera CSV y lo sube a Google Drive.

    Retorna (file_id, web_view_link).
    """
    csv_content = generate_csv(offers)
    csv_bytes = csv_content.getvalue().encode("utf-8-sig")  # BOM en bytes

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{config.filename_prefix}_{ts}.csv"

    file_metadata: dict = {
        "name": filename,
        "mimeType": "text/csv",
    }
    if config.folder_id:
        file_metadata["parents"] = [config.folder_id]

    media = MediaInMemoryUpload(csv_bytes, mimetype="text/csv; charset=utf-8")

    logger.info(
        f"Subiendo {filename} a Google Drive... ({len(csv_bytes):,} bytes)"
    )
    file = (
        drive_service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id,webViewLink,webContentLink",
        )
        .execute()
    )

    file_id = file.get("id", "")
    web_view_link = file.get(
        "webViewLink", f"https://drive.google.com/file/d/{file_id}/view"
    )

    logger.info(f"✅ Subido exitosamente: {filename}")
    logger.info(f"   file_id: {file_id}")
    logger.info(f"   URL: {web_view_link}")

    return file_id, web_view_link
