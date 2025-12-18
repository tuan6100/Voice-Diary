
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from user_api.cores.config import settings
from user_api.cores.database import init_db
from user_api.router.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Connecting to Database...")
    await init_db()
    print("Database Connected!")
    yield

    print("Shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "user-manager-api"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)