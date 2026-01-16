
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import asyncio
import json
import threading
import os
from contextlib import asynccontextmanager
from terminal_session import TerminalSession

# Set paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, '../Frontend/dist')

# Global Node Instance
terminal_instance = None
active_websockets = []
loop = None

def broadcast_log(msg: str):
    # print(f"[TERM] {msg}") # Optional server-side logging
    for websocket in active_websockets:
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"type": "log", "data": msg}), 
                loop
            )

def broadcast_topo(data: dict):
    for websocket in active_websockets:
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"type": "topo", "data": data}), 
                loop
            )

@asynccontextmanager
async def lifespan(app: FastAPI):
    global terminal_instance, loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
        
    print(f"Initializing TerminalSession...")
    # Initialize Terminal Session
    terminal_instance = TerminalSession(
        log_callback=broadcast_log,
        topo_callback=broadcast_topo
    )
    print(f"TerminalSession Ready.")
    
    yield
    
    print("Shutting down...")
    # Cleanup logic if needed

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return JSONResponse({"status": "ok", "mode": "static_serving" if os.path.exists(DIST_DIR) else "backend_only"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message['type'] == 'command':
                cmd = message['data']
                if terminal_instance:
                    terminal_instance.write(cmd)
                    
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
    except Exception as e:
        print(f"WebSocket Error: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)

# Serve React App
# Verify dist directory exists to avoid errors if not built
if os.path.exists(DIST_DIR):
    print(f"Found React build at: {DIST_DIR}")
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="static")
else:
    print(f"Warning: React Build directory not found at {DIST_DIR}")
    print("Please run 'npm run build' in ../Frontend/")
    
    @app.get("/")
    async def root_warning():
        return JSONResponse({
            "error": "Frontend not built",
            "message": "Please run 'npm run build' in Web-Interface/Frontend directory.",
            "path_checked": DIST_DIR
        }, status_code=404)

if __name__ == "__main__":
    import sys
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}, using default 8000")
            
    print(f"Starting Backend on 0.0.0.0:{port}")
    print("Note: If accessing from another machine, ensure Windows Firewall allows python.exe")
    uvicorn.run(app, host="0.0.0.0", port=port)
