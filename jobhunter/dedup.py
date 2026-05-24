"""Deduplicación de ofertas contra historial local."""

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from loguru import logger


def normalize_url(url: str) -> str:
    """Normaliza URL removiendo parámetros de tracking.

    - Mantiene scheme, netloc, path.
    - Remueve query params y fragment.
    - Remueve trailing slash.
    """
    if not url:
        return ""
    parsed = urlparse(url)
    # Reconstruir sin query ni fragment
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    # Remover trailing slash
    return clean.rstrip("/")


def load_history(path: str) -> dict:
    """Carga historial desde archivo JSON. Retorna dict vacío si no existe."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning(f"Historial en {path} no es un dict, reiniciando.")
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Error leyendo historial en {path}: {e}. Reiniciando.")
        return {}


def save_history(history: dict, path: str) -> None:
    """Guarda historial en JSON con escritura atómica (temp + rename)."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Escritura atómica
    fd, tmp_path = tempfile.mkstemp(
        dir=str(file_path.parent),
        prefix=".history_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(file_path))
    except Exception:
        # Limpiar temp file en caso de error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def filter_new_offers(
    offers: list[dict],
    history: dict,
    history_file: str = "",
) -> tuple[list[dict], dict]:
    """Filtra ofertas que ya existen en el historial.

    Retorna (nuevas_ofertas, historial_actualizado).
    """
    new_offers: list[dict] = []
    for offer in offers:
        url = normalize_url(offer.get("url", ""))
        if not url:
            continue
        if url in history:
            logger.debug(f"Oferta duplicada: {url}")
            continue
        new_offers.append(offer)
        # Agregar al historial
        history[url] = {
            "title": offer.get("title", ""),
            "company": offer.get("company", ""),
            "first_seen": offer.get("scraped_at", ""),
        }

    logger.info(
        f"Dedup: {len(offers)} recibidas, {len(new_offers)} nuevas, "
        f"{len(offers) - len(new_offers)} duplicadas."
    )

    # Guardar historial actualizado si hay file
    if history_file and new_offers:
        save_history(history, history_file)

    return new_offers, history
