# api/main.py

import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from core.config import get_config
from core.database import init_db
from api.routes import satellites, observations, intelligence
from api.websockets import manager
from workers.scheduler import Scheduler
from workers.receiver_worker import ReceiverWorker

config = get_config()
logger = logging.getLogger("api")

# Use ORJSONResponse for default to speed up all JSON responses

app = FastAPI(
    title="Satellite Intelligence System [SIS-PRO]",
    description="Proprietary SIGINT & Orbital Analysis Framework",
    version="2.0.0",
    default_response_class=ORJSONResponse
)

# CORS (Allow local dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(satellites.router)
app.include_router(observations.router)
app.include_router(intelligence.router)

# Global Worker Instances
receiver_worker = None
scheduler = None

@app.on_event("startup")
async def startup_event():
    """System Bootstrap"""
    global receiver_worker, scheduler
    
    logger.info("System Startup Initiated...")

    # 1. Init DB
    try:
        init_db()
        logger.info("Database Initialized.")
    except Exception as e:
        logger.error(f"Database Init Failed: {e}")

    # 2. Start Receiver Worker (Isolated Process)
    # Only start if enabled in config
    if config.receiver.enabled:
        try:
            receiver_worker = ReceiverWorker(config.receiver)
            receiver_worker.start()
            logger.info("Receiver Worker Started.")
        except Exception as e:
            logger.error(f"Receiver Worker Start Failed: {e}")

    # 3. Start Scheduler (Async Task Manager)
    try:
        scheduler = Scheduler(receiver_worker, manager)
        asyncio.create_task(scheduler.run())
        logger.info("Scheduler Started.")
    except Exception as e:
        logger.error(f"Scheduler Start Failed: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    global receiver_worker, scheduler
    if scheduler:
        scheduler.stop()
    if receiver_worker:
        receiver_worker.stop()
    logger.info("System Shutdown Complete.")

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Unified WebSocket Endpoint.
    Client sends JSON to subscribe: {"action": "subscribe", "topics": ["spectrum", "alerts"]}
    """
    # Default subscription
    await manager.connect(websocket, topics=["alerts"]) # Auto-subscribe to alerts 

    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle client commands
            if isinstance(data, dict):
                if data.get("action") == "subscribe":
                    topics = data.get("topics", [])
                    # In a real implementation we would update the subscription list for this socket
                    # For now, we just add them to the manager's lists via a simplified re-connect logic
                    # or extend manager to handle dynamic subscriptions.
                    # Current Manager.connect appends. So we can just call it again with new topics.
                    # Ideally, Manager should handle duplicate prevention.
                    await manager.connect(websocket, topics)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket)

@app.get("/")
def health_check():
    return {
        "system": "SIS-PRO",
        "status": "OPERATIONAL",
        "mode": config.environment,
        "receiver": "ACTIVE" if receiver_worker and receiver_worker.process.is_alive() else "OFFLINE"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.api_host, port=config.api_port)
