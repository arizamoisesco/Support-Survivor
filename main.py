import json
import asyncio 
import os
import boto3
import random

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
#from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_aws import ChatBedrock
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Configuration app

app = FastAPI(title="Chat Bedrock API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    #allow_origins=["*"],
    #allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cargar variables de entorno desde el archivo .env
load_dotenv()

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

# Pydantic model

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    # This part allow change the system prompt since from the frontend
    system: str | None = None

class ChatResponse(BaseModel):
    message: str
    system: str

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

def random_stage_system_promt(
        client_names: tuple[str], 
        incidents: tuple[str], 
        personalities:tuple[str]
) -> str:
    actual_incidents:str = random.choice(incidents)
    actual_personality:str = random.choice(personalities)
    client_name:str = random.choice(client_names)

    system_prompt:str = f"""
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
    """

    return system_prompt

def build_langchain_messages( 
    messages: list[ChatMessage],
    system_prompt: str | None = None
) -> list:
    """"
    Convert frontend history messages to Langchain format, 
    truncate if history exceeds limits and add system prompt if provided.
    """

    result = [SystemMessage(content=system_prompt or SYSTEM_PROMPT)]

    #Truncate history if exceeds limits
    if len(messages) > MAX_HISTORY_TURNS * 2: # *2 because each turn has user + assistant message
        messages = messages[-MAX_HISTORY_TURNS * 2:]

    for message in messages:
        if message.role == "user":
            result.append(HumanMessage(content=message.content))
        elif message.role == "assistant":
            result.append(AIMessage(content=message.content))
        else:
            raise ValueError(f"Invalid message role: {message.role}")

    return result

# Endpoints
@app.get("/")
def read_root():
    return {"message": "¡Hola! Esta es la API de simulación de soporte TI."}

@app.post("/chat", response_model=ChatResponse)
async def post_message(request: ChatRequest):
    # Process the posted message (e.g., send it to the AI model)
    if not request.messages:
        raise HTTPException(status_code=400, detail="Requeried one message")
    
    system_promt = request.system or random_stage_system_promt(client_names,incidents, personalities)
    
    lc_message = build_langchain_messages(request.messages, system_promt)
    llm = get_llm()

    response, _ = await asyncio.gather( 
        llm.ainvoke(lc_message),
        asyncio.sleep(TYPING_DELAY),
    )

    return ChatResponse(message=response.content)


@app.get("/health")
async def health():
    return {"status": "ok"}