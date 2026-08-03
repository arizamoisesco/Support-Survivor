from dotenv import load_dotenv
load_dotenv()# Cargar variables de entorno desde el archivo .env

import asyncio 
import os
import io
import random
import secrets
import string
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import boto3
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from langchain_aws import ChatBedrock
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from auth import supabase, verify_token, require_admin, require_learner
from db_init import init_db
import config as cfg

# Configuration app
async def lifespan(app):
    await init_db(supabase)
    cfg.init_config(supabase) # carga todos los configs de Supabase al arrancar
    yield

app = FastAPI(title="Soporte TI - Simulador API v2", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://main.d1cutcgdr87tup.amplifyapp.com"],
    #allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cliente boto3 compartido para ambos modelos
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

# Limit of history messages to keep in context
MAX_HISTORY_TURNS = 20 # 20 for users / assistants, 40 for system messages

#Delay artificial
TYPING_DELAY = 2.0

# Verify DB to start
@app.on_event("startup")
async def startup():
    await init_db(supabase)

# Pydantic model

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    session_id: str
    messages: list[ChatMessage]
    # This part allow change the system prompt since from the frontend
    system: str | None = None

class ChatResponse(BaseModel):
    message: str
    #system: str # Pensar seriamente si quito esto because no it's necessary if the frontend to tale to endpoint yet

class SessionResponse(BaseModel):
    session_id: str
    system: str

class EvaluateRequest(BaseModel):
    session_id: str
    messages: list[ChatMessage]
    duration_seconds: int

class EvaluationResponse(BaseModel):
    scores: dict
    total: float
    feedback_positive: str
    feedback_improve: str
    criteria_labels: dict


# Cataloge
class ClientNameIn(BaseModel):
    name:str

class IncidentIn(BaseModel):
    description:str
    category: str | None = None

class PersonalityIn(BaseModel):
    name: str
    description: str

# Users
class LearnerIn(BaseModel):
    email: EmailStr
    full_name: str
    cohort: int
    password: str | None = None

#Config
class ConfigUpdate(BaseModel):
    value: str

# Initialize the Bedrock model
def get_llm() -> ChatBedrock:
    """Initialize the Bedrock model with the specified parameters."""
    return ChatBedrock(
        model_id="meta.llama3-70b-instruct-v1:0", # Este modelo es más caro pero tiene soporte de chat y es muy potente, ideal para el rol play, aunque hay que ajustar el prompt para que no se vuelva loco y se mantenga en el rol, ya que es un modelo muy grande y con mucha capacidad de generación, lo que puede hacer que se salga del rol si el prompt no es lo suficientemente claro y restrictivo.
        client=bedrock_client,
        model_kwargs={
            "temperature": 0.8,
            "max_tokens": 1000,
        }, 
        streaming = False,
    )

# Helper

"""
def random_stage_system_promt(
        client_names: tuple[str], 
        incidents: tuple[str], 
        personalities:tuple[str]
) -> str:
    
    actual_incidents:str = random.choice(incidents)
    actual_personality:str = random.choice(personalities)
    client_name:str = random.choice(client_names)

    system_prompt:str = f'''
    ESTÁS EN UN ROL DE SIMULACIÓN (ROLEPLAY).
    Eres un cliente contactando a soporte TI.
    
    TU PERFIL:
    - Nombre: {client_name}
    - Incidente: {actual_incidents}
    - Personalidad: {actual_personality}
    
    REGLAS DE COMPORTAMIENTO:
    1. NO eres un asistente de IA. Eres un humano frustrado que representa a un cliente real.
    2. Empieza la conversación muy molesto o preocupado o alterado según tu personalidad.
    3. NO aceptes soluciones técnicas complejas de inmediato.
    4. CRITERIO DE DESESCALADA: Solo si el agente (usuario) muestra EMPATÍA real, valida tus sentimientos Y ofrece una solución clara, bajarás el tono.
    5. Si el agente es frío, técnico o robótico, aumenta tu molestia.
    6. Mantén respuestas breves (como en un chat real).
    7. Si el especialista de soporte te ofrece una solución que resuelve tu problema, aunque no sea la más técnica o avanzada, muestra agradecimiento y satisfacción, y da por resuelto el incidente.
    8. Si comete errores de ortografia o gramática, no los corrijas, ya que eres un cliente real y eso es normal en un chat de soporte.
    9. De vez en cuando comete errore de tipeo o escribe palabras mal, para simular un chat real de soporte.
    10. Si el agente de soporte te ofrece una solución que no entiendes, muestra confusión y pide que te lo expliquen de otra manera, sin usar términos técnicos.
    11. Si el agente de soporte te ofrece una solución que es claramente incorrecta o que no tiene sentido, muestra frustración y dile que eso no va a funcionar, sin ser grosero.
    12. Si el especialista de soporte demora mucho en responder, muestra impaciencia y dile que estás esperando una respuesta, sin ser grosero.
    13. Si recibes el mensaje INTERNO [ESPECIALISTA_INACTIVO], pregunta con impaciencia si hay alguien ahí, acorde a tu personalidad.
    '''

    return system_prompt
"""

def get_evaluator_llm() -> ChatBedrock:
    return ChatBedrock(
        model_id="meta.llama3-70b-instruct-v1:0",
        client=bedrock_client,
        model_kwargs={"temperature": 0.1, "max_tokens": 1500},
        streaming=False,
    )

def build_langchain_messages( 
    messages: list[ChatMessage],
    system_prompt: str
) -> list:
    """"
    Convert frontend history messages to Langchain format, 
    truncate if history exceeds limits and add system prompt if provided.
    """

    result = [SystemMessage(content=system_prompt)]

    #Truncate history if exceeds limits
    if len(messages) > MAX_HISTORY_TURNS * 2: # *2 because each turn has user + assistant message
        messages = messages[-(MAX_HISTORY_TURNS * 2):]

    for message in messages:
        if message.role == "user":
            result.append(HumanMessage(content=message.content))
        elif message.role == "assistant":
            result.append(AIMessage(content=message.content))
        else:
            raise ValueError(f"Invalid message role: {message.role}")

    return result

def format_conversation(messages: list[ChatMessage]) -> str:
    lines = []
    for msg in messages:
        role = "ESPECIALISTA" if msg.role == "user" else "CLIENTE"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)

