import time
import random
import os
import threading
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import boto3

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Cliente boto3 compartido para ambos modelos
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

# Reemplaza ChatGoogleGenerativeAI → Claude 3.5 Sonnet (orquestador/evaluador)
llm = ChatBedrock(
    #model_id="anthropic.claude-3-5-sonnet-20241022-v2:0", 
    #model_id="google.gemma-3-12b-it", # no funciona para el rol  play ya que no tiene soporte de chat (converse) por ahora, aunque es un modelo más potente y económico que Claude 3.5 Sonnet
    model_id="meta.llama3-70b-instruct-v1:0", # Este modelo es más caro pero tiene soporte de chat y es muy potente, ideal para el rol play, aunque hay que ajustar el prompt para que no se vuelva loco y se mantenga en el rol, ya que es un modelo muy grande y con mucha capacidad de generación, lo que puede hacer que se salga del rol si el prompt no es lo suficientemente claro y restrictivo.
    client=bedrock_client,
    model_kwargs={
        "temperature": 0.8,
        "max_tokens": 1000,
    }
)

# Reemplaza ChatOllama → Claude 3 Haiku (cliente simulado, más económico)
llm2 = ChatBedrock(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    client=bedrock_client,
    model_kwargs={
        "temperature": 0.8,
        "max_tokens": 500,
    }
)

# Nombres aleatorios para los clientes
client_names = ["Carlos Martinez", "Ana García", "Luis Rodríguez", "Marta López", "Jorge Hernández", "Sofía Martínez", "Pedro González", "Lucía Sánchez"]

# Bases de datos de simulacion
incidents = [
    "El servidor de correo no sincroniza y estoy perdiendo ventas.",
    "La VPN me desconecta cada 10 minutos y tengo una presentación en 1 hora.",
    "Mi pantalla se puso azul y perdí el informe trimestral no guardado."
]

personalidades = [
    "AGRESIVO: Gritas (en mayúsculas a veces), amenazas con llamar al supervisor, no entiendes razones técnicas.",
    "ASUSTADO: Crees que te van a despedir por esto, estás en pánico, pides ayuda desesperadamente.",
    "SARCÁSTICO: Te burlas de la competencia de TI, haces comentarios pasivo-agresivos, eres impaciente."
]

def wait_for_input_with_timeout(timeout=60):
    """
    Espera el input del usuario.
    Retorna el texto escrito, o None si se agotó el tiempo.
    """
    user_input = [None]      # Lista para poder modificarla desde el hilo
    input_received = threading.Event()  # Señal para comunicar entre hilos

    def get_input():
        user_input[0] = input("\nTu respuesta (soporte): ")
        input_received.set()  # Avisa que ya llegó el input

    # Hilo secundario esperando el input
    thread = threading.Thread(target=get_input, daemon=True)
    thread.start()

    # Hilo principal espera máximo `timeout` segundos
    input_received.wait(timeout=timeout)

    if input_received.is_set():
        return user_input[0]  # El usuario respondió a tiempo
    else:
        return None           # Se agotó el tiempo → dispara mensaje automático

def start_simulation():
    actual_incidents = random.choice(incidents)
    actual_personality = random.choice(personalidades)
    client_name = random.choice(client_names)

    print("\n" + "="*50)
    print(f"🔧 CONTEXTO PARA EL LEARNER (Ojos solamente):")
    print(f"Incidente: {actual_incidents}")
    print("="*50 + "\n")
    print("📢 CONECTANDO CON EL CLIENTE...\n")

    system_prompt = f"""
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

    chat_history = [SystemMessage(content=system_prompt)]

    while True:
        #start_time = time.time()
        #user_input = input("\nTu respuesta (soporte): ")
        #end_time = time.time()
        #total_time = end_time - start_time
        #print(f"Tiempo de al cliente fue: {total_time:.2f} segundos")
        # ⏱️ Espera el input con timeout de 60 segundos
        user_input = wait_for_input_with_timeout(timeout=60)

        if user_input.lower() in ["exit", "salir"]:
            print("\n--- SIMULACIÓN TERMINADA ---")
            break

        """
            if total_time > 30:
            print("El cliente esta escribiendo ...")
            print("El cliente se esta impacientado por la demora en tu respuesta)")
        """
        

        if user_input is None:
            #chat_history.append(AIMessage(content="¿Sigues ahí? Estoy esperando una respuesta..."))
            chat_history.append(HumanMessage(content="[ESPECIALISTA_INACTIVO]"))
            response = llm.invoke(chat_history)
            chat_history.append(response)
            print(f"Cliente ({client_name}): {response.content}")
            continue  # Vuelve a esperar respuesta del agente

        chat_history.append(HumanMessage(content=user_input))

        print("\n... (El cliente está leyendo y escribiendo. Espera) ...")
        time.sleep(2)

        # ✅ Igual que antes, solo cambia el modelo usado
        response = llm.invoke(chat_history)
        chat_history.append(response)

        print(f"\nCliente ({client_name}): {response.content}")

        if ("gracias" in response.content.lower() or "adios" in response.content.lower()) and len(chat_history) > 6: # Necesito una mejor forma de terminarlo porque si el cliente esta siendo cortez y dice gracias o adios el incidente no ha acabado aún solo cuando ya le valide que si no necesita apoyo de nada más y confirmo que la se termina la simulación del chat.
            print("\n--- EL CLIENTE PARECE SATISFECHO. FIN DE LA SIMULACIÓN ---")
            break

if __name__ == "__main__":
    start_simulation()