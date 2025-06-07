import asyncio
import cv2
import json
import logging
from datetime import datetime
from typing import Optional
import fractions

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCDataChannel
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SprayerController:
    """Mock sprayer controller - replace with actual hardware interface"""
    
    def __init__(self):
        self.pan = 50.0  # Current pan position (0-100%)
        self.tilt = 50.0  # Current tilt position (0-100%)
        self.firing = False  # Firing state
        
    def set_position(self, pan: float, tilt: float):
        """Set sprayer pan/tilt position"""
        self.pan = max(0, min(100, pan))
        self.tilt = max(0, min(100, tilt))
        logger.info(f"Sprayer position set to Pan: {self.pan}%, Tilt: {self.tilt}%")
        
    def set_firing(self, firing: bool):
        """Set firing state"""
        self.firing = firing
        action = "FIRING" if firing else "STOPPED"
        logger.info(f"Sprayer {action}")
        
    def execute_command(self, command_data: dict):
        """Execute a sprayer command"""
        try:
            pan = command_data.get('pan', self.pan)
            tilt = command_data.get('tilt', self.tilt)
            fire = command_data.get('fire', self.firing)
            
            self.set_position(pan, tilt)
            self.set_firing(fire)
            
            # Here you would interface with actual hardware
            # For example:
            # self.hardware_interface.move_to(pan, tilt)
            # self.hardware_interface.set_fire(fire)
            
        except Exception as e:
            logger.error(f"Error executing sprayer command: {e}")