def generate_password(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(length))

async def create_learner_account(learner: LearnerIn) -> dict:
    """Crea usuario en Supabase Auth + perfil. Devuelve email y contraseña."""
    password = learner.password or generate_password()
    try:
        result = supabase.auth.admin.create_user({ # Revisar este result que no es accesible
            "email":    learner.email,
            "password": password,
            "email_confirm": True,          # confirmar automáticamente
            "user_metadata": {
                "full_name": learner.full_name,
                "role":      "learner",
                "cohort":    learner.cohort,
            },
        })
        return {"email": learner.email, "password": password, "status": "created"}
    except Exception as e:
        return {"email": learner.email, "error": str(e), "status": "failed"}

# Public Endpoints
@app.get("/")
def read_root():
    return {"message": "¡Hola! Esta es la API de simulación de soporte TI."}

@app.get("/health")
async def health():
    return {"status": "ok"}

# Learner: Start practice session
@app.post("/session/new", response_model=SessionResponse)
async def new_session(payload: dict = Depends(require_learner)):
    learner_id   = payload["sub"]
    timer_seconds = cfg.get_int("session_timer_seconds", 180)
 
    # Priorizar scenarios narrativos no vistos
    vistos = supabase.table("sessions")\
        .select("scenario_id")\
        .eq("learner_id", learner_id)\
        .eq("session_type", "scenario")\
        .not_.is_("scenario_id", "null")\
        .execute()
 
    ids_vistos = [s["scenario_id"] for s in (vistos.data or []) if s["scenario_id"]]
    query = supabase.table("scenarios").select("*").eq("active", True)
    if ids_vistos:
        query = query.not_.in_("id", ids_vistos)
 
    narrativos = query.execute()
 
    if narrativos.data:
        escenario = random.choice(narrativos.data)
        session = supabase.table("sessions").insert({
            "learner_id":     learner_id,
            "scenario_id":    escenario["id"],
            "combination_id": None,
            "system_prompt":  escenario["system_prompt"],
            "session_type":   "scenario",
            "status":         "active",
            "timer_seconds":  timer_seconds,
        }).execute()
 
        return SessionResponse(
            session_id=session.data[0]["id"],
            system=escenario["system_prompt"],
            timer_seconds=timer_seconds,
            session_type="scenario",
        )
 
    # Fallback a combinaciones aleatorias del catálogo
    usadas = supabase.table("scenario_combinations")\
        .select("client_name_id, incident_id, personality_id")\
        .eq("learner_id", learner_id).execute()
 
    usadas_set = {(r["client_name_id"], r["incident_id"], r["personality_id"])
                  for r in (usadas.data or [])}
 
    names = supabase.table("client_names").select("*").eq("active", True).execute().data
    incs  = supabase.table("incidents").select("*").eq("active", True).execute().data
    pers  = supabase.table("personalities").select("*").eq("active", True).execute().data
 
    disponibles = [
        (n, i, p) for n in names for i in incs for p in pers
        if (n["id"], i["id"], p["id"]) not in usadas_set
    ]
 
    if not disponibles:
        raise HTTPException(status_code=404,
            detail="Ya practicaste todos los casos disponibles. ¡Felicitaciones!")
 
    name, inc, per = random.choice(disponibles)
 
    system_prompt = (
        f"ESTÁS EN UN ROL DE SIMULACIÓN (ROLEPLAY).\n"
        f"Eres un cliente contactando a soporte TI.\n\n"
        f"TU PERFIL:\n"
        f"- Nombre: {name['name']}\n"
        f"- Incidente: {inc['description']}\n"
        f"- Personalidad: {per['name']} — {per['description']}\n\n"
        f"REGLAS DE COMPORTAMIENTO:\n"
        f"1. NO eres un asistente de IA. Eres un humano frustrado representando a un cliente real.\n"
        f"2. Empieza la conversación muy molesto, asustado o alterado según tu personalidad.\n"
        f"3. NO aceptes soluciones técnicas complejas de inmediato.\n"
        f"4. Solo baja el tono si el agente muestra EMPATÍA real y ofrece solución clara.\n"
        f"5. Si el agente es frío o robótico, aumenta tu molestia.\n"
        f"6. Respuestas breves, 1-3 oraciones máximo.\n"
        f"7. Si el especialista resuelve tu problema, muestra agradecimiento.\n"
        f"8. No corrijas errores de ortografía del agente.\n"
        f"9. De vez en cuando comete errores de tipeo para simular un chat real.\n"
        f"10. Si no entiendes algo técnico, pide explicación simple.\n"
        f"Responde siempre en español."
    )
 
    combo = supabase.table("scenario_combinations").insert({
        "learner_id":     learner_id,
        "client_name_id": name["id"],
        "incident_id":    inc["id"],
        "personality_id": per["id"],
    }).execute()
 
    session = supabase.table("sessions").insert({
        "learner_id":     learner_id,
        "combination_id": combo.data[0]["id"],
        "scenario_id":    None,
        "system_prompt":  system_prompt,
        "session_type":   "combination",
        "status":         "active",
        "timer_seconds":  timer_seconds,
    }).execute()
 
    return SessionResponse(
        session_id=session.data[0]["id"],
        system=system_prompt,
        timer_seconds=timer_seconds,
        session_type="combination",
    )
 
 
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, payload: dict = Depends(require_learner)):
    if not request.messages:
        raise HTTPException(status_code=400, detail="Se requiere al menos un mensaje")
 
    lc_messages = build_langchain_messages(request.messages, request.system)
    llm = get_llm()
 
    response, _ = await asyncio.gather(
        asyncio.to_thread(llm.invoke, lc_messages),
        asyncio.sleep(TYPING_DELAY),
    )
 
    content = response.content
    ultimo  = request.messages[-1]
    supabase.table("messages").insert([
        {"session_id": request.session_id, "role": "user",      "content": ultimo.content},
        {"session_id": request.session_id, "role": "assistant", "content": content},
    ]).execute()
 
    return ChatResponse(message=content)
 
 
