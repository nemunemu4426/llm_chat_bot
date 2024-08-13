from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from odmantic import AIOEngine
from openai import OpenAI
from dependencies import verify_ms_principal_id, get_db, get_openai_client
from models import User, Thread
import json

router = APIRouter(
    prefix="/threads",
    tags=["threads"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", status_code=201)
async def create_thread(
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)],
    client: Annotated[OpenAI, Depends(get_openai_client)]
):
    user = await db.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    thread = client.beta.threads.create()

    user.threads.append(Thread(id=thread.id, last_message=""))
    await db.save(user)

    return user


@router.get("/{thread_id}")
async def get_thread_messages(
    thread_id,
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)],
    client: Annotated[OpenAI, Depends(get_openai_client)]
):
    user = await db.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    if thread_id not in [thread.id for thread in user.threads]:
        raise HTTPException(status_code=403, detail="Unauthorized")    

    messages = client.beta.threads.messages.list(
        thread_id=thread_id
    )

    data = json.loads(messages.model_dump_json(indent=2))

    return data["data"]
