from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from dependencies import verify_ms_access_token, verify_ms_principal_id, get_db
from models import User
from odmantic import AIOEngine
import jwt

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", status_code=201)
async def register_user(
    token: Annotated[str, Depends(verify_ms_access_token)],
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)]
):
    existing_user = await db.find_one(User, User.principal_id == principal_id)
    if existing_user:
        raise HTTPException(status_code=409, detail="User with this principal ID already exists")

    decoded = jwt.decode(token, options={"verify_signature": False})
    name = decoded["name"]
    email = decoded["email"]
    user = User(name=name, email=email, principal_id=principal_id)
    await db.save(user)
    return user

@router.get("/me")
async def get_users(
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)]
):
    user = await db.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    return user