@app.post("/session/evaluate", response_model=EvaluationResponse)
async def evaluate_session(request: EvaluateRequest, payload: dict = Depends(require_learner)):
    if not request.messages:
        raise HTTPException(status_code=400, detail="No hay mensajes para evaluar")
 
    # Leer prompt de evaluación desde Supabase (ya en cache)
    eval_prompt_template = cfg.get("evaluation_prompt")
    if not eval_prompt_template:
        raise HTTPException(status_code=500,
            detail="Prompt de evaluación no configurado. Contacta al administrador.")
 
    # Contexto del escenario para el evaluador
    session_data = supabase.table("sessions")\
        .select("system_prompt")\
        .eq("id", request.session_id)\
        .single().execute()
 
    system_prompt    = session_data.data.get("system_prompt", "")
    scenario_context = f"Perfil del cliente simulado:\n{system_prompt[:800]}"
    conversation     = format_conversation(request.messages)
 
    eval_prompt = eval_prompt_template.format(
        scenario_context=scenario_context,
        conversation=conversation,
    )
 
    llm = get_evaluator_llm()
 
    try:
        response = await asyncio.to_thread(
            llm.invoke, [HumanMessage(content=eval_prompt)]
        )
        import json
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())
 
    except Exception as e:
        raise HTTPException(status_code=500,
            detail=f"Error al generar la evaluación: {str(e)}")
 
    # Guardar en Supabase
    try:
        supabase.table("evaluations").upsert({
            "session_id":        request.session_id,
            "criteria_scores":   result["scores"],
            "total_score":       int(float(result["total"])),
            "feedback_positive": result["feedback_positive"],
            "feedback_improve":  result["feedback_improve"],
        }).execute()
 
        supabase.table("sessions").update({
            "status":           "completed",
            "ended_at":         datetime.now(timezone.utc).isoformat(),
            "revealed":         True,
            "duration_seconds": request.duration_seconds,
        }).eq("id", request.session_id).execute()
 
    except Exception:
        pass
 
    # Leer labels de criterios desde Supabase
    criteria_labels = cfg.get_json("criteria_labels", {
        "ciclo_gestion":            "Ciclo de gestión de incidencias",
        "lenguaje_positivo":        "Lenguaje positivo y profesional",
        "reconocimiento_emociones": "Reconocimiento de emociones",
        "adaptacion_perfil":        "Adaptación al perfil del cliente",
        "estructura_conversacion":  "Estructura de la conversación",
        "claridad_concision":       "Claridad y concisión",
        "gramatica_ortografia":     "Gramática y ortografía",
    })
 
    return EvaluationResponse(
        scores=result["scores"],
        total=float(result["total"]),
        feedback_positive=result["feedback_positive"],
        feedback_improve=result["feedback_improve"],
        criteria_labels=criteria_labels,
    )
 
 
# ── Admin: configuraciones ─────────────────────────────────────────────────────
 
@app.get("/admin/config")
async def list_configs(payload: dict = Depends(require_admin)):
    """Lista todas las configuraciones del sistema."""
    return supabase.table("system_configs").select("*").order("key").execute().data
 
@app.patch("/admin/config/{key}")
async def update_config(key: str, update: ConfigUpdate, payload: dict = Depends(require_admin)):
    """Actualiza una configuración y recarga el cache automáticamente."""
    result = supabase.table("system_configs")\
        .update({"value": update.value})\
        .eq("key", key).execute()
 
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Configuración '{key}' no encontrada")
 
    # Recargar cache para que el cambio sea inmediato
    cfg.reload_config(supabase)
 
    return result.data[0]
 
@app.post("/admin/config/reload")
async def reload_configs(payload: dict = Depends(require_admin)):
    """Fuerza recarga del cache de configuraciones."""
    cfg.reload_config(supabase)
    return {"message": "Configuraciones recargadas", "keys": list(cfg._cache.keys())}
 
 
# ── Admin: usuarios ────────────────────────────────────────────────────────────
 
@app.post("/admin/learners")
async def create_learner(learner: LearnerIn, payload: dict = Depends(require_admin)):
    return await create_learner_account(learner)
 
