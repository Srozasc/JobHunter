# Spec: Selectores DOM (linkedin/selectors.py)

## Historia de usuario

Como desarrollador, quiero tener todos los selectores CSS/XPath de LinkedIn Jobs centralizados en un archivo con fallbacks, para que cambios en la UI de LinkedIn no rompan el scraping de un solo golpe.

## Asunciones acordadas

1. Los selectores se organizan en un diccionario `SELECTORS` donde cada clave mapea a una lista de selectores CSS (ordenados por prioridad).
2. La función `find_element(page, key)` retorna el primer fallback que coincida, o lanza `ElementNotFoundError` si ninguno coincide.
3. Si todos los selectores fallan, se captura la excepción y se loguea un warning con los primeros 2000 chars del HTML para debug.
4. Los selectores cubren como mínimo: `job_card`, `title`, `company`, `location`, `url`, `description`, `next_page_btn`, `date_posted`.
5. Los selectores se prueban contra la versión actual de LinkedIn Jobs (mayo 2026) y se documentan con la fecha de última verificación.
6. Se incluye un script auxiliar `scripts/verify_selectors.py` que abre LinkedIn y verifica qué selectores funcionan (modo diagnóstico).

## Criterios de aceptación

### AC-1: Dicc organizado
- Cuando se lee `selectors.py`, entonces existe un diccionario `SELECTORS` con al menos las claves: `job_card`, `title`, `company`, `location`, `url`, `description`, `next_page_btn`, `date_posted`.

### AC-2: Fallbacks funcionan
- Cuando el primer selector de una clave no coincide con ningún elemento, entonces se intenta con el siguiente fallback automáticamente.
- Cuando al menos un fallback coincide, entonces se retorna ese elemento sin error.

### AC-3: Error descriptivo
- Cuando NINGÚN fallback coincide para una clave, entonces se lanza `ElementNotFoundError` con mensaje que incluye la clave, la lista de selectores intentados y la URL actual.
- Se loguea un warning con snippet del HTML (2000 chars) para facilitar debug.

### AC-4: Script de verificación
- Cuando se ejecuta `python scripts/verify_selectors.py`, entonces abre LinkedIn Jobs con sesión guardada e imprime un reporte de qué selectores funcionan y cuáles no.

### AC-5: Fecha de verificación
- Cuando se lee el header del archivo, entonces incluye un comentario con la fecha de última verificación contra la UI real de LinkedIn.

## Escenarios BDD

### Escenario 1: Selector con primer fallback válido
```gherkin
Given LinkedIn Jobs cargado con resultados
And el primer selector de "job_card" coincide
When llamo find_element(page, "job_card")
Then retorna lista de elementos sin intentar fallbacks adicionales
```

### Escenario 2: Selector con segundo fallback válido
```gherkin
Given LinkedIn Jobs cargado con resultados
And el primer selector de "job_card" NO coincide
And el segundo selector de "job_card" coincide
When llamo find_element(page, "job_card")
Then retorna lista de elementos
And se loguea debug "Usando fallback 2 para job_card"
```

### Escenario 3: Todos los selectores fallan
```gherkin
Given LinkedIn Jobs cargado
And ningún selector de "title" coincide
When llamo find_element(page, "title")
Then se lanza ElementNotFoundError
And el mensaje incluye la clave "title"
And el mensaje incluye la lista de selectores intentados
And se loguea warning con HTML snippet
```

### Escenario 4: Script de verificación
```gherkin
Given sesión válida de LinkedIn guardada
When ejecuto python scripts/verify_selectors.py
Then imprime reporte por cada clave de SELECTORS
And cada clave muestra: selector probado | ✅ o ❌ | # elementos encontrados
```

## Detalles de implementación

### Selectores (mayo 2026)

```python
# Última verificación contra UI de LinkedIn: mayo 2026
# Si LinkedIn cambia su UI, actualizar este archivo y la fecha anterior.

SELECTORS = {
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
```

### Implementación

```python
from loguru import logger

class ElementNotFoundError(Exception):
    def __init__(self, key, selectors_tried, url):
        self.key = key
        self.selectors_tried = selectors_tried
        self.url = url
        msg = (
            f"No se encontró ningún elemento para '{key}'.\n"
            f"Selectores intentados: {selectors_tried}\n"
            f"URL actual: {url}"
        )
        super().__init__(msg)


async def find_elements(page, key: str) -> list:
    """Intenta cada fallback de selectores para una clave hasta encontrar uno válido."""
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    if key not in SELECTORS:
        raise KeyError(f"Clave de selector desconocida: {key}")

    selectors = SELECTORS[key]
    for i, selector in enumerate(selectors):
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                if i > 0:
                    logger.debug(f"Usando fallback {i+1} para '{key}': {selector}")
                return elements
        except Exception:
            continue

    # Ningún selector funcionó — log HTML snippet para debug
    html_snippet = (await page.content())[:2000]
    logger.warning(
        f"Todos los selectores fallaron para '{key}'.\n"
        f"URL: {page.url}\n"
        f"HTML snippet:\n{html_snippet}"
    )
    raise ElementNotFoundError(key, selectors, page.url)


async def find_element(page, key: str):
    """Retorna el primer elemento encontrado para una clave."""
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
    return await element.get_attribute(attr) or ""
```

### Script de verificación (`scripts/verify_selectors.py`)

```python
"""Verifica selectores DOM contra LinkedIn Jobs en tiempo real."""
import asyncio
from playwright.async_api import async_playwright
from jobhunter.linkedin.selectors import SELECTORS, find_elements

async def verify():
    session_file = "data/session/linkedin_session.json"
    search_url = "https://www.jobs.linkedin.com/jobs/search/?keywords=python&location=Chile"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state=session_file)
        page = await ctx.new_page()
        await page.goto(search_url, wait_until="networkidle", timeout=30000)

        print("=" * 60)
        print("VERIFICACIÓN DE SELECTORES — LinkedIn Jobs")
        print(f"URL: {search_url}")
        print("=" * 60)

        for key, selectors in SELECTORS.items():
            found = False
            for sel in selectors:
                elements = await page.query_selector_all(sel)
                status = "✅" if elements else "❌"
                count = len(elements)
                print(f"  {key:20s} | {status} ({count:3d}) | {sel}")
                if elements:
                    found = True
                    break
            if not found:
                print(f"  {key:20s} | ❌ NINGÚN SELECTOR FUNCIONA")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify())
```

## Tareas derivadas (del plan de acción)

- Paso 4.1: Definir selectores con fallbacks
