import time
import random
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Cargar variables de entorno desde el archivo .env
load_dotenv()

#Configurando la API key 
#os.environ["GOOGLE_API_KEY"] = ""
api_key_gemmini = os.getenv("GOOGLE_API_KEY")
print(f"Usando la API Key: {api_key_gemmini}")

# Configuración del modelo de Gemmini 2.5
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=api_key_gemmini,
    temperature=0.8, # Temperatura alta para mayor variabilidad en los estados de animo
)

# Hay que definir nombres aleatorios para los clientes.
client_names = ["Carlos", "Ana", "Luis", "Marta", "Jorge", "Sofía", "Pedro", "Lucía"]

#Bases de datos de simulacion
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

def start_simulation():
    actual_incidents = random.choice(incidents)
    actual_personality = random.choice(personalidades)
    client_name = random.choice(client_names)

    print("\n" + "="*50)
    print(f"🔧 CONTEXTO PARA EL LEARNER (Ojos solamente):")
    print(f"Incidente: {actual_incidents}")
    print("="*50 + "\n")
    print("📢 CONECTANDO CON EL CLIENTE...\n")

    # 3. Diseño del Prompt (El "Cerebro" del Chatbot)
    system_prompt = f"""
    ESTÁS EN UN ROL DE SIMULACIÓN (ROLEPLAY).
    Eres un cliente contactando a soporte TI.
    
    TU PERFIL:
    - Nombre: {client_name}
    - Incidente: {actual_incidents}
    - Personalidad: {actual_personality}
    
    REGLAS DE COMPORTAMIENTO:
    1. NO eres un asistente de IA. Eres un humano frustrado.
    2. Empieza la conversación muy molesto o alterado según tu personalidad.
    3. NO aceptes soluciones técnicas complejas de inmediato.
    4. CRITERIO DE DESESCALADA: Solo si el agente (usuario) muestra EMPATÍA real, valida tus sentimientos Y ofrece una solución clara, bajarás el tono.
    5. Si el agente es frío, técnico o robótico, aumenta tu molestia.
    6. Mantén respuestas breves (como en un chat real).
    """

    #print(system_prompt)
    chat_history = [SystemMessage(content=system_prompt)]

    #Mensaje inicial del cliente (generado por la IA para arrancar)
    print("El cliente esta en linea.\n")
    greeted_support_specialist = input("Ingrese su saludo inicial (soporte): ")
    print(type(greeted_support_specialist))
    initial_response = llm.invoke(greeted_support_specialist) #Considero que aqui esta el problema # Aqui debe iniciar la conversación el especialista de soporte TI
    chat_history.append(initial_response)
    print(f"Cliente: {initial_response.content}")

    while True:
        user_input = input("\nTu respuesta (soporte): ")

        #Salida de emergencia para pruebas
        if user_input.lower() in ["exit", "salir"]:
            break

        chat_history.append(HumanMessage(content=user_input))

        #La lógica para el tiempo de espera
        print("\n... (El cliente está leyendo y escribiendo. Espera 1 minuto) ...")
        time.sleep(2)

        response = llm.invoke(chat_history)
        chat_history.append(response)

        print(f"\nCliente: {response.content}")

        if "gracias" in response.content.lower() and len(chat_history) > 6: # Aqui termina el roleplay si el cliente dice gracias, es importante tener más posibles palabras de cierre para que sea más natural.
            print("\n--- EL CLIENTE PARECE SATISFECHO. FIN DE LA SIMULACIÓN ---")
            break

if __name__ == "__main__":
    start_simulation()
