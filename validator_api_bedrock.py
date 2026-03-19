import boto3
import os
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    service_name="bedrock",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

response = client.list_foundation_models(byInferenceType="ON_DEMAND")

print(f"{'Proveedor':<15} {'Model ID':<55} {'Soporta Chat'}")
print("-" * 90)

for model in response["modelSummaries"]:
    # ✅ Esta es la clave: verificar si tiene CONVERSATIONAL en sus modos
    input_modes = model.get("inputModalities", [])
    response_modes = model.get("responseStreamingSupported", False)
    supported_use = model.get("modelLifecycle", {})
    
    # El campo clave para saber si soporta chat
    inference_types = model.get("inferenceTypesSupported", [])
    streaming = model.get("responseStreamingSupported", False)
    
    # Modelos con API Converse (chat) tienen esto en su ID o son de Anthropic/Meta/Mistral/Amazon
    supports_chat = any(provider in model["modelId"] for provider in [
        "anthropic", "meta", "mistral", "amazon.titan", "amazon.nova", "cohere"
    ])
    
    chat_label = "✅ Sí" if supports_chat else "❌ No"
    
    print(f"{model['providerName']:<15} {model['modelId']:<55} {chat_label}")



"""

import boto3
import os
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    # service_name='bedrock-runtime', # bedrock runtime  espara ejecución e invocar modelos
    service_name='bedrock', #Bedrock es para gestión de modelos, listar modelos, etc
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
)

# Listar los modelos disponibles en Bedrock
response = client.list_foundation_models(
    byInferenceType="ON_DEMAND"
)

for model in response["modelSummaries"]:
    print(f"Proveedor : {model['providerName']}")
    print(f"Nombre    : {model['modelName']}")
    print(f"Model ID  : {model['modelId']}")
    print("-" * 40)

"""    

"""
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage

llm = ChatBedrock(
    #model_id="anthropic.claude-3-haiku-20240307-v1:0",
    model_id="anthropic.claude-sonnet-4-6",
    client=client,
)

response = llm.invoke([HumanMessage(content="Hola, ¿funcionas?")])
print(response.content)
"""

