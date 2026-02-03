import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Goku Backend API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Goku Backend is ONLINE", "status": "Dragon Ball Z vibes active"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("type") == "stop":
                logger.info("Received termination signal from client")
                # Logic to interrupt the active LiteRouter task would go here
                await manager.send_personal_message(json.dumps({"type": "status", "content": "Action Terminated"}), websocket)
                continue

            # Standard chat logic
            user_text = msg.get("content")
            logger.info(f"Received message: {user_text}")
            
            # Simulate thought process transparency
            await manager.send_personal_message(json.dumps({"type": "thought", "content": "1. Analyzing prompt..."}), websocket)
            await asyncio.sleep(0.5)
            
            # Simulate streaming response
            await manager.send_personal_message(json.dumps({"type": "content", "content": "Goku is processing your request..."}), websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