@app.post("/admin/learners/bulk")
async def create_learners_bulk(file: UploadFile = File(...), payload: dict = Depends(require_admin)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan .xlsx o .xls")
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo Excel")
    required = {"full_name", "email", "cohort"}
    missing  = required - set(df.columns.str.lower())
    if missing:
        raise HTTPException(status_code=400, detail=f"Columnas faltantes: {', '.join(missing)}")
    df.columns = df.columns.str.lower()
    results = []
    for _, row in df.iterrows():
        learner = LearnerIn(
            email=str(row["email"]).strip(),
            full_name=str(row["full_name"]).strip(),
            cohort=int(row["cohort"]),
            password=str(row["password"]).strip()
                if "password" in df.columns and pd.notna(row.get("password")) else None,
        )
        results.append(await create_learner_account(learner))
    created = [r for r in results if r["status"] == "created"]
    failed  = [r for r in results if r["status"] == "failed"]
    return {"total": len(results), "created": len(created), "failed": len(failed), "results": results}
 
@app.get("/admin/learners/template")
async def download_template(payload: dict = Depends(require_admin)):
    df = pd.DataFrame(columns=["full_name", "email", "cohort", "password"])
    df.loc[0] = ["Juan Pérez",  "juan.perez@empresa.com",  9, ""]
    df.loc[1] = ["María López", "maria.lopez@empresa.com", 9, ""]
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Learners")
        ws = writer.sheets["Learners"]
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 32
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 16
    buffer.seek(0)
    return StreamingResponse(buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_learners.xlsx"})
 
@app.get("/admin/learners")
async def list_learners(payload: dict = Depends(require_admin)):
    return supabase.table("profiles")\
        .select("id, email, full_name, cohort, active, created_at")\
        .eq("role", "learner").order("cohort", desc=True).order("full_name").execute().data
 
@app.patch("/admin/learners/{learner_id}")
async def update_learner(learner_id: str, updates: dict, payload: dict = Depends(require_admin)):
    allowed  = {"full_name", "cohort", "active"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    return supabase.table("profiles").update(filtered).eq("id", learner_id).execute().data[0]
 
 
# ── Admin: catálogos ───────────────────────────────────────────────────────────
 
@app.get("/admin/catalog/names")
async def list_names(payload: dict = Depends(require_admin)):
    return supabase.table("client_names").select("*").order("name").execute().data
 
@app.post("/admin/catalog/names")
async def add_name(item: ClientNameIn, payload: dict = Depends(require_admin)):
    return supabase.table("client_names")\
        .insert({"name": item.name, "created_by": payload["sub"]}).execute().data[0]
 
@app.patch("/admin/catalog/names/{item_id}")
async def toggle_name(item_id: str, updates: dict, payload: dict = Depends(require_admin)):
    return supabase.table("client_names")\
        .update({"active": updates.get("active", True)}).eq("id", item_id).execute().data[0]
 
@app.get("/admin/catalog/incidents")
async def list_incidents(payload: dict = Depends(require_admin)):
    return supabase.table("incidents").select("*").order("category").execute().data
 
@app.post("/admin/catalog/incidents")
async def add_incident(item: IncidentIn, payload: dict = Depends(require_admin)):
    return supabase.table("incidents").insert({
        "description": item.description, "category": item.category,
        "created_by": payload["sub"]
    }).execute().data[0]
 
@app.patch("/admin/catalog/incidents/{item_id}")
async def toggle_incident(item_id: str, updates: dict, payload: dict = Depends(require_admin)):
    return supabase.table("incidents")\
        .update({"active": updates.get("active", True)}).eq("id", item_id).execute().data[0]
 
@app.get("/admin/catalog/personalities")
async def list_personalities(payload: dict = Depends(require_admin)):
    return supabase.table("personalities").select("*").order("name").execute().data
 
@app.post("/admin/catalog/personalities")
async def add_personality(item: PersonalityIn, payload: dict = Depends(require_admin)):
    return supabase.table("personalities").insert({
        "name": item.name, "description": item.description,
        "created_by": payload["sub"]
    }).execute().data[0]
 
@app.patch("/admin/catalog/personalities/{item_id}")
async def toggle_personality(item_id: str, updates: dict, payload: dict = Depends(require_admin)):
    return supabase.table("personalities")\
        .update({"active": updates.get("active", True)}).eq("id", item_id).execute().data[0]
 
 
# ── Admin: scenarios narrativos ────────────────────────────────────────────────
 
@app.get("/admin/scenarios")
async def list_scenarios(payload: dict = Depends(require_admin)):
    return supabase.table("scenarios").select("*").order("created_at", desc=True).execute().data
 
@app.post("/admin/scenarios")
async def create_scenario(scenario: dict, payload: dict = Depends(require_admin)):
    scenario["created_by"] = payload["sub"]
    return supabase.table("scenarios").insert(scenario).execute().data[0]
 
@app.patch("/admin/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, updates: dict, payload: dict = Depends(require_admin)):
    return supabase.table("scenarios").update(updates).eq("id", scenario_id).execute().data[0]
 
 
# ── Admin: reportes ────────────────────────────────────────────────────────────
 
@app.get("/admin/sessions")
async def list_sessions(payload: dict = Depends(require_admin)):
    return supabase.table("sessions")\
        .select("""
            id, status, session_type, started_at, ended_at, duration_seconds, timer_seconds,
            profiles:learner_id (full_name, email, cohort),
            evaluations (total_score, criteria_scores, feedback_positive, feedback_improve),
            scenario_combinations (
                client_names (name),
                incidents (description),
                personalities (name)
            ),
            scenarios (title, difficulty)
        """)\
        .order("started_at", desc=True).execute().data
 

@app.get("/admin/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, payload: dict = Depends(require_admin)):
    result = supabase.table("messages")\
        .select("role, content, created_at")\
        .eq("session_id", session_id)\
        .order("created_at")\
        .execute()
    return result.data