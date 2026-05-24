"""Carga y validación de config.yaml mediante Pydantic v2."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import yaml
from loguru import logger
from pydantic import BaseModel, Field, ValidationError


# ── Enumeraciones ──────────────────────────────────────────────


class ExperienceLevel(str, Enum):
    entry = "entry"
    associate = "associate"
    mid_senior = "mid_senior"
    director = "director"
    executive = "executive"


class DatePosted(str, Enum):
    past_24h = "past_24h"
    past_week = "past_week"
    past_month = "past_month"


class JobType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    temporary = "temporary"
    internship = "internship"


class SortBy(str, Enum):
    recent = "recent"
    relevant = "relevant"


# ── Modelos Pydantic ───────────────────────────────────────────


class LinkedInConfig(BaseModel):
    session_file: str = "data/session/linkedin_session.json"
    headless: bool = True


class SearchConfig(BaseModel):
    keywords: Annotated[str, Field(description="Términos de búsqueda en LinkedIn Jobs")]
    location: str = ""
    experience_level: list[ExperienceLevel] = []
    date_posted: DatePosted | None = None
    job_type: list[JobType] = []
    remote: bool = False
    max_results: int = Field(default=100, ge=1, le=500)
    sort_by: SortBy = SortBy.recent


class ScheduleConfig(BaseModel):
    enabled: bool = True
    frequency: str = "daily"  # daily | weekly | every_Xh
    every_hours: Annotated[int, Field(ge=1, le=720)] = 24
    hour: str = "09:00"


class GDriveConfig(BaseModel):
    enabled: bool = True
    credentials_file: str = "credentials.json"
    token_file: str = "token.json"
    folder_id: str = ""
    filename_prefix: str = "ofertas"


class DedupConfig(BaseModel):
    history_file: str = "data/history/offers_history.json"


class AppConfig(BaseModel):
    linkedin: LinkedInConfig = LinkedInConfig()
    search: SearchConfig
    schedule: ScheduleConfig = ScheduleConfig()
    google_drive: GDriveConfig = GDriveConfig()
    dedup: DedupConfig = DedupConfig()


# ── Función pública ────────────────────────────────────────────


def load_config(path: str = "config.yaml") -> AppConfig:
    """Carga, valida y retorna la configuración desde un archivo YAML.

    Las rutas relativas se resuelven respecto al cwd.
    """
    config_path = Path(path)
    if not config_path.exists():
        logger.error(
            f"No se encontró {path}. Ejecuta 'jobhunter init' para crearlo."
        )
        raise SystemExit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        logger.error(f"El archivo {path} no tiene un formato YAML válido.")
        raise SystemExit(1)

    try:
        cfg = AppConfig.model_validate(raw)
    except ValidationError as exc:
        logger.error(f"Error de validación en {path}:\n{exc}")
        raise SystemExit(1)

    return cfg
