# config.py
# Lee configuraciones desde la tabla system_configs de Supabase.
# Usa cache en memoria para no consultar Supabase en cada request.
# El instructor/admin puede editar los valores desde el panel
# y llamar a /admin/config/reload para refrescar el cache.

import json
import logging
from supabase import Client

logger = logging.getLogger(__name__)

_cache: dict = {}


def _load_all(supabase: Client) -> None:
    """Carga todos los registros de system_configs en el cache."""
    result = supabase.table("system_configs").select("key, value").execute()
    for row in (result.data or []):
        _cache[row["key"]] = row["value"]
    logger.info(f"✅ Configuraciones cargadas: {list(_cache.keys())}")


def init_config(supabase: Client) -> None:
    """Llamar al arrancar el servidor."""
    _load_all(supabase)


def reload_config(supabase: Client) -> None:
    """Recargar el cache — llamar desde el endpoint /admin/config/reload."""
    _cache.clear()
    _load_all(supabase)


def get(key: str, default: str = "") -> str:
    """Obtener un valor de configuración como string."""
    return _cache.get(key, default)


def get_json(key: str, default=None):
    """Obtener un valor de configuración parseado como JSON."""
    raw = _cache.get(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"No se pudo parsear como JSON la config '{key}'")
        return default


def get_int(key: str, default: int = 0) -> int:
    """Obtener un valor de configuración como entero."""
    try:
        return int(_cache.get(key, default))
    except (ValueError, TypeError):
        return default