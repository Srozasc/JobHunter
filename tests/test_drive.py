"""Tests de Google Drive uploader (con mocks)."""

import io
from unittest.mock import MagicMock

import pytest

from jobhunter.config import GDriveConfig
from jobhunter.drive.uploader import CSV_COLUMNS, generate_csv, upload_csv


# ── generate_csv ────────────────────────────────────────────────


class TestGenerateCsv:
    def _make_offer(self, **kwargs):
        """Helper para crear ofertas de prueba."""
        base = {
            "title": "Python Developer",
            "company": "Acme Corp",
            "location": "Santiago, Chile",
            "description": "Buscamos un desarrollador Python con experiencia en Django.",
            "url": "https://linkedin.com/jobs/view/123",
            "scraped_at": "2026-01-15T10:30:00+00:00",
        }
        base.update(kwargs)
        return base

    def test_header_columns(self):
        """El encabezado tiene las columnas correctas."""
        csv_content = generate_csv([])
        text = csv_content.read()
        lines = text.lstrip("\ufeff").strip().split("\r\n")
        header = lines[0]
        for col in CSV_COLUMNS:
            assert col in header

    def test_bom_present(self):
        """El CSV inicia con BOM UTF-8."""
        csv_content = generate_csv([])
        text = csv_content.read()
        assert text.startswith("\ufeff")

    def test_single_offer_row(self):
        """Una oferta genera una fila de datos."""
        offers = [self._make_offer()]
        csv_content = generate_csv(offers)
        text = csv_content.read().lstrip("\ufeff")
        lines = [l for l in text.strip().split("\r\n") if l]
        # Header + 1 fila
        assert len(lines) == 2
        assert "Python Developer" in lines[1]

    def test_multiple_offers(self):
        """Múltiples ofertas generan múltiples filas."""
        offers = [
            self._make_offer(title="Dev 1"),
            self._make_offer(title="Dev 2"),
            self._make_offer(title="Dev 3"),
        ]
        csv_content = generate_csv(offers)
        text = csv_content.read().lstrip("\ufeff")
        lines = [l for l in text.strip().split("\r\n") if l]
        assert len(lines) == 4  # header + 3 ofertas

    def test_empty_description(self):
        """Oferta con descripción vacía genera fila con campo vacío."""
        offers = [self._make_offer(description="")]
        csv_content = generate_csv(offers)
        text = csv_content.read().lstrip("\ufeff")
        lines = text.strip().split("\r\n")
        assert len(lines) == 2  # header + 1 fila

    def test_empty_offers_list(self):
        """Lista vacía genera CSV solo con encabezado."""
        csv_content = generate_csv([])
        text = csv_content.read().lstrip("\ufeff")
        lines = [l for l in text.strip().split("\r\n") if l]
        assert len(lines) == 1  # solo header

    def test_special_characters(self):
        """Caracteres especiales (tildes, eñes) se preservan."""
        offers = [self._make_offer(title="Desarrollador/a en Córdoba España")]
        csv_content = generate_csv(offers)
        text = csv_content.read()
        assert "Córdoba" in text

    def test_description_truncated(self):
        """Descripción >2000 chars se recorta."""
        long_desc = "A" * 3000
        offers = [self._make_offer(description=long_desc)]
        csv_content = generate_csv(offers)
        text = csv_content.read()
        # La descripción en el CSV no debe contener los 3000 chars
        assert "A" * 3000 not in text


# ── upload_csv ──────────────────────────────────────────────────


class TestUploadCsv:
    def _make_drive_service_mock(self):
        """Crea mock de Drive service que retorna file_id y webViewLink."""
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_create = MagicMock()
        mock_create.execute.return_value = {
            "id": "test_file_123",
            "webViewLink": "https://drive.google.com/file/d/test_file_123/view",
        }
        mock_service.files.return_value = mock_files
        mock_files.create.return_value = mock_create
        return mock_service

    def _make_config(self, folder_id=""):
        return GDriveConfig(folder_id=folder_id, filename_prefix="ofertas")

    def test_returns_file_id_and_link(self):
        """Retorna (file_id, web_view_link) tras subida exitosa."""
        offers = [{"title": "Dev", "company": "Acme", "url": "https://example.com"}]
        service = self._make_drive_service_mock()
        config = self._make_config()
        file_id, link = upload_csv(offers, service, config)
        assert file_id == "test_file_123"
        assert link.startswith("https://drive.google.com/file/d/")

    def test_with_folder_id(self):
        """Cuando folder_id está definido, se incluye en parents."""
        offers = [{"title": "Dev", "company": "Acme", "url": "https://example.com"}]
        service = self._make_drive_service_mock()
        config = self._make_config(folder_id="abc123")
        upload_csv(offers, service, config)
        # Verificar que se llamó con parents
        call_kwargs = service.files().create.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body", {})
        assert "parents" in body
        assert body["parents"] == ["abc123"]

    def test_without_folder_id(self):
        """Cuando folder_id está vacío, no se incluye parents."""
        offers = [{"title": "Dev", "company": "Acme", "url": "https://example.com"}]
        service = self._make_drive_service_mock()
        config = self._make_config(folder_id="")
        upload_csv(offers, service, config)
        call_kwargs = service.files().create.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body", {})
        assert "parents" not in body

    def test_filename_has_timestamp(self):
        """El nombre del archivo incluye timestamp."""
        offers = [{"title": "Dev", "company": "Acme", "url": "https://example.com"}]
        service = self._make_drive_service_mock()
        config = self._make_config()
        upload_csv(offers, service, config)
        call_kwargs = service.files().create.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body", {})
        filename = body.get("name", "")
        assert filename.startswith("ofertas_")
        assert filename.endswith(".csv")
        # Verificar formato timestamp (ofertas_YYYYMMDD_HHMMSS.csv)
        ts_part = filename.replace("ofertas_", "").replace(".csv", "")
        assert len(ts_part) == 15  # YYYYMMDD_HHMMSS

    def test_empty_offers_still_uploads(self):
        """Aunque no haya ofertas, se genera CSV con solo header y se sube."""
        offers = []
        service = self._make_drive_service_mock()
        config = self._make_config()
        file_id, link = upload_csv(offers, service, config)
        assert file_id == "test_file_123"
