"""Autenticación OAuth2 con Google Drive API v3."""

import os
import stat
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from loguru import logger

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service(
    credentials_file: str = "credentials.json",
    token_file: str = "token.json",
):
    """Obtiene un servicio autenticado de Google Drive API v3.

    Flujo:
      1. Si token.json existe y es válido → lo carga.
      2. Si expirado pero tiene refresh_token → lo refresca.
      3. Si no hay token válido → inicia flujo OAuth2 de consola.
    """
    creds = _load_or_refresh_credentials(credentials_file, token_file)
    return build("drive", "v3", credentials=creds)


def _load_or_refresh_credentials(
    credentials_file: str, token_file: str
) -> Credentials:
    """Carga credenciales existentes, refresca si necesario, o inicia flujo."""
    creds = _load_token(token_file)

    if creds and creds.valid:
        logger.info("Token válido cargado, reutilizando.")
        return creds
    elif creds and creds.expired and creds.refresh_token:
        logger.info("Token expirado, refrescando...")
        creds.refresh(Request())
        _save_token(creds, token_file)
        return creds
    else:
        logger.info("Iniciando flujo de autorización OAuth2...")
        return _perform_oauth_flow(credentials_file, token_file)


def _load_token(token_file: str) -> Credentials | None:
    """Carga token desde archivo. Retorna None si no existe o es inválido."""
    token_path = Path(token_file)
    if not token_path.exists():
        logger.debug(f"No existe {token_file}, se necesitará autorización inicial.")
        return None
    try:
        return Credentials.from_authorized_user_file(token_file, SCOPES)
    except Exception as e:
        logger.warning(f"Error cargando token: {e}. Se solicitará re-autorización.")
        return None


def _perform_oauth_flow(credentials_file: str, token_file: str) -> Credentials:
    """Ejecuta flujo OAuth2 de consola o servidor local."""
    creds_path = Path(credentials_file)
    if not creds_path.exists():
        msg = (
            f"No se encontró '{credentials_file}'.\n"
            "Descarga las credenciales OAuth2 desde Google Cloud Console:\n"
            "https://console.cloud.google.com/apis/credentials → "
            "'Create Credentials' → 'OAuth 2.0 Client ID' → Type: 'Desktop app'.\n"
            "Luego guarda el archivo JSON descargado como 'credentials.json' "
            "en el directorio del proyecto."
        )
        raise FileNotFoundError(msg)

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    try:
        creds = flow.run_console()
    except OSError:
        creds = flow.run_local_server(port=0)
    _save_token(creds, token_file)
    logger.info(f"Token guardado en {token_file}")
    return creds


def _save_token(creds: Credentials, token_file: str) -> None:
    """Guarda token en archivo con permisos restrictivos."""
    token_path = Path(token_file)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