class CustomVideoStreamTrack(VideoStreamTrack):
    """Video stream track that captures from camera and adds overlay information"""
    
    def __init__(self, camera_id: int = 0, sprayer_controller: Optional[SprayerController] = None):
        super().__init__()
        self.cap = cv2.VideoCapture(camera_id)
        self.frame_count = 0
        self.sprayer_controller = sprayer_controller
        
        # Set camera properties for better quality
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_id}")
            
        logger.info(f"Camera {camera_id} opened successfully")

    async def recv(self):
        """Capture and return video frame"""
        self.frame_count += 1
        
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Failed to read frame from camera")
            # Return a blank frame instead of None
            frame = self.create_error_frame("Camera Error")
        else:
            # Add overlays to the frame
            frame = self.add_overlays(frame)
        
        # Convert BGR to RGB for WebRTC
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create VideoFrame
        video_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        video_frame.pts = self.frame_count
        video_frame.time_base = fractions.Fraction(1, 30)
        
        return video_frame
    
    def create_error_frame(self, message: str) -> cv2.Mat:
        """Create an error frame with a message"""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, message, (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return frame
    
    def add_overlays(self, frame: cv2.Mat) -> cv2.Mat:
        """Add timestamp and sprayer status overlays to the frame"""
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Add frame counter
        cv2.putText(frame, f"Frame: {self.frame_count}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        # Add sprayer status if available
        if self.sprayer_controller:
            status_y = frame.shape[0] - 80
            cv2.putText(frame, f"Pan: {self.sprayer_controller.pan:.1f}%", (10, status_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Tilt: {self.sprayer_controller.tilt:.1f}%", (10, status_y + 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Firing indicator
            fire_color = (0, 0, 255) if self.sprayer_controller.firing else (128, 128, 128)
            fire_text = "FIRING" if self.sprayer_controller.firing else "READY"
            cv2.putText(frame, fire_text, (10, status_y + 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, fire_color, 2)
            
            # Draw crosshair based on pan/tilt
            center_x = int((self.sprayer_controller.pan / 100.0) * frame.shape[1])
            center_y = int((self.sprayer_controller.tilt / 100.0) * frame.shape[0])
            
            # Draw crosshair
            crosshair_color = (0, 0, 255) if self.sprayer_controller.firing else (255, 255, 255)
            cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), crosshair_color, 2)
            cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), crosshair_color, 2)
            cv2.circle(frame, (center_x, center_y), 3, crosshair_color, -1)
        
        return frame
    
    def __del__(self):
        """Clean up camera resources"""
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

class CameraServer:
    """Main camera server class that handles WebRTC connections and sprayer control"""
    
    def __init__(self, ip_address: str = "127.0.0.1", port: int = 9999, camera_id: int = 0):
        self.ip_address = ip_address
        self.port = port
        self.camera_id = camera_id
        self.sprayer_controller = SprayerController()
        self.pc: Optional[RTCPeerConnection] = None
        self.signaling: Optional[TcpSocketSignaling] = None
        self.control_channel: Optional[RTCDataChannel] = None
        self.video_sender: Optional[CustomVideoStreamTrack] = None
        
    async def setup_webrtc_and_run(self):
        """Set up WebRTC connection and start streaming"""
        logger.info(f"Starting camera server on {self.ip_address}:{self.port}")
        
        # Create signaling and peer connection
        self.signaling = TcpSocketSignaling(self.ip_address, self.port)
        self.pc = RTCPeerConnection()
        
        # Create video track with sprayer controller
        self.video_sender = CustomVideoStreamTrack(self.camera_id, self.sprayer_controller)
        self.pc.addTrack(self.video_sender)
        
        # Create data channel for control commands
        self.control_channel = self.pc.createDataChannel("control")
        self.setup_data_channel_handlers()
        
        try:
            await self.signaling.connect()
            
            @self.pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state: {self.pc.connectionState}")
                if self.pc.connectionState == "connected":
                    logger.info("WebRTC connection established successfully")
                elif self.pc.connectionState == "failed":
                    logger.error("WebRTC connection failed")
                elif self.pc.connectionState == "disconnected":
                    logger.info("WebRTC connection disconnected")
            
            # Create and send offer
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)
            await self.signaling.send(self.pc.localDescription)
            logger.info("Offer sent, waiting for answer...")
            
            # Wait for answer
            while True:
                obj = await self.signaling.receive()
                if isinstance(obj, RTCSessionDescription):
                    await self.pc.setRemoteDescription(obj)
                    logger.info("Answer received, connection established")
                    break
                elif obj is None:
                    logger.warning("Signaling ended unexpectedly")
                    break
            
            # Keep connection alive
            logger.info("Streaming video and listening for commands...")
            while self.pc.connectionState in ["connecting", "connected"]:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in WebRTC setup: {e}")
            raise
        finally:
            await self.cleanup()
    
    def setup_data_channel_handlers(self):
        """Set up data channel event handlers"""
        @self.control_channel.on("open")
        def on_open():
            logger.info("Control data channel opened")
            
        @self.control_channel.on("message")
        def on_message(message):
            logger.info(f"Received control message: {message}")
            try:
                command_data = json.loads(message)
                if command_data.get("type") == "sprayer_command":
                    self.sprayer_controller.execute_command(command_data)
                    
                    # Send acknowledgment back
                    ack_message = {
                        "type": "command_ack",
                        "status": "executed",
                        "timestamp": datetime.now().isoformat(),
                        "position": {
                            "pan": self.sprayer_controller.pan,
                            "tilt": self.sprayer_controller.tilt,
                            "firing": self.sprayer_controller.firing
                        }
                    }
                    self.control_channel.send(json.dumps(ack_message))
                    
            except json.JSONDecodeError:
                logger.error("Invalid JSON in control message")
            except Exception as e:
                logger.error(f"Error processing control message: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up camera server")
        try:
            if self.pc:
                await self.pc.close()
            if self.signaling:
                await self.signaling.close()
            if self.video_sender:
                # VideoStreamTrack cleanup is handled by its destructor
                pass
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Camera Server with Sprayer Control")
    parser.add_argument("--ip", default="127.0.0.1", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=9999, help="Port to bind to")
    parser.add_argument("--camera", type=int, default=0, help="Camera ID")
    
    args = parser.parse_args()
    
    server = CameraServer(args.ip, args.port, args.camera)
    
    try:
        await server.setup_webrtc_and_run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    # Import numpy here to avoid issues if not installed
    import numpy as np
    asyncio.run(main())