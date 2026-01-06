# api/websockets.py
import logging
from typing import List, Dict
from fastapi import WebSocket, WebSocketDisconnect
import orjson
import asyncio
import numpy as np

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections with Topic Subscription support.
    Uses ORJSON for high-performance serialization of NumPy arrays.
    """
    def __init__(self):
        # topic -> list of websockets
        self.active_connections: Dict[str, List[WebSocket]] = {
            "spectrum": [],
            "tracking": [],
            "alerts": []
        }

    async def connect(self, websocket: WebSocket, topics: List[str]):
        await websocket.accept()
        for topic in topics:
            if topic in self.active_connections:
                self.active_connections[topic].append(websocket)
            else:
                logger.warning(f"Client requested unknown topic: {topic}")

    def disconnect(self, websocket: WebSocket):
        for topic in self.active_connections:
            if websocket in self.active_connections[topic]:
                self.active_connections[topic].remove(websocket)

    async def broadcast(self, topic: str, data: dict):
        """
        Broadcast data to all subscribers of a topic.
        Optimized: Serializes once, sends bytes to many.
        """
        if topic not in self.active_connections or not self.active_connections[topic]:
            return

        # Pre-serialize for performance (CPU bound operation done once)
        # orjson handles numpy arrays natively!
        def default(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError
            
        try:
            message_bytes = orjson.dumps(data, default=default, option=orjson.OPT_SERIALIZE_NUMPY)
        except Exception:
             # Fallback if OPT_SERIALIZE_NUMPY is not sufficient for some nested structures
            message_bytes = orjson.dumps(data, default=default)


        # Broadcast
        dead_sockets = []
        for connection in self.active_connections[topic]:
            try:
                await connection.send_bytes(message_bytes)
            except RuntimeError: # Socket closed roughly
                dead_sockets.append(connection)
            except Exception as e:
                logger.error(f"WS Send Error: {e}")
                dead_sockets.append(connection)
        
        # Cleanup
        for ws in dead_sockets:
            self.disconnect(ws)

# Global Manager Instance
manager = ConnectionManager()
