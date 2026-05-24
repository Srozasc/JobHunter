"""Tests de deduplicación de ofertas."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from jobhunter.dedup import (
    filter_new_offers,
    load_history,
    normalize_url,
    save_history,
)


# ── normalize_url ───────────────────────────────────────────────


class TestNormalizeUrl:
    def test_removes_query_params(self):
        """Remueve parámetros de tracking de la URL."""
        url = "https://www.linkedin.com/jobs/view/123?position=1&trk=public_jobs"
        assert normalize_url(url) == "https://www.linkedin.com/jobs/view/123"

    def test_removes_fragment(self):
        """Remueve fragment de la URL."""
        url = "https://www.linkedin.com/jobs/view/123#section"
        assert normalize_url(url) == "https://www.linkedin.com/jobs/view/123"

    def test_removes_trailing_slash(self):
        """Remueve trailing slash."""
        url = "https://www.linkedin.com/jobs/view/123/"
        assert normalize_url(url) == "https://www.linkedin.com/jobs/view/123"

    def test_empty_url(self):
        """URL vacía retorna vacío."""
        assert normalize_url("") == ""

    def test_clean_url_unchanged(self):
        """URL sin params se mantiene igual."""
        url = "https://www.linkedin.com/jobs/view/abc-123"
        assert normalize_url(url) == "https://www.linkedin.com/jobs/view/abc-123"

    def test_tracking_params_removed(self):
        """Parámetros de tracking comunes se remueven."""
        url = "https://linkedin.com/jobs/view/456?refId=abc123&trackingId=xyz"
        result = normalize_url(url)
        assert "?" not in result
        assert result == "https://linkedin.com/jobs/view/456"


# ── load_history ────────────────────────────────────────────────


class TestLoadHistory:
    def test_returns_dict_when_file_missing(self):
        """Si el archivo no existe, retorna dict vacío."""
        result = load_history("/tmp/no_existe_history.json")
        assert result == {}

    def test_loads_valid_json(self):
        """Carga historial válido desde disco."""
        data = {
            "https://linkedin.com/jobs/view/1": {
                "title": "Dev",
                "company": "Acme",
                "first_seen": "2026-01-01T00:00:00",
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = load_history(path)
            assert result == data
        finally:
            os.unlink(path)

    def test_returns_empty_on_invalid_json(self):
        """Si el JSON es inválido, retorna dict vacío."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{invalid json")
            path = f.name
        try:
            result = load_history(path)
            assert result == {}
        finally:
            os.unlink(path)


# ── save_history ────────────────────────────────────────────────


class TestSaveHistory:
    def test_creates_file(self):
        """Crea el archivo si no existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "history.json")
            save_history({"key": "value"}, path)
            assert os.path.exists(path)

    def test_writes_valid_json(self):
        """Escribe JSON válido y legible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            data = {
                "https://example.com": {
                    "title": "Test",
                    "first_seen": "2026-01-01",
                }
            }
            save_history(data, path)
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == data

    def test_creates_parent_directories(self):
        """Crea directorios padres si no existen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a", "b", "c", "history.json")
            save_history({"test": True}, path)
            assert os.path.exists(path)


# ── filter_new_offers ───────────────────────────────────────────


class TestFilterNewOffers:
    def _make_offer(self, url="https://linkedin.com/jobs/view/1", title="Dev"):
        return {
            "url": url,
            "title": title,
            "company": "Acme",
            "scraped_at": "2026-01-15T10:00:00+00:00",
        }

    def test_new_offer_included(self):
        """Oferta nueva se incluye en resultados."""
        offers = [self._make_offer()]
        new, history = filter_new_offers(offers, {})
        assert len(new) == 1
        assert "https://linkedin.com/jobs/view/1" in history

    def test_duplicate_filtered(self):
        """Oferta duplicada se filtra."""
        existing_url = "https://linkedin.com/jobs/view/1"
        history = {existing_url: {"title": "Dev", "first_seen": "2026-01-01"}}
        offers = [self._make_offer(url=existing_url)]
        new, _ = filter_new_offers(offers, history)
        assert len(new) == 0

    def test_mixed_new_and_duplicate(self):
        """Mezcla de ofertas nuevas y duplicadas."""
        history = {
            "https://linkedin.com/jobs/view/1": {
                "title": "Old",
                "first_seen": "2026-01-01",
            }
        }
        offers = [
            self._make_offer(url="https://linkedin.com/jobs/view/1"),
            self._make_offer(url="https://linkedin.com/jobs/view/2", title="New"),
        ]
        new, updated = filter_new_offers(offers, history)
        assert len(new) == 1
        assert new[0]["title"] == "New"
        assert "https://linkedin.com/jobs/view/2" in updated

    def test_empty_offers(self):
        """Lista vacía retorna vacío."""
        new, history = filter_new_offers([], {})
        assert new == []
        assert history == {}

    def test_offer_without_url_skipped(self):
        """Oferta sin URL se salta."""
        offers = [{"title": "No URL", "company": "Acme"}]
        new, _ = filter_new_offers(offers, {})
        assert len(new) == 0

    def test_tracking_params_normalized_for_dedup(self):
        """URLs con tracking params se deduplican correctamente."""
        history = {
            "https://linkedin.com/jobs/view/123": {
                "title": "Dev",
                "first_seen": "2026-01-01",
            }
        }
        # Misma oferta pero con params de tracking
        offers = [
            self._make_offer(
                url="https://linkedin.com/jobs/view/123?position=1&trk=abc"
            )
        ]
        new, _ = filter_new_offers(offers, history)
        assert len(new) == 0  # Debe detectarse como duplicada

    def test_saves_to_file_when_provided(self):
        """Guarda historial actualizado cuando se proporciona archivo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            offers = [self._make_offer()]
            filter_new_offers(offers, {}, history_file=path)
            assert os.path.exists(path)
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            assert "https://linkedin.com/jobs/view/1" in saved
