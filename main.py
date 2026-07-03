from dotenv import load_dotenv
load_dotenv()# Cargar variables de entorno desde el archivo .env

import asyncio 
import os
import io
import random
import secrets
import string
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
from db_init import init_db, SYSTEM_PROMPT_TEMPLATE

# Configuration app

app = FastAPI(title="Soporte TI - Simulador API v2")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    #allow_origins=["*"],
    #allow_credentials=True,
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

#
# Nombres aleatorios para los clientes
client_names = ["Carlos Martinez", "Ana García", "Luis Rodríguez", "Marta López", "Jorge Hernández", "Sofía Martínez", "Pedro González", "Lucía Sánchez"]

# Bases de datos de simulacion
incidents = [
    "El servidor de correo no sincroniza y estoy perdiendo ventas.",
    "La VPN me desconecta cada 10 minutos y tengo una presentación en 1 hora.",
    "Mi pantalla se puso azul y perdí el informe trimestral no guardado."
]

personalities = [
    "AGRESIVO: Gritas (en mayúsculas a veces), amenazas con llamar al supervisor, no entiendes razones técnicas.",
    "ASUSTADO: Crees que te van a despedir por esto, estás en pánico, pides ayuda desesperadamente.",
    "SARCÁSTICO: Te burlas de la competencia de TI, haces comentarios pasivo-agresivos, eres impaciente."
]

