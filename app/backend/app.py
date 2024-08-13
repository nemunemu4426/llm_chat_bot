from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routers import users, assistants, threads, vectorstores
import os

if os.getenv("ENV", "development") != "production":
    import dotenv
    dotenv.load_dotenv()


router = APIRouter()
router.include_router(users.router, prefix="/api")
router.include_router(assistants.router, prefix="/api")
router.include_router(threads.router, prefix="/api")
router.include_router(vectorstores.router, prefix="/api")


@router.get("/")
async def index():
    return FileResponse("static/index.html")


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
    