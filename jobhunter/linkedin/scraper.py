"""Scraping de ofertas desde LinkedIn Jobs."""

import asyncio
import random
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlencode

from loguru import logger

from jobhunter.config import SearchConfig

# ── Mapeo de filtros a parámetros URL ──────────────────────────

DATE_POSTED_MAP = {
    "past_24h": "r86400",
    "past_week": "r604800",
    "past_month": "r2592000",
}

EXPERIENCE_MAP = {
    "entry": "1",
    "associate": "2",
    "mid_senior": "3",
    "director": "4",
    "executive": "5",
}

JOB_TYPE_MAP = {
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "temporary": "T",
    "internship": "I",
}

REMOTE_MAP = {
    1: "1",   # On-site
    2: "2",   # Remote
    3: "3",   # Hybrid
}


# ── Construcción de URL ────────────────────────────────────────


def build_search_url(search: SearchConfig) -> str:
    """Construye la URL de LinkedIn Jobs desde SearchConfig."""
    base = "https://www.linkedin.com/jobs/search/"
    params: dict[str, str] = {
        "keywords": search.keywords,
        "location": search.location,
    }

    # Filtro fecha de publicación
    if search.date_posted:
        date_val = DATE_POSTED_MAP.get(search.date_posted.value, "")
        if date_val:
            params["f_TPR"] = date_val

    # Filtro nivel de experiencia
    if search.experience_level:
        params["f_E"] = ",".join(
            EXPERIENCE_MAP.get(exp.value, "") for exp in search.experience_level
        )

    # Filtro tipo de empleo
    if search.job_type:
        params["f_JT"] = ",".join(
            JOB_TYPE_MAP.get(jt.value, "") for jt in search.job_type
        )

    # Filtro remoto
    if search.remote:
        params["f_WT"] = "2"

    # Ordenamiento
    params["sortBy"] = "DD" if search.sort_by.value == "recent" else "R"

    # Remover params vacíos
    params = {k: v for k, v in params.items() if v}

    return f"{base}?{urlencode(params, quote_via=quote_plus)}"


# ── Scraping principal ─────────────────────────────────────────


async def scrape_offers(ctx, search: SearchConfig) -> list[dict]:
    """Scraping completo de ofertas desde LinkedIn Jobs.

    Retorna lista de dicts con: id, title, company, location, url,
    description, date_posted, scraped_at.
    """
    from jobhunter.linkedin.selectors import find_elements, SELECTORS

    url = build_search_url(search)
    logger.info(f"Iniciando scraping: {url}")

    page = await ctx.new_page()
    offers: list[dict] = []
    page_num = 0

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except asyncio.TimeoutError:
        logger.error(f"Timeout cargando la primera página: {url}")
        await page.close()
        return []

    while len(offers) < search.max_results:
        page_num += 1
        logger.info(f"Procesando página {page_num}...")

        # Esperar job cards
        try:
            cards = await find_elements(page, "job_card")
        except Exception as e:
            logger.warning(f"No se encontraron job cards en página {page_num}: {e}")
            break

        logger.info(f"  {len(cards)} ofertas encontradas en página {page_num}")

        for card in cards:
            if len(offers) >= search.max_results:
                break
            offer = await _extract_offer_data(ctx, card)
            if offer["url"]:  # Solo incluir si tiene URL
                offers.append(offer)

        # Paginación
        if not await _go_to_next_page(page):
            logger.info("No hay más páginas de resultados.")
            break

        # Rate limiting entre páginas
        delay = random.uniform(1.5, 3.5)
        logger.debug(f"Rate limit: esperando {delay:.1f}s")
        await asyncio.sleep(delay)

    await page.close()
    logger.info(f"Scraping completo: {len(offers)} ofertas en {page_num} páginas.")
    return offers


# ── Extracción de datos ────────────────────────────────────────


async def _extract_offer_data(ctx, card) -> dict:
    """Extrae datos de un job card del listado."""
    title = (await _safe_text(card, "title"))[:300]
    company = (await _safe_text(card, "company"))[:200]
    location = (await _safe_text(card, "location"))[:200]
    url = await _safe_attr(card, "url", "href") or ""
    dt_attr = await _safe_attr(card, "date_posted", "datetime")
    date_posted = dt_attr or (await _safe_text(card, "date_posted"))[:50]

    # Extraer descripción navegando al detalle
    description = ""
    if url:
        description = await _extract_description(ctx, url)

    # Normalizar URL como ID
    offer_id = url.split("?")[0] if url else ""

    return {
        "id": offer_id,
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "description": description[:2000],
        "date_posted": date_posted,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


async def _safe_text(parent, key: str) -> str:
    """Extrae texto del primer elemento que coincida con selectores de key."""
    from jobhunter.linkedin.selectors import SELECTORS

    for selector in SELECTORS.get(key, []):
        el = await parent.query_selector(selector)
        if el:
            text = await el.text_content()
            if text and text.strip():
                return text.strip()
    return ""


async def _safe_attr(parent, key: str, attr: str) -> str:
    """Extrae atributo del primer elemento que coincida con selectores de key."""
    from jobhunter.linkedin.selectors import SELECTORS

    for selector in SELECTORS.get(key, []):
        el = await parent.query_selector(selector)
        if el:
            val = await el.get_attribute(attr)
            if val and val.strip():
                return val.strip()
    return ""


# ── Extracción de descripción ──────────────────────────────────


async def _extract_description(ctx, url: str) -> str:
    """Navega a la página de detalle de una oferta y extrae la descripción."""
    from jobhunter.linkedin.selectors import SELECTORS

    # Rate limit antes de navegar al detalle
    await asyncio.sleep(random.uniform(2.0, 4.0))

    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        for selector in SELECTORS.get("description", []):
            el = await page.query_selector(selector)
            if el:
                text = await el.text_content()
                if text and len(text.strip()) > 50:
                    return text.strip()[:2000]
        return ""
    except asyncio.TimeoutError:
        logger.debug(f"Timeout extrayendo descripción: {url}")
        return ""
    except Exception as e:
        logger.debug(f"Error extrayendo descripción: {url} — {e}")
        return ""
    finally:
        await page.close()


# ── Paginación ─────────────────────────────────────────────────


async def _go_to_next_page(page) -> bool:
    """Intenta avanzar a la siguiente página. Retorna True si lo logró."""
    from jobhunter.linkedin.selectors import SELECTORS

    for selector in SELECTORS.get("next_page_btn", []):
        btn = await page.query_selector(selector)
        if btn:
            is_disabled = await btn.get_attribute("disabled")
            if is_disabled:
                return False
            await btn.click()
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
                return True
            except asyncio.TimeoutError:
                logger.warning("Timeout esperando siguiente página")
                return False
    return False
