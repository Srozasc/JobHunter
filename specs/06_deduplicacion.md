# Spec: Deduplicación (dedup.py)

## Historia de usuario

Como usuario, quiero que JobHunter no vuelva a incluir ofertas que ya recolectó en ejecuciones anteriores, para que el CSV de Drive solo contenga ofertas nuevas.

## Asunciones acordadas

1. Historial como JSON: `{"url_normalizada": {"title": ..., "company": ..., "first_seen": "ISO_date"}, ...}`.
2. URL se normaliza removiendo parámetros de tracking (`position=`, `pageNum=`, `refId=`, `trackingId=`, `trk=`, etc.) manteniendo el path base.
3. Escritura atómica: escribe a `history.json.tmp` y renombra con `os.replace()`.
4. Si el archivo no existe, se crea desde cero sin error.
5. Comparación case-insensitive y slug-agnostic (URL con `/` final vs sin `/` se consideran iguales).

## Criterios de aceptación

### AC-1: Filtrado de duplicados
- Cuando el historial ya tiene URL "https://linkedin.com/jobs/view/12345", entonces una oferta nueva con `?position=1` se identifica como duplicada y se filtra.
- Cuando una oferta es nueva, entonces se incluye en el resultado.

### AC-2: Normalización de URLs
- Cuando dos URLs son equivalentes pero una tiene `?pageNum=2` y la otra tiene `?pageNum=3`, entonces se consideran IGUALES (ambas se normalizan al path base).
- Cuando una URL termina en `/` y la otra no, entonces se consideran IGUALES tras normalización.

### AC-3: Persistencia atómica
- Cuando el programa se interrumpe a mitad de guardado, entonces el archivo anterior no se corrompe (nunca escribe parcial).

### AC-4: Manejo de historial vacío o inexistente
- Cuando `history_file` no existe, entonces se crea nuevo sin error.
- Cuando el historial existe pero está vacío, entonces se interpreta como "sin ofertas previas" y todas las nuevas se incluyen.

### AC-5: Actualización del historial
- Cuando se añaden ofertas nuevas, entonces `save_history()` incluye URLs + metadata (title, company, first_seen) para cada entrada.
- Cuando una URL ya existía, entonces NO se modifica su entrada en el historial.

## Escenarios BDD

### Escenario 1: Filtrado de duplicado por tracking param
```gherkin
Given historial con "https://linkedin.com/jobs/view/12345"
When filter_new_offers recibe oferta con url "https://linkedin.com/jobs/view/12345?position=1"
Then la oferta NO aparece en la lista de nuevas
And se loguea debug "Oferta duplicada ignorada: ..."
```

### Escenario 2: Oferta nueva
```gherkin
Given historial con "https://linkedin.com/jobs/view/11111"
When filter_new_offers recibe oferta con url "https://linkedin.com/jobs/view/22222"
Then la oferta SÍ aparece en la lista de nuevas
And se agrega al historial actualizado
```

### Escenario 3: Normalización de URL con trailing slash
```gherkin
Given historial con "https://linkedin.com/jobs/view/12345" (sin slash)
When filter_new_offers recibe oferta con url "https://linkedin.com/jobs/view/12345/"
Then se consideran iguales y la oferta se filtra
```

### Escenario 4: Escritura atómica
```gherkin
Given historial con 2 ofertas
When save_history() se interrumpe por un kill signal DURANTE la escritura
Then el archivo de historial anterior (con 2 ofertas) se mantiene intacto
And no existe un archivo history.json.tmp residual
```

## Detalles de implementación

### Función de normalización

```python
from urllib.parse import urlparse, urlunparse, parse_qs
from pathlib import Path

def normalize_url(url: str) -> str:
    """Normaliza URL removiendo parámetros de tracking y normalizando el path."""
    parsed = urlparse(url)

    # Limpiar query params de tracking
    tracking_params = {"position", "pageNum", "refId", "trackingId", "trk", "ref", "src"}
    params = {k: v for k, v in parse_qs(parsed.query).items() if k.lower() not in tracking_params}
    clean_query = urlencode(params, doseq=True)

    # Normalizar path (remover trailing slash, case-insensitive)
    path = parsed.path.rstrip("/").lower()
    if path == "":
        path = "/"

    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        "",  # params (deprecated)
        clean_query,
        "",  # fragment
    ))
```

### Implementación de filtrado

```python
import json
from pathlib import Path

def load_history(path: str) -> dict:
    """Carga historial desde disco. Retorna dict vacío si no existe."""
    history_path = Path(path)
    if not history_path.exists():
        return {}
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning("Historial corrupto, iniciando desde cero.")
        return {}


def filter_new_offers(offers: list[dict], history: dict) -> tuple[list[dict], dict]:
    """
    Filtra ofertas nuevas comparando contra historial por URL normalizada.

    Returns:
        (nuevas_ofertas, historial_actualizado)
    """
    new_offers = []
    seen_urls = set(history.keys())

    for offer in offers:
        norm_url = normalize_url(offer.get("url", ""))
        if not norm_url:
            continue  # Sin URL = no procesar

        if norm_url not in seen_urls:
            # Guardar en historial con metadata mínima
            from datetime import datetime, timezone
            history[norm_url] = {
                "title": offer.get("title", ""),
                "company": offer.get("company", ""),
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
            seen_urls.add(norm_url)
            new_offers.append(offer)
        else:
            # Actualizar last_seen
            history[norm_url]["last_seen"] = datetime.now(timezone.utc).isoformat()

    logger.info(f"Deduplicación: {len(offers)} totales → {len(new_offers)} nuevas")
    return new_offers, history


def save_history(history: dict, path: str) -> None:
    """
    Guarda historial de forma atómica: escribe a archivo temporal y renombra.
    """
    history_path = Path(path)
    tmp_path = history_path.with_suffix(".json.tmp")

    # Asegurar que el directorio exista
    history_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, history_path)  # atómico en POSIX
    except Exception as e:
        # Cleanup temp file si hay error
        if tmp_path.exists():
            tmp_path.unlink()
        raise
```

## Tareas derivadas (del plan de acción)

- Paso 6.1: Implementar carga y guardado de historial
- Paso 6.2: Implementar filtrado de ofertas nuevas
- Paso 6.3: Tests de deduplicación
