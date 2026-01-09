import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# PON TU KEY AQUÍ
MI_API_KEY = os.getenv("GOOGLE_API_KEY")

print(f"Key tiene {len(MI_API_KEY)} caracteres: {MI_API_KEY[:20]}...")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=MI_API_KEY,
)

print(llm.invoke("Hola").content)