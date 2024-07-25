from fastapi import FastAPI, APIRouter, Header, Depends, HTTPException, Body, UploadFile, File
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from odmantic import AIOEngine, Model
from typing import List, Annotated, Union
from openai import AzureOpenAI
import time
import jwt
import json
import os
import uuid

if os.getenv("ENV", "development") != "production":
    import dotenv
    dotenv.load_dotenv()

router = APIRouter()

class AssistantData(BaseModel):
    name: str
    instructions: str

class Assistant(AssistantData):
    id: str

class Thread(BaseModel):
    id: str
    last_message: str

class VectorStore(BaseModel):
    id: str
    filenames: List[str]

class MessageData(BaseModel):
    role: str
    content: str

class User(Model):
    name: str
    email: str
    principal_id: str
    assistants: List[Assistant] = []
    threads: List[Thread] = []
    vectorstores: List[VectorStore] = []

engine = AIOEngine()

client = AzureOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

async def verify_ms_access_token(x_ms_token_aad_access_token: Annotated[str, Header()] = os.getenv("DEFAULT_ACCESS_TOKEN")):
    return x_ms_token_aad_access_token


async def verty_ms_principal_id(x_ms_client_principal_id: Annotated[str, Header()] = os.getenv("DEFAULT_PRINCIPAL_ID")):
    return x_ms_client_principal_id


@router.get("/")
async def index():
    return FileResponse("static/index.html")


@router.post("/users/", status_code=201)
async def register_user(
    token: Annotated[str, Depends(verify_ms_access_token)],
    principal_id: Annotated[str, Depends(verty_ms_principal_id)]
):
    existing_user = await engine.find_one(User, User.principal_id == principal_id)
    if existing_user:
        raise HTTPException(status_code=409, detail="User with this principal ID already exists")

    decoded = jwt.decode(token, options={"verify_signature": False})
    name = decoded["name"]
    email = decoded["email"]
    user = User(name=name, email=email, principal_id=principal_id)
    await engine.save(user)
    return user


@router.get("/users/me")
async def get_users(
    principal_id: Annotated[str, Depends(verty_ms_principal_id)]    
):
    user = await engine.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    return user


@router.post("/assistants/", status_code=201)
async def create_assistant(
    principal_id: Annotated[str, Depends(verty_ms_principal_id)],
    assistant_data: AssistantData = Body()
):
    user = await engine.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")
    
    assistant = client.beta.assistants.create(
        name=assistant_data.name,
        instructions=assistant_data.instructions,
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        tools=[{"type": "file_search"}],
    )

    user.assistants.append(Assistant(name=assistant_data.name, instructions=assistant_data.instructions, id=assistant.id))
    await engine.save(user)

    return user


@router.put("/assistants/{assistant_id}")
async def update_assistant(
    assistant_id,
    principal_id: Annotated[str, Depends(verty_ms_principal_id)],
    assistant_data: AssistantData = Body()    
):
    user = await engine.find_one(User, User.principal_id == principal_id)
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
    await engine.save(user)

    return user


@router.post("/threads/", status_code=201)
async def create_thread(
    principal_id: Annotated[str, Depends(verty_ms_principal_id)]    
):
    user = await engine.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    thread = client.beta.threads.create()

    user.threads.append(Thread(id=thread.id, last_message=""))
    await engine.save(user)

    return user


@router.get("/threads/{thread_id}")
async def get_thread_messages(
    thread_id,
    principal_id: Annotated[str, Depends(verty_ms_principal_id)]     
):
    user = await engine.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    if thread_id not in [thread.id for thread in user.threads]:
        raise HTTPException(status_code=403, detail="Unauthorized")    

    messages = client.beta.threads.messages.list(
        thread_id=thread_id
    )

    data = json.loads(messages.model_dump_json(indent=2))

    return data["data"]


@router.post("/assistants/{assistant_id}/threads/{thread_id}")
async def chat(
    assistant_id,
    thread_id,
    principal_id: Annotated[str, Depends(verty_ms_principal_id)],
    message_data: MessageData = Body()
):
    user = await engine.find_one(User, User.principal_id == principal_id)
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
    await engine.save(user)

    return user


@router.post("/vectorstores/", status_code=201)
async def insert_datasource(
    principal_id: Annotated[str, Depends(verty_ms_principal_id)],
    files: List[UploadFile] = File()
):
    user = await engine.find_one(User, User.principal_id == principal_id)
    if not user:
        raise HTTPException(404, detail="User with this principal ID is not registered")

    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No upload file sent")
    
    vector_store = client.beta.vector_stores.create(name=f"{uuid.uuid4()}-vectorstore")
    file_streams = [(file.filename, await file.read()) for file in files]
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
    )

    user.vectorstores.append(VectorStore(id=vector_store.id, filenames=[file.filename for file in files]))
    await engine.save(user)

    return user


@router.patch("/assistants/{assistant_id}/vectorstores/{vectorestore_id}")
async def update_assistant(
    assistant_id,
    vectorstore_id,
    principal_id: Annotated[str, Depends(verty_ms_principal_id)]    
):
    user = await engine.find_one(User, User.principal_id == principal_id)
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

def configure_app(app: FastAPI):
    app.mount("/static", StaticFiles(directory="static", html=True), name="static")
    app.include_router(router, prefix="")


def create_app():
    app = FastAPI()
    configure_app(app)
    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=30303)