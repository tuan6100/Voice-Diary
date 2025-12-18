from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from audio_api.controllers.progress import router as progress_router
from audio_api.controllers.upload import router as upload_router
from audio_api.cores import injectable
from audio_api.cores.config import settings
from shared_messaging.producer import RabbitMQProducer


async def lifespan(app: FastAPI):
    print("Starting Audio API...")
    producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await producer.connect()
    injectable._Producer = producer
    yield
    print("Stopping Audio API...")
    await producer.close()
    injectable._Producer = None


app = FastAPI(
    title="Audio API",
    lifespan=lifespan,
    swagger_ui_parameters={"syntaxHighlight": {"theme": "nord"}}
)

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(progress_router, prefix="/api/v1/status", tags=["Upload"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "audio-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8002, reload=True)