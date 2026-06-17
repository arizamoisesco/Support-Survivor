# auth.py
import os
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from jose import jwt, JWTError

def get_supabase() -> Client:
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY"),
    )

supabase: Client = get_supabase()
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            os.getenv("SUPABASE_JWT_SECRET"),
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

def require_admin(payload: dict = Security(verify_token)) -> dict:
    user_id = payload.get("sub")
    result = supabase.table("profiles").select("role").eq("id", user_id).single().execute()
    if not result.data or result.data["role"] != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return payload

def require_learner(payload: dict = Security(verify_token)) -> dict:
    return payload