from fastapi import Header, HTTPException
from typing import Annotated
from openai import OpenAI
from odmantic import AIOEngine
import os

if os.getenv("ENV", "development") != "production":
    import dotenv
    dotenv.load_dotenv()

async def verify_ms_access_token(x_ms_token_aad_access_token: Annotated[str, Header()] = os.getenv("DEFAULT_ACCESS_TOKEN")):
    if not x_ms_token_aad_access_token:
        raise HTTPException(401, detail="Missing Token")
    return x_ms_token_aad_access_token


async def verify_ms_principal_id(x_ms_client_principal_id: Annotated[str, Header()] = os.getenv("DEFAULT_PRINCIPAL_ID")):
    if not x_ms_client_principal_id:
        raise HTTPException(401, detail="Missing principal ID")
    return x_ms_client_principal_id

async def get_openai_client():
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    return client

async def get_db():
    db = AIOEngine()
    try:
        yield db
    finally:
        pass
