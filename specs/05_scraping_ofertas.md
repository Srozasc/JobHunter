# Spec: Scraping de Ofertas (linkedin/scraper.py)

## Historia de usuario

Como usuario, quiero que JobHunter navegue automáticamente a LinkedIn Jobs con mis filtros configurados, recorra todas las páginas de resultados y extraiga título, empresa, ubicación, descripción y URL de cada oferta, para obtener un dataset completo de oportunidades laborales.

## Asunciones acordadas

1. La URL de búsqueda se construye dinámicamente desde `SearchConfig` con parámetros de filtro (`f_TPR`, `f_E`, `f_JT`, `f_WT`).
2. La descripción se extrae navegando a la URL de cada oferta individual (no del listado).
3. Rate limiting: pausa aleatoria 1.5–3.5s entre páginas, 2.0–4.0s antes de navegar al detalle de cada oferta.
4. Timeout por página de resultados: 30s. Si timeout → log warning → continuar.
5. Se detiene al alcanzar `max_results` o al no haber más páginas.
6. Cada oferta es un dict con: `id`, `title`, `company`, `location`, `url`, `description`, `date_posted`, `scraped_at`.

## Criterios de aceptación

### AC-1: URL de búsqueda correcta
- Cuando `SearchConfig` tiene `keywords="python"`, `location="Chile"`, entonces la URL generada contiene `keywords=python` y `location=Chile`.
- Cuando hay filtros adicionales (`date_posted`, `experience_level`, `job_type`), entonces los parámetros `f_TPR`, `f_E`, `f_JT` están presentes.

### AC-2: Extracción completa por oferta
- Cuando una página de resultados tiene N job cards, entonces se extraen N ofertas con `title`, `company`, `location`, `url`, `date_posted`.
- Cuando se navega al detalle de una oferta, entonces `description` contiene el texto completo de la descripción.

### AC-3: Paginación
- Cuando hay más resultados en la siguiente página, entonces el scraper avanza a la siguiente página automáticamente.
- Cuando no hay más páginas, entonces el scraping termina con un log "No hay más páginas".

### AC-4: Límite de resultados
- Cuando `max_results=50` y hay 200 ofertas disponibles, entonces se extraen exactamente 50.

### AC-5: Rate limiting
- Cuando el scraper pagina entre resultados, entonces hay una pausa de 1.5–3.5s entre cada página.
- Cuando el scraper navega al detalle de una oferta, entonces hay una pausa de 2.0–4.0s antes de navegar.

### AC-6: Manejo de errores
- Cuando una página da timeout (30s), entonces se loguea warning y se continúa con la siguiente.
- Cuando una oferta individual falla al extraer descripción, entonces se incluye con `description=""` y se loguea debug.

### AC-7: Output estructurado
- Cuando el scraping termina, entonces retorna `list[dict]` donde cada dict tiene las claves: `id`, `title`, `company`, `location`, `url`, `description`, `date_posted`, `scraped_at`.

## Escenarios BDD

### Escenario 1: Scraping completo con paginación
```gherkin
Given sesión válida de LinkedIn
And SearchConfig con keywords="python", location="Chile", max_results=50
When llamo scrape_offers(ctx, search_config)
Then retorna lista de hasta 50 ofertas
And cada oferta tiene title, company, location, url, description
And se logueó el número de páginas procesadas
```

### Escenario 2: Construcción de URL con filtros
```gherkin
Given SearchConfig:
  keywords = "data scientist"
  location = "Spain"
  experience_level = ["mid_senior"]
  date_posted = "past_week"
  job_type = ["full_time"]
When llamo _build_search_url(config)
Then la URL contiene "keywords=data+scientist"
And la URL contiene "location=Spain"
And la URL contiene "f_TPR=r604800"
And la URL contiene "f_E=3"
And la URL contiene "f_JT=F"
```

### Escenario 3: Timeout en página
```gherkin
Given sesión válida
And página de resultados que no carga en 30s
When scrape_offers procesa esa página
Then se loguea warning "Timeout en página X"
And el scraper continúa con la siguiente página
And las ofertas de páginas exitosas se incluyen en el resultado
```

### Escenario 4: Descripción vacía por error
```gherkin
Given sesión válida
And una oferta cuya página de detalle falla
When scrape_offers procesa esa oferta
Then la oferta se incluye con description=""
And se loguea debug indicando la URL que falló
```

### Escenario 5: Última página
```gherkin
Given sesión válida
And última página de resultados (no hay botón "Next")
When scrape_offers intenta avanzar
Then detecta que no hay siguiente página
And loguea "No hay más páginas"
And retorna ofertas acumuladas
```

## Detalles de implementación

### Mapeo de filtros a parámetros URL

```python
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
```

### Funciones auxiliares de URL

```python
from urllib.parse import urlencode, quote_plus

def _build_search_url(search) -> str:
    base = "https://www.linkedin.com/jobs/search/"
    params = {
        "keywords": search.keywords,
        "location": search.location,
        "f_TPR": DATE_POSTED_MAP.get(search.date_posted.value, ""),
        "f_JT": ",".join(JOB_TYPE_MAP[j.value] for j in search.job_type),
        "f_E": ",".for exp in search.experience_level),
        "f_WT": "2" if search.remote else "",
    }
    # Remover params vacíos
    params = {k: v for k, v in params.items() if v}
    return f"{base}?{urlencode(params, quote_via=quote_plus)}"
```

### Flujo principal de scraping

```python
import asyncio
import random
from datetime import datetime, timezone
from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeout
from jobhunter.linkedin.selectors import find_elements, get_text, get_attribute

async def scrape_offers(ctx, search) -> list[dict]:
    """Scraping completo de ofertas desde LinkedIn Jobs."""
    url = _build_search_url(search)
    logger.info(f"Iniciando scraping: {url}")

    page = await ctx.new_page()
    offers = []
    page_num = 0

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except PlaywrightTimeout:
        logger.error("Timeout cargando la primera página.")
        await page.close()
        return []

    while len(offers) < search.max_results:
        page_num += 1
        logger.info(f"Procesando página {page_num}...")

        try:
            cards = await find_elements(page, "job_card")
        except Exception as e:
            logger.warning(f"No se encontraron job cards en página {page_num}: {e}")
            break

        logger.info(f"  {len(cards)} ofertas encontradas en página {page_num}")

        for card in cards:
            if len(offers) >= search.max_results:
                break
            offer = await _extract_offer_data(page, card)
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
```

### Extracción de datos de una oferta

```python
async def _extract_offer_data(page, card) -> dict:
    """Extrae datos básicos de un job card del listado."""
    title_el = await card.query_selector(SELECTORS["title"][0]) if False else None
    # Usar selectores del módulo selectors
    from jobhunter.linkedin.selectors import find_elements

    offers = []  # placeholder

    title = (await _safe_text(card, "title"))[:300]
    company = (await _safe_text(card, "company"))[:200]
    location = (await _safe_text(card, "location"))[:200]
    url = await _safe_attr(card, "url", "href") or ""
    date_posted = await _safe_attr(card, "date_posted", "datetime") or \
                  (await _safe_text(card, "date_posted"))[:50]

    # Extraer descripción navegando al detalle
    description = ""
    if url:
        description = await _extract_description(page.context, url)

    return {
        "id": url.split("?")[0] if url else "",
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
            if text:
                return text.strip()
    return ""


async def _safe_attr(parent, key: str, attr: str) -> str:
    """Extrae atributo del primer elemento que coincida."""
    from jobhunter.linkedin.selectors import SELECTORS
    for selector in SELECTORS.get(key, []):
        el = await parent.query_selector(selector)
        if el:
            val = await el.get_attribute(attr)
            if val:
                return val.strip()
    return ""
```

### Extracción de descripción

```python
async def _extract_description(ctx, url: str) -> str:
    """Navega a la página de detalle de una oferta y extrae la descripción."""
    import random
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    # Rate limit antes de navegar al detalle
    await asyncio.sleep(random.uniform(2.0, 4.0))

    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        from jobhunter.linkedin.selectors import SELECTORS
        for selector in SELECTORS.get("description", []):
            el = await page.query_selector(selector)
            if el:
                text = await el.text_content()
                if text and len(text) > 50:  # Descripción mínima viable
                    return text.strip()[:2000]
        return ""
    except PlaywrightTimeout:
        logger.debug(f"Timeout extrayendo descripción: {url}")
        return ""
    except Exception as e:
        logger.debug(f"Error extrayendo descripción: {url} — {e}")
        return ""
    finally:
        await page.close()
```

### Paginación

```python
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
            except PlaywrightTimeout:
                logger.warning("Timeout esperando siguiente página")
                return False
    return False
```

## Tareas derivadas (del plan de acción)

- Paso 5.1: Construir URL de búsqueda desde configuración
- Paso 5.2: Implementar extracción de ofertas por página
- Paso 5.3: Implementar extracción de descripción
- Paso 5.4: Implementar paginación y flujo principal
- Paso 5.5: Tests de scraping (mock)
