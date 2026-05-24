"""Selectores DOM para LinkedIn Jobs con sistema de fallbacks.

Última verificación contra UI de LinkedIn: mayo 2026
Si LinkedIn cambia su UI, actualizar este archivo y la fecha anterior.
"""

from loguru import logger

# ── Diccionario de selectores ──────────────────────────────────

SELECTORS: dict[str, list[str]] = {
    "job_card": [
        "div.job-card-container",
        "li.jobs-search-results__list-item",
        "div.base-card[data-entity-urn]",
        "div.job-search-card",
    ],
    "title": [
        "a.job-card-list__title span[aria-hidden='true']",
        "h3.base-search-card__title",
        "a.job-card-container__link span[aria-hidden='true']",
        "div.job-card-list__title",
    ],
    "company": [
        "a.job-card-container__company-name",
        "h4.base-search-card__subtitle a",
        "span.job-card-container__primary-description",
        "div.job-card-container__company-wrapper a",
    ],
    "location": [
        "span.job-card-container__metadata-item",
        "span.job-search-card__location",
        "div.job-card-container__metadata-wrapper span",
    ],
    "url": [
        "a.job-card-list__title",
        "a.base-card__full-link",
        "a.job-card-container__link",
    ],
    "date_posted": [
        "time.job-search-card__listdate",
        "span.job-search-card__listdate",
        "time[datetime]",
    ],
    "description": [
        "div.jobs-description__content",
        "div.jobs-box__html-content",
        "div.job-details-JobsDescription__content",
        "article.jobs-description",
    ],
    "next_page_btn": [
        "button[aria-label='Next']",
        "button.artdeco-pagination__button--next",
        "button[aria-label='Siguiente']",
    ],
}


# ── Excepción personalizada ────────────────────────────────────


class ElementNotFoundError(Exception):
    """Ningún selector fallback encontró un elemento."""

    def __init__(self, key: str, selectors_tried: list[str], url: str):
        self.key = key
        self.selectors_tried = selectors_tried
        self.url = url
        msg = (
            f"No se encontró ningún elemento para '{key}'.\n"
            f"Selectores intentados: {selectors_tried}\n"
            f"URL actual: {url}"
        )
        super().__init__(msg)


# ── Funciones públicas ─────────────────────────────────────────


async def find_elements(page, key: str) -> list:
    """Intenta cada fallback de selectores hasta encontrar uno válido.

    Retorna lista de elementos encontrados.
    Lanza ElementNotFoundError si ningún fallback coincide.
    """
    if key not in SELECTORS:
        raise KeyError(f"Clave de selector desconocida: {key}")

    selectors = SELECTORS[key]
    for i, selector in enumerate(selectors):
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                if i > 0:
                    logger.debug(f"Usando fallback {i + 1} para '{key}': {selector}")
                return elements
        except Exception:
            continue

    # Ningún selector funcionó — log HTML snippet para debug
    html_snippet = ""
    try:
        html_snippet = (await page.content())[:2000]
    except Exception:
        pass
    logger.warning(
        f"Todos los selectores fallaron para '{key}'.\n"
        f"URL: {page.url}\n"
        f"HTML snippet:\n{html_snippet}"
    )
    raise ElementNotFoundError(key, selectors, page.url)


async def find_element(page, key: str):
    """Retorna el primer elemento encontrado para una clave, o None."""
    elements = await find_elements(page, key)
    return elements[0] if elements else None


async def get_text(element) -> str:
    """Extrae texto limpio de un elemento."""
    if element is None:
        return ""
    text = await element.text_content()
    return text.strip() if text else ""


async def get_attribute(element, attr: str) -> str:
    """Extrae atributo de un elemento."""
    if element is None:
        return ""
    return (await element.get_attribute(attr)) or ""
