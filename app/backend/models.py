from pydantic import BaseModel
from odmantic import Model
from typing import List

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
