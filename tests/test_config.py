"""Tests de configuración y validación de config.yaml."""

import pytest
from pydantic import ValidationError

from jobhunter.config import (
    AppConfig,
    DatePosted,
    ExperienceLevel,
    GDriveConfig,
    JobType,
    LinkedInConfig,
    ScheduleConfig,
    SearchConfig,
    SortBy,
    load_config,
)


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def minimal_yaml(tmp_path):
    """Crea un config.yaml mínimo válido."""
    content = """
search:
  keywords: "python developer"
"""
    path = tmp_path / "config.yaml"
    path.write_text(content)
    return path


@pytest.fixture
def full_yaml(tmp_path):
    """Crea un config.yaml completo con todas las secciones."""
    content = """
linkedin:
  session_file: data/session/linkedin_session.json
  headless: true

search:
  keywords: "python developer"
  location: "Chile"
  experience_level: ["associate", "mid_senior"]
  date_posted: "past_week"
  job_type: ["full_time"]
  remote: false
  max_results: 150
  sort_by: "relevant"

schedule:
  enabled: true
  frequency: "weekly"
  every_hours: 48
  hour: "08:00"

google_drive:
  credentials_file: "credentials.json"
  token_file: "token.json"
  folder_id: "abc123"
  filename_prefix: "ofertas_test"

dedup:
  history_file: data/history/test_history.json
"""
    path = tmp_path / "config.yaml"
    path.write_text(content)
    return path


# ── Escenario 1: Carga exitosa ─────────────────────────────────


class TestLoadConfigSuccess:
    def test_minimal_config_loads(self, minimal_yaml):
        """Un config.yaml mínimo con solo keywords carga sin errors."""
        cfg = load_config(str(minimal_yaml))
        assert isinstance(cfg, AppConfig)

    def test_full_config_fields(self, full_yaml):
        """Todos los campos del config completo se parsean correctamente."""
        cfg = load_config(str(full_yaml))
        assert cfg.search.keywords == "python developer"
        assert cfg.search.location == "Chile"
        assert cfg.search.max_results == 150
        assert cfg.search.sort_by == SortBy.relevant
        assert cfg.schedule.frequency == "weekly"
        assert cfg.schedule.every_hours == 48
        assert cfg.google_drive.folder_id == "abc123"
        assert cfg.dedup.history_file == "data/history/test_history.json"


# ── Escenario 2: Archivo inexistente ───────────────────────────


class TestLoadConfigMissingFile:
    def test_missing_file_exits(self, tmp_path):
        """Si config.yaml no existe, se lanza SystemExit con mensaje accionable."""
        with pytest.raises(SystemExit):
            load_config(str(tmp_path / "no_existe.yaml"))


# ── Escenario 3: Campo inválido ────────────────────────────────


class TestLoadConfigInvalidField:
    def test_invalid_frequency(self, tmp_path):
        """Un valor inválido en frequency muestra warning pero no rompe.
        La validación estricta se aplica a every_hours (ge=1, le=720)."""
        content = """
search:
  keywords: python developer
schedule:
  frequency: "cada_rato"
"""
        path = tmp_path / "config.yaml"
        path.write_text(content)
        # frequency es un string libre para permitir "every_Xh"; no causa error
        cfg = load_config(str(path))
        assert cfg.schedule.frequency == "cada_rato"

    def test_every_hours_ge_1(self):
        """every_hours debe ser >= 1."""
        with pytest.raises(ValidationError):
            ScheduleConfig(every_hours=0)

    def test_every_hours_le_720(self):
        """every_hours debe ser <= 720."""
        with pytest.raises(ValidationError):
            ScheduleConfig(every_hours=721)
        """max_results debe ser >= 1."""
        with pytest.raises(ValidationError):
            SearchConfig(keywords="test", max_results=0)

    def test_max_results_le_500(self):
        """max_results debe ser <= 500."""
        with pytest.raises(ValidationError):
            SearchConfig(keywords="test", max_results=501)


# ── Escenario 4: Valores por defecto ───────────────────────────


class TestLoadConfigDefaults:
    def test_default_max_results(self, minimal_yaml):
        """max_results por defecto es 100."""
        cfg = load_config(str(minimal_yaml))
        assert cfg.search.max_results == 100

    def test_default_schedule_enabled(self, minimal_yaml):
        """schedule.enabled por defecto es true."""
        cfg = load_config(str(minimal_yaml))
        assert cfg.schedule.enabled is True

    def test_default_history_file(self, minimal_yaml):
        """history_file por defecto apunta a data/history/offers_history.json."""
        cfg = load_config(str(minimal_yaml))
        assert cfg.dedup.history_file == "data/history/offers_history.json"

    def test_default_headless(self, minimal_yaml):
        """linkedin.headless por defecto es true."""
        cfg = load_config(str(minimal_yaml))
        assert cfg.linkedin.headless is True

    def test_default_sort_by(self, minimal_yaml):
        """sort_by por defecto es 'recent'."""
        cfg = load_config(str(minimal_yaml))
        assert cfg.search.sort_by == SortBy.recent


# ── Escenario 5: Modelos individuales ─────────────────────────


class TestModelValidation:
    def test_experience_level_enum(self, tmp_path):
        """Los experience_level inválidos son rechazados."""
        content = """
search:
  keywords: test
  experience_level: ["nivel_inexistente"]
"""
        path = tmp_path / "config.yaml"
        path.write_text(content)
        with pytest.raises(SystemExit):
            load_config(str(path))

    def test_job_type_enum(self):
        """JobType acepta solo valores válidos."""
        cfg = SearchConfig(keywords="test", job_type=[JobType.full_time, JobType.contract])
        assert len(cfg.job_type) == 2

    def test_invalid_sort_by(self):
        """sort_by inválido lanza ValidationError."""
        with pytest.raises(ValidationError):
            SearchConfig(keywords="test", sort_by="invalid")
