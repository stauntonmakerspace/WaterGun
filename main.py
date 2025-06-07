import asyncio
import cv2
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCDataChannel
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data models
class ConnectRequest(BaseModel):
    device_ip: str

class SprayerCommand(BaseModel):
    pan: float  # 0-100 percentage
    tilt: float  # 0-100 percentage
    fire: bool

class StatusResponse(BaseModel):
    connection_state: str
    video_ready: bool
    control_channel_ready: bool
    frame_count: int

# Global state
class ServerState:
    def __init__(self):
        self.pc: Optional[RTCPeerConnection] = None
        self.signaling: Optional[TcpSocketSignaling] = None
        self.video_track: Optional[MediaStreamTrack] = None
        self.control_channel: Optional[RTCDataChannel] = None
        self.connection_state = "Disconnected"
        self.video_ready = False
        self.control_channel_ready = False
        self.frame_count = 0
        self.current_frame: Optional[np.ndarray] = None
        self.device_ip: Optional[str] = None
        self.websocket_clients = set()

state = ServerState()
app = FastAPI(title="Sprayer Control Backend")

# Add CORS middleware to handle cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoReceiver:
    def __init__(self):
        self.frame_count = 0

    async def handle_track(self, track):
        logger.info("Starting video track handler")
        try:
            while True:
                try:
                    frame = await asyncio.wait_for(track.recv(), timeout=5.0)
                    self.frame_count += 1
                    state.frame_count = self.frame_count
                    
                    logger.info(f"Received frame {self.frame_count}")
                    
                    if isinstance(frame, VideoFrame):
                        frame_array = frame.to_ndarray(format="bgr24")
                    elif isinstance(frame, np.ndarray):
                        frame_array = frame
                    else:
                        logger.warning(f"Unexpected frame type: {type(frame)}")
                        continue
                    
                    # Add timestamp to the frame
                    current_time = datetime.now()
                    display_time = current_time - timedelta(seconds=55)
                    timestamp = display_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    cv2.putText(frame_array, timestamp, (10, frame_array.shape[0] - 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
                    
                    # Store current frame for HTTP streaming
                    state.current_frame = frame_array.copy()
                    
                    # Optionally save frames for debugging
                    if not os.path.exists("imgs"):
                        os.makedirs("imgs")
                    cv2.imwrite(f"imgs/received_frame_{self.frame_count}.jpg", frame_array)
                    
                    # Notify WebSocket clients of new frame
                    await self.notify_websocket_clients()
                    
                except asyncio.TimeoutError:
                    logger.debug("Timeout waiting for frame")
                    continue
                except Exception as e:
                    logger.error(f"Error processing frame: {e}")
                    if "Connection" in str(e):
                        break
                        
        except Exception as e:
            logger.error(f"Error in video track handler: {e}")
        finally:
            state.video_ready = False
            logger.info("Video track handler stopped")

    async def notify_websocket_clients(self):
        """Notify WebSocket clients of new frame availability"""
        if state.websocket_clients:
            message = {
                "type": "frame_update",
                "frame_count": state.frame_count,
                "timestamp": datetime.now().isoformat()
            }
            disconnected = set()
            for websocket in state.websocket_clients:
                try:
                    await websocket.send_text(json.dumps(message))
                except:
                    disconnected.add(websocket)
            
            # Remove disconnected clients
            state.websocket_clients -= disconnected

video_receiver = VideoReceiver()

async def setup_webrtc_connection(device_ip: str):
    """Set up WebRTC connection to camera device"""
    try:
        logger.info(f"Setting up WebRTC connection to {device_ip}")
        
        # Create signaling connection
        state.signaling = TcpSocketSignaling(device_ip, 9999)
        await state.signaling.connect()
        
        # Create peer connection
        state.pc = RTCPeerConnection()
        
        @state.pc.on("track")
        def on_track(track):
            logger.info(f"Receiving {track.kind} track")
            if track.kind == "video":
                state.video_track = track
                state.video_ready = True
                asyncio.ensure_future(video_receiver.handle_track(track))

        @state.pc.on("datachannel")
        def on_datachannel(channel):
            logger.info(f"Data channel established: {channel.label}")
            state.control_channel = channel
            state.control_channel_ready = True
            
            @channel.on("message")
            def on_message(message):
                logger.info(f"Received message: {message}")

        @state.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state: {state.pc.connectionState}")
            state.connection_state = state.pc.connectionState
            if state.pc.connectionState == "connected":
                logger.info("WebRTC connection established successfully")

        # Wait for offer from sender
        logger.info("Waiting for offer from camera device...")
        offer = await state.signaling.receive()
        logger.info("Offer received, setting up connection")
        
        await state.pc.setRemoteDescription(offer)
        answer = await state.pc.createAnswer()
        await state.pc.setLocalDescription(answer)
        await state.signaling.send(state.pc.localDescription)
        
        logger.info("Answer sent, waiting for connection establishment")
        
        # Wait for connection to be established
        timeout = 30  # 30 seconds timeout
        start_time = asyncio.get_event_loop().time()
        while state.pc.connectionState != "connected":
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("Connection timeout")
            await asyncio.sleep(0.1)
        
        state.device_ip = device_ip
        logger.info("WebRTC connection established successfully")
        
    except Exception as e:
        logger.error(f"Failed to setup WebRTC connection: {e}")
        await cleanup_connection()
        raise

async def cleanup_connection():
    """Clean up WebRTC connection"""
    try:
        if state.pc:
            await state.pc.close()
        if state.signaling:
            await state.signaling.close()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        state.pc = None
        state.signaling = None
        state.video_track = None
        state.control_channel = None
        state.connection_state = "Disconnected"
        state.video_ready = False
        state.control_channel_ready = False
        state.frame_count = 0
        state.current_frame = None
        state.device_ip = None

async def send_control_command(command: SprayerCommand):
    """Send control command via WebRTC data channel"""
    if not state.control_channel or not state.control_channel_ready:
        raise HTTPException(status_code=400, detail="Control channel not ready")
    
    try:
        command_data = {
            "type": "sprayer_command",
            "pan": command.pan,
            "tilt": command.tilt,
            "fire": command.fire,
            "timestamp": datetime.now().isoformat()
        }
        
        state.control_channel.send(json.dumps(command_data))
        logger.info(f"Sent command: {command_data}")
        
    except Exception as e:
        logger.error(f"Failed to send control command: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send command: {e}")

def generate_frame_stream():
    """Generate video stream for HTTP streaming"""
    while True:
        if state.current_frame is not None:
            ret, buffer = cv2.imencode('.jpg', state.current_frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # Send a blank frame if no video available
            blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank_frame, "No Video Signal", (160, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            ret, buffer = cv2.imencode('.jpg', blank_frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# API Routes
@app.options("/api/{path:path}")
async def options_handler(path: str):
    """Handle OPTIONS requests for CORS preflight"""
    return {"message": "OK"}

@app.post("/api/connect")
async def connect_to_device(request: ConnectRequest):
    """Connect to camera device"""
    logger.info(f"Received connection request for device: {request.device_ip}")
    
    if state.connection_state == "Connected":
        logger.warning("Already connected to a device")
        raise HTTPException(status_code=400, detail="Already connected to a device")
    
    try:
        logger.info(f"Attempting to connect to camera device at {request.device_ip}")
        await setup_webrtc_connection(request.device_ip)
        logger.info("Successfully connected to camera device")
        return {"status": "connected", "device_ip": request.device_ip}
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Connection failed: {e}")

@app.post("/api/disconnect")
async def disconnect_from_device():
    """Disconnect from camera device"""
    logger.info("Received disconnect request")
    await cleanup_connection()
    logger.info("Successfully disconnected from device")
    return {"status": "disconnected"}

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get current connection status"""
    return StatusResponse(
        connection_state=state.connection_state,
        video_ready=state.video_ready,
        control_channel_ready=state.control_channel_ready,
        frame_count=state.frame_count
    )

@app.post("/api/sprayer/command")
async def send_sprayer_command(command: SprayerCommand):
    """Send sprayer control command"""
    await send_control_command(command)
    return {"status": "command_sent", "command": command.dict()}

@app.get("/api/video/stream")
async def video_stream():
    """HTTP video stream endpoint"""
    return StreamingResponse(
        generate_frame_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    state.websocket_clients.add(websocket)
    
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            # Echo back or handle specific messages if needed
            
    except WebSocketDisconnect:
        state.websocket_clients.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        state.websocket_clients.discard(websocket)

# Serve static files (Vue.js frontend)
frontend_dir = Path("dist")  # Assuming Vue.js builds to 'dist' directory
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    
    @app.get("/")
    async def serve_frontend():
        """Serve the Vue.js frontend"""
        index_file = frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        else:
            return {"message": "Frontend not built. Run 'npm run build' in the frontend directory."}
else:
    @app.get("/")
    async def serve_frontend():
        return {"message": "Frontend directory not found. Build the Vue.js app first."}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    # Ensure imgs directory exists
    os.makedirs("imgs", exist_ok=True)
    
    logger.info("Starting Sprayer Control Backend Server")
    logger.info("Server will be available at: http://localhost:8000")
    logger.info("API documentation at: http://localhost:8000/docs")
    
    # Run the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )