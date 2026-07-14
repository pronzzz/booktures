from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import redis.asyncio as redis_async
import json
from core.config import settings
from core.database import engine, Base
from routers import project_router

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lumina-Reader API")

# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173", # Vite dev default
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
import os

app.include_router(project_router.router, tags=["Projects"])

# Create generated_images directory if not exists
os.makedirs("generated_images", exist_ok=True)
app.mount("/generated", StaticFiles(directory="generated_images"), name="generated")

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    redis_client = redis_async.from_url(settings.REDIS_URL)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"task_progress:{task_id}")
    
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = json.loads(message["data"])
                await websocket.send_json(data)
                if data.get("status") in ["SUCCESS", "FAILURE", "completed"]:
                    break
            else:
                await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Websocket error: {e}")
    finally:
        await pubsub.unsubscribe(f"task_progress:{task_id}")
        await redis_client.aclose() if hasattr(redis_client, "aclose") else await redis_client.close()

@app.get("/")
def read_root():
    return {"message": "Welcome to Lumina-Reader API"}
