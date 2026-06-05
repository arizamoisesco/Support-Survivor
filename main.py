from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "¡Hola! Esta es la API de simulación de soporte TI."}

@app.post("/chat")
def post_message(message: str):
    # Process the posted message (e.g., send it to the AI model)
    return {"message": f"Message received: {message}"}