# System prompt: AI role
SYSTEM_PROMPT = """Eres un cliente que llama a soporte técnico.
Estás frustrado porque llevas tiempo con un problema sin resolver.
Eres impaciente, a veces interrumpes, y a veces das información incompleta.
Solo das más detalles cuando el agente de soporte te hace las preguntas correctas.
Responde siempre en español. Tus respuestas son cortas, de 1-3 oraciones.
Problema actual: No puedes acceder a tu correo corporativo desde ayer."""

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
    learner_id = payload["sub"]
 
    # Combinaciones que el learner ya usó
    usadas = supabase.table("scenario_combinations")\
        .select("client_name_id, incident_id, personality_id")\
        .eq("learner_id", learner_id)\
        .execute()
 
    usadas_set = {
        (r["client_name_id"], r["incident_id"], r["personality_id"])
        for r in (usadas.data or [])
    }
 
    # Cargar catálogos activos
    names   = supabase.table("client_names").select("*").eq("active", True).execute().data
    incs    = supabase.table("incidents").select("*").eq("active", True).execute().data
    pers    = supabase.table("personalities").select("*").eq("active", True).execute().data
 
    if not names or not incs or not pers:
        raise HTTPException(status_code=500, detail="Los catálogos están vacíos. Contacta al administrador.")
 
    # Generar todas las combinaciones posibles no usadas
    disponibles = [
        (n, i, p)
        for n in names for i in incs for p in pers
        if (n["id"], i["id"], p["id"]) not in usadas_set
    ]
 
    if not disponibles:
        raise HTTPException(
            status_code=404,
            detail="Ya practicaste todas las combinaciones disponibles. ¡Bien hecho!"
        )
 
    # Elegir una combinación al azar
    name, inc, per = random.choice(disponibles)
 
    # Armar el system prompt con la plantilla
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        client_name=name["name"],
        incident=inc["description"],
        personality_name=per["name"],
        personality_description=per["description"],
    )
 
    # Registrar la combinación como usada
    combo = supabase.table("scenario_combinations").insert({
        "learner_id":      learner_id,
        "client_name_id":  name["id"],
        "incident_id":     inc["id"],
        "personality_id":  per["id"],
    }).execute()
 
    # Crear sesión
    session = supabase.table("sessions").insert({
        "learner_id":     learner_id,
        "combination_id": combo.data[0]["id"],
        "system_prompt":  system_prompt,
        "status":         "active",
    }).execute()
 
    return SessionResponse(
        session_id=session.data[0]["id"],
        system=system_prompt,
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
 
    ultimo = request.messages[-1]
    supabase.table("messages").insert([
        {"session_id": request.session_id, "role": "user",      "content": ultimo.content},
        {"session_id": request.session_id, "role": "assistant", "content": content},
    ]).execute()
 
    return ChatResponse(message=content)


@app.patch("/session/{session_id}/complete")
async def complete_session(session_id: str, payload: dict = Depends(require_learner)):
    supabase.table("sessions").update({
        "status":   "completed",
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "revealed": True,
    }).eq("id", session_id).execute()
 
    # Traer datos de la combinación para revelar al learner
    sesion = supabase.table("sessions")\
        .select("""
            combination_id,
            scenario_combinations (
                client_names (name),
                incidents (description, category),
                personalities (name, description)
            )
        """)\
        .eq("id", session_id)\
        .single().execute()
 
    combo = sesion.data.get("scenario_combinations", {})
    return {
        "revealed": {
            "client_name": combo.get("client_names", {}).get("name"),
            "incident":    combo.get("incidents", {}).get("description"),
            "category":    combo.get("incidents", {}).get("category"),
            "personality": combo.get("personalities", {}).get("name"),
        }
    }

# Admin: user administration

@app.post("/admin/learners")
async def create_learner(learner: LearnerIn, payload: dict = Depends(require_admin)):
    """Crear un solo learner."""
    result = await create_learner_account(learner)
    return result
 
 
@app.post("/admin/learners/bulk")
async def create_learners_bulk(
    file: UploadFile = File(...),
    payload: dict = Depends(require_admin)
):
    """
    Crear múltiples learners desde un archivo Excel.
    Columnas requeridas: full_name, email, cohort
    Columna opcional:    password (si no está, se genera automáticamente)
 
    El admin descarga el resultado con emails y contraseñas generadas.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .xlsx o .xls")
 
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo Excel")
 
    # Validar columnas requeridas
    required = {"full_name", "email", "cohort"}
    missing  = required - set(df.columns.str.lower())
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Columnas faltantes en el Excel: {', '.join(missing)}"
        )
 
    df.columns = df.columns.str.lower()
 
    results = []
    for _, row in df.iterrows():
        learner = LearnerIn(
            email=str(row["email"]).strip(),
            full_name=str(row["full_name"]).strip(),
            cohort=int(row["cohort"]),
            password=str(row["password"]).strip() if "password" in df.columns and pd.notna(row.get("password")) else None,
        )
        result = await create_learner_account(learner)
        results.append(result)
 
    created = [r for r in results if r["status"] == "created"]
    failed  = [r for r in results if r["status"] == "failed"]
 
    return {
        "total":   len(results),
        "created": len(created),
        "failed":  len(failed),
        "results": results,   # incluye contraseñas generadas — guardar antes de cerrar
    }
 
 
@app.get("/admin/learners")
async def list_learners(payload: dict = Depends(require_admin)):
    result = supabase.table("profiles")\
        .select("id, email, full_name, cohort, active, created_at")\
        .eq("role", "learner")\
        .order("cohort", desc=True)\
        .order("full_name")\
        .execute()
    return result.data
 
 
@app.patch("/admin/learners/{learner_id}")
async def update_learner(learner_id: str, updates: dict, payload: dict = Depends(require_admin)):
    allowed = {"full_name", "cohort", "active"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    result = supabase.table("profiles").update(filtered).eq("id", learner_id).execute()
    return result.data[0]
 
 
# ── Admin: gestión de catálogos ───────────────────────────────────────────────
 
@app.get("/admin/catalog/names")
async def list_names(payload: dict = Depends(require_admin)):
    return supabase.table("client_names").select("*").order("name").execute().data
 
@app.post("/admin/catalog/names")
async def add_name(item: ClientNameIn, payload: dict = Depends(require_admin)):
    result = supabase.table("client_names").insert({
        "name": item.name, "created_by": payload["sub"]
    }).execute()
    return result.data[0]
 
@app.patch("/admin/catalog/names/{item_id}")
async def toggle_name(item_id: str, updates: dict, payload: dict = Depends(require_admin)):
    result = supabase.table("client_names").update({"active": updates.get("active", True)}).eq("id", item_id).execute()
    return result.data[0]
 
 
@app.get("/admin/catalog/incidents")
async def list_incidents(payload: dict = Depends(require_admin)):
    return supabase.table("incidents").select("*").order("category").execute().data
 
@app.post("/admin/catalog/incidents")
async def add_incident(item: IncidentIn, payload: dict = Depends(require_admin)):
    result = supabase.table("incidents").insert({
        "description": item.description,
        "category":    item.category,
        "created_by":  payload["sub"],
    }).execute()
    return result.data[0]
 
@app.patch("/admin/catalog/incidents/{item_id}")
async def toggle_incident(item_id: str, updates: dict, payload: dict = Depends(require_admin)):
    result = supabase.table("incidents").update({"active": updates.get("active", True)}).eq("id", item_id).execute()
    return result.data[0]
 
 
@app.get("/admin/catalog/personalities")
async def list_personalities(payload: dict = Depends(require_admin)):
    return supabase.table("personalities").select("*").order("name").execute().data
 
@app.post("/admin/catalog/personalities")
async def add_personality(item: PersonalityIn, payload: dict = Depends(require_admin)):
    result = supabase.table("personalities").insert({
        "name":        item.name,
        "description": item.description,
        "created_by":  payload["sub"],
    }).execute()
    return result.data[0]
 
@app.patch("/admin/catalog/personalities/{item_id}")
async def toggle_personality(item_id: str, updates: dict, payload: dict = Depends(require_admin)):
    result = supabase.table("personalities").update({"active": updates.get("active", True)}).eq("id", item_id).execute()
    return result.data[0]

# Admin:Reports

@app.get("/admin/sessions")
async def list_sessions(payload: dict = Depends(require_admin)):
    result = supabase.table("sessions")\
        .select("""
            id, status, started_at, ended_at,
            profiles:learner_id (full_name, email, cohort),
            scenario_combinations (
                client_names (name),
                incidents (description),
                personalities (name)
            )
        """)\
        .order("started_at", desc=True)\
        .execute()
    return result.data

@app.get("/admin/learners/template")
async def download_learners_template(payload: dict = Depends(require_admin)):
    """
    Genera y descarga el archivo Excel plantilla para la carga masiva de learners.
    Las columnas coinciden exactamente con lo que espera POST /admin/learners/bulk.
    """
    df = pd.DataFrame(columns=["full_name", "email", "cohort", "password"])
 
    # Filas de ejemplo — el admin las borra y pone sus datos reales
    df.loc[0] = ["Juan Pérez",  "juan.perez@generacion.org",  9, ""]
    df.loc[1] = ["María López", "maria.lopez@generacion.org", 9, ""]
 
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Learners")
 
        # Ajustar ancho de columnas para que se vea bien al abrir el archivo
        worksheet = writer.sheets["Learners"]
        worksheet.column_dimensions["A"].width = 25  # full_name
        worksheet.column_dimensions["B"].width = 32  # email
        worksheet.column_dimensions["C"].width = 10  # cohort
        worksheet.column_dimensions["D"].width = 16  # password
 
    buffer.seek(0)
 
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=plantilla_learners.xlsx"
        },
    )