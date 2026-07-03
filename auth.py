import os
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client

def get_supabase() -> Client:
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY"),
    )

supabase: Client = get_supabase()
security = HTTPBearer()

# Cliente que descarga y cachea las claves públicas de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
jwks_client = PyJWKClient(JWKS_URL)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    token = credentials.credentials
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],   # Supabase usa ES256 en proyectos nuevos
            audience="authenticated",
            leeway=10, # Tolerancie for 10 seg with clock diference
            options={"verify_exp": True},
        )
        return payload
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Token inválido: {str(e)}")


def require_admin(payload: dict = Security(verify_token)) -> dict:
    user_id = payload.get("sub")
    result = supabase.table("profiles").select("role").eq("id", user_id).single().execute()
    if not result.data or result.data["role"] != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return payload


def require_learner(payload: dict = Security(verify_token)) -> dict:
    return payload