# db_init.py
# Se ejecuta al iniciar el backend (startup event de FastAPI)
# Crea las tablas si no existen — quien clone el repo ya tiene el modelo listo

import os
import logging
from supabase import Client

logger = logging.getLogger(__name__)

# ── System prompt base — se rellena con los datos del catálogo ─────────────────
SYSTEM_PROMPT_TEMPLATE = """ESTÁS EN UN ROL DE SIMULACIÓN (ROLEPLAY).
Eres un cliente contactando a soporte TI.

TU PERFIL:
- Nombre: {client_name}
- Incidente: {incident}
- Personalidad: {personality_name} — {personality_description}

REGLAS DE COMPORTAMIENTO:
1. NO eres un asistente de IA. Eres un humano frustrado representando a un cliente real.
2. Empieza la conversación muy molesto, asustado o alterado según tu personalidad.
3. NO aceptes soluciones técnicas complejas de inmediato.
4. CRITERIO DE DESESCALADA: Solo si el agente muestra EMPATÍA real, valida tus sentimientos Y ofrece una solución clara, bajarás el tono.
5. Si el agente es frío, técnico o robótico, aumenta tu molestia.
6. Mantén respuestas breves (como en un chat real), 1-3 oraciones máximo.
7. Si el especialista ofrece una solución que resuelve tu problema, muestra agradecimiento y da el incidente por resuelto.
8. No corrijas errores de ortografía del agente.
9. De vez en cuando comete errores de tipeo para simular un chat real.
10. Si no entiendes una solución técnica, pide que te lo expliquen sin términos técnicos.
11. Si una solución es claramente incorrecta, muéstrate frustrado pero no grosero.
12. Si el agente demora mucho en responder, muestra impaciencia.
13. Si recibes el mensaje INTERNO [ESPECIALISTA_INACTIVO], pregunta con impaciencia si hay alguien ahí.
Responde siempre en español."""


async def init_db(supabase: Client):
    """
    Verifica que las tablas existan y los catálogos tengan datos.
    Supabase no permite CREATE TABLE IF NOT EXISTS desde el cliente Python,
    así que usamos una verificación: si la query falla, las tablas no existen
    y guiamos al usuario a ejecutar el schema.sql.
    """
    try:
        # Verificar que las tablas principales existen
        supabase.table("profiles").select("id").limit(1).execute()
        supabase.table("client_names").select("id").limit(1).execute()
        supabase.table("incidents").select("id").limit(1).execute()
        supabase.table("personalities").select("id").limit(1).execute()
        logger.info("✅ Tablas verificadas correctamente")

        # Si los catálogos están vacíos, insertar datos iniciales
        await _seed_catalogs(supabase)

    except Exception as e:
        logger.error(
            "❌ Las tablas no existen. Ejecuta sql/schema.sql en Supabase SQL Editor. "
            f"Error: {e}"
        )
        raise RuntimeError(
            "Base de datos no inicializada. "
            "Ve a Supabase → SQL Editor y ejecuta el archivo sql/schema.sql"
        )


async def _seed_catalogs(supabase: Client):
    """Inserta datos iniciales si los catálogos están vacíos."""

    # client_names
    names_result = supabase.table("client_names").select("id").limit(1).execute()
    if not names_result.data:
        supabase.table("client_names").insert([
            {"name": "Carlos Martínez"},
            {"name": "Ana García"},
            {"name": "Luis Rodríguez"},
            {"name": "Marta López"},
            {"name": "Jorge Hernández"},
            {"name": "Sofía Martínez"},
            {"name": "Pedro González"},
            {"name": "Lucía Sánchez"},
        ]).execute()
        logger.info("✅ Nombres de clientes insertados")

    # incidents
    incidents_result = supabase.table("incidents").select("id").limit(1).execute()
    if not incidents_result.data:
        supabase.table("incidents").insert([
            {"description": "No puedo acceder a mi correo corporativo desde ayer.", "category": "correo"},
            {"description": "La VPN se desconecta cada 10 minutos y tengo una presentación en 1 hora.", "category": "red"},
            {"description": "Mi pantalla se puso azul y perdí el informe trimestral no guardado.", "category": "hardware"},
            {"description": "El sistema de facturación no carga y estoy perdiendo ventas.", "category": "software"},
            {"description": "No puedo imprimir y el cliente llega en 20 minutos.", "category": "hardware"},
        ]).execute()
        logger.info("✅ Incidentes insertados")

    # personalities
    personalities_result = supabase.table("personalities").select("id").limit(1).execute()
    if not personalities_result.data:
        supabase.table("personalities").insert([
            {
                "name": "AGRESIVO",
                "description": "Gritas (en mayúsculas a veces), amenazas con llamar al supervisor, no entiendes razones técnicas. Si el agente es empático y claro, bajas el tono gradualmente."
            },
            {
                "name": "ASUSTADO",
                "description": "Crees que te van a despedir por este problema. Estás en pánico, pides ayuda desesperadamente y agradeces cualquier avance."
            },
            {
                "name": "SARCÁSTICO",
                "description": "Te burlas de la competencia de TI, haces comentarios pasivo-agresivos, eres impaciente pero no grosero."
            },
        ]).execute()
        logger.info("✅ Personalidades insertadas")