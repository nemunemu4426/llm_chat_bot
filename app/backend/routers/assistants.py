from fastapi import APIRouter, Depends, Body, HTTPException
from typing import Annotated
from odmantic import AIOEngine
from openai import OpenAI
import time
from dependencies import verify_ms_principal_id, get_db, get_openai_client
from models import AssistantData, Assistant, User, MessageData

router = APIRouter(
    prefix="/assistants",
    tags=["assistants"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", status_code=201)
async def create_assistant(
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)],
    client: Annotated[OpenAI, Depends(get_openai_client)],
    assistant_data: AssistantData = Body()
):
    user = await db.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")
    
    assistant = client.beta.assistants.create(
        name=assistant_data.name,
        instructions=assistant_data.instructions,
        model="gpt-4o-mini",
        tools=[{"type": "file_search"}],
    )

    user.assistants.append(Assistant(name=assistant_data.name, instructions=assistant_data.instructions, id=assistant.id))
    await db.save(user)

    return user


@router.put("/{assistant_id}")
async def update_assistant(
    assistant_id,
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)],
    client: Annotated[OpenAI, Depends(get_openai_client)],
    assistant_data: AssistantData = Body()    
):
    user = await db.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    if assistant_id not in [assistant.id for assistant in user.assistants]:
        raise HTTPException(403, detail="Unauthorized")
    
    assistant = client.beta.assistants.update(
        assistant_id=assistant_id,
        name=assistant_data.name,
        instructions=assistant_data.instructions
    )
    
    assistant_index = user.assistants.index(next(filter(lambda assistant: assistant.id == assistant_id, user.assistants)))
    user.assistants[assistant_index].name = assistant_data.name
    user.assistants[assistant_index].instructions = assistant_data.instructions
    await db.save(user)

    return user

@router.post("/{assistant_id}/threads/{thread_id}")
async def chat(
    assistant_id,
    thread_id,
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)],
    client: Annotated[OpenAI, Depends(get_openai_client)],
    message_data: MessageData = Body()
):
    user = await db.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    if assistant_id not in [assistant.id for assistant in user.assistants] or \
    thread_id not in [thread.id for thread in user.threads]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role=message_data.role,
        content=message_data.content
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )

    run = client.beta.threads.runs.retrieve(
        thread_id=thread_id,
        run_id=run.id
    )

    status = run.status

    while status not in ["completed", "cancelled", "expired", "failed"]:
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id,run_id=run.id)
        status = run.status

    if status != "completed":
        raise HTTPException(500, detail=f"chat completion failed: {status}")

    thread_index = user.threads.index(next(filter(lambda thread: thread.id == thread_id, user.threads)))
    user.threads[thread_index].last_message = message_data.content
    await db.save(user)

    return user

@router.patch("/{assistant_id}/vectorstores/{vectorestore_id}")
async def update_assistant(
    assistant_id,
    vectorstore_id,
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)],
    client: Annotated[OpenAI, Depends(get_openai_client)]
):
    user = await db.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    if assistant_id not in [assistant.id for assistant in user.assistants] or \
    vectorstore_id not in [vectorstore.id for vectorstore in  user.vectorstores]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    assistant = client.beta.assistants.update(
        assistant_id=assistant_id,
        tool_resources={"file_search": {"vector_store_ids": [vectorstore_id]}},
    )    

    return user
