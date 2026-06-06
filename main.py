import json
import asyncio 
import os
import boto3
from typing import AsyncGenerator
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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

# System prompt: AI role
SYSTEM_PROMPT = """Eres un cliente que llama a soporte técnico.
Estás frustrado porque llevas tiempo con un problema sin resolver.
Eres impaciente, a veces interrumpes, y a veces das información incompleta.
Solo das más detalles cuando el agente de soporte te hace las preguntas correctas.
Responde siempre en español. Tus respuestas son cortas, de 1-3 oraciones.
Problema actual: No puedes acceder a tu correo corporativo desde ayer."""

# Limit of history messages to keep in context
MAX_HISTORY_TURNS = 20 # 20 for users / assistants, 40 for system messages

# Pydantic model

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    # This part allow change the system prompt since from the frontend
    system: str | None = None

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
        streaming = True,
    )

# Helper

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

async def stream_bedrock(messages: list) -> AsyncGenerator[str, None]:
    """"
    Generate SSE event: Send messages to Bedrock model and stream the response back as an async generator.
    SSE format: 'data: {chunk}\n\n'
    """
    llm = get_llm()

    try:
        async for chunk in llm.astream(messages):
            token = chunk.content
            if token:
                # Send each token with a SSE event format
                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"
                # A bit pause for no overhelm the buffer of client
                await asyncio.sleep(0)

        # Close event: The frontend knows that event close
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        # In case of error, send an error event
        error_payload = json.dumps({"error": str(e)})
        yield f"data: {payload}\n\n"


# Endpoints
@app.get("/")
def read_root():
    return {"message": "¡Hola! Esta es la API de simulación de soporte TI."}

@app.post("/chat")
def post_message(message: str):
    # Process the posted message (e.g., send it to the AI model)
    return {"message": f"Message received: {message}"}

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Endpoint to handle chat messages and stream the AI response back to the client.
    The frontend sends the entire chat history with each request, and optionally a custom system prompt.
    The answer is streamed back token by token as SSE events.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")
    
    lc_messages = build_langchain_messages(request.messages, request.system)

    return StreamingResponse(
        stream_bedrock(lc_messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X_Accel_Buffering": "no", # Disable buffering for nginx
        }
    )

@app.get("/health")
async def health():
    return {"status": "ok"}