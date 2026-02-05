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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/config")
async def get_config():
    """Check which API keys are configured (return actual values for UI)."""
    return {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "HF_TOKEN": os.getenv("HF_TOKEN", ""),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    }

@app.post("/config")
async def update_config(config_data: dict):
    """Update .env with new API keys."""
    try:
        # For simplicity, we write directly to .env
        # In production, use a more robust config manager
        lines = []
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                lines = f.readlines()
        
        new_lines = []
        updated_keys = set()
        for line in lines:
            if "=" in line:
                key = line.split("=")[0].strip()
                if key in config_data:
                    new_lines.append(f"{key}={config_data[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        for key, value in config_data.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")
        
        with open(".env", "w") as f:
            f.writelines(new_lines)
            
        # Refresh environment
        load_dotenv(override=True)
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

import json
import asyncio
from .lite_router import router
from .mcp_manager import mcp_manager
from .memory import memory

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            
            if msg.get("type") == "stop":
                logger.info("Received termination signal")
                await manager.send_personal_message(json.dumps({"type": "status", "content": "Action Terminated"}), websocket)
                continue

            user_text = msg.get("content", "")
            if not user_text: continue

            # 1. Thought Process: Retrieval
            await manager.send_personal_message(json.dumps({
                "type": "thought", 
                "content": "Searching vector memory for relevant context..."
            }), websocket)
            context = await memory.search_memory(user_text)
            
            # 2. Thought Process: Tool Discovery
            await manager.send_personal_message(json.dumps({
                "type": "thought", 
                "content": "Checking available MCP tools (Git, Search, Shell)..."
            }), websocket)
            all_tools = await mcp_manager.get_all_tools()

            # 3. Execution & Streaming
            messages = [{"role": "user", "content": user_text}]
            
            await manager.send_personal_message(json.dumps({
                "type": "thought", 
                "content": "Routing to best model (Hybrid Online/Offline)..."
            }), websocket)

            # In a real assistant, we'd loop for tool calls here. 
            # For this MVP, we simulate the logic flow.
            stream = await router.get_response(model="gpt-4o", messages=messages, stream=True)
            
            async for chunk in stream:
                if hasattr(chunk, 'choices') and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    await manager.send_personal_message(json.dumps({
                        "type": "content", 
                        "content": content
                    }), websocket)
            
            # 4. Finalizing
            await memory.add_memory(user_text, {"type": "user_query"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in websocket loop: {str(e)}")
        await manager.send_personal_message(json.dumps({"type": "error", "content": str(e)}), websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
