from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import Annotated, List
from odmantic import AIOEngine
from openai import OpenAI
from dependencies import verify_ms_principal_id, get_db, get_openai_client
from models import User, VectorStore
import uuid

router = APIRouter(
    prefix="/vectorstores",
    tags=["vectorstores"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", status_code=201)
async def insert_datasource(
    principal_id: Annotated[str, Depends(verify_ms_principal_id)],
    db: Annotated[AIOEngine, Depends(get_db)],
    client: Annotated[OpenAI, Depends(get_openai_client)],
    files: List[UploadFile] = File()
):
    user = await db.find_one(User, User.principal_id == principal_id)
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
    await db.save(user)

    return user
