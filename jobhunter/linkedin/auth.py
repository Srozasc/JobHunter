"""Autenticación persistente con LinkedIn mediante Playwright."""

import os
import stat
from pathlib import Path

from loguru import logger
from playwright.async_api import BrowserContext, async_playwright

LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"
LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"


async def ensure_session(
    session_file: str = "data/session/linkedin_session.json",
    headless: bool = True,
) -> BrowserContext:
    """Asegura una sesión válida de LinkedIn, reutilizando o creando una nueva.

    Flujo:
      1. Si session_file existe → cargar → validar → retornar.
      2. Si expiró → borrar → re-login con headed.
      3. Si no exists → login con headed.
    """
    session_path = Path(session_file)

    if session_path.exists():
        logger.info("Sesión existente encontrada, validando...")
        ctx = await _load_session(session_file, headless=headless)
        if await _is_session_valid(ctx):
            logger.info("Sesión válida, reutilizando.")
            return ctx
        else:
            logger.warning("Sesión expirada. Solicitando re-login...")
            await _close_context(ctx)
            session_path.unlink(missing_ok=True)
    else:
        logger.info("No se encontró sesión existente.")

    return await _login_flow(session_file, headless=False)


# ── Privadas ───────────────────────────────────────────────────


async def _load_session(session_file: str, headless: bool) -> BrowserContext:
    """Carga sesión desde archivo storage_state."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    ctx = await browser.new_context(storage_state=session_file)
    # Guardar referencia para cerrar después
    ctx._playwright = playwright  # type: ignore[attr-defined]
    return ctx


async def _is_session_valid(ctx: BrowserContext) -> bool:
    """Verifica si la sesión es válida navegando al feed."""
    page = await ctx.new_page()
    try:
        await page.goto(LINKEDIN_FEED_URL, wait_until="networkidle", timeout=30000)
        final_url = page.url
        is_valid = "/login" not in final_url and "/checkpoint" not in final_url
        if not is_valid:
            logger.debug(f"Sesión inválida: redirigido a {final_url}")
        return is_valid
    except Exception as e:
        logger.error(f"Error validando sesión: {e}")
        return False
    finally:
        await page.close()


async def _login_flow(session_file: str, headless: bool) -> BrowserContext:
    """Abre navegador para login manual del usuario."""
    logger.info("Abriendo navegador para login de LinkedIn...")
    logger.info("Por favor, inicia sesión en la ventana del navegador.")

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    ctx = await browser.new_context()
    ctx._playwright = playwright  # type: ignore[attr-defined]

    page = await ctx.new_page()
    await page.goto(LINKEDIN_LOGIN_URL)

    logger.info("Esperando login manual... (máximo 5 minutos)")
    try:
        await page.wait_for_url("**/feed/**", timeout=300_000)
        logger.info("Login exitoso detectado.")
    except Exception:
        logger.error("Timeout esperando login. Cerrando.")
        await _close_context(ctx)
        raise RuntimeError("Login timeout: no se detectó inicio de sesión en 5 minutos.")

    # Guardar sesión
    session_path = Path(session_file)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    await ctx.storage_state(path=session_file)
    os.chmod(session_file, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    logger.info(f"Sesión guardada en {session_file} (permisos 0600)")

    await page.close()
    return ctx


async def _close_context(ctx: BrowserContext) -> None:
    """Cierra contexto y navigator de forma segura."""
    try:
        await ctx.browser.close()
    except Exception:
        pass
    try:
        await ctx._playwright.stop()  # type: ignore[attr-defined]
    except Exception:
        pass
