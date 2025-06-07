import asyncio
import cv2
import json
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame
import fractions
from datetime import datetime
import logging

# Set up logging to see connection details
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomVideoStreamTrack(VideoStreamTrack):
    def __init__(self, camera_id):
        super().__init__()
        self.camera_id = camera_id
        self.cap = None
        self.frame_count = 0
        self.initialize_camera()
        
    def initialize_camera(self):
        """Initialize or reinitialize the camera"""
        if self.cap is not None:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            logger.error(f"Failed to open camera {self.camera_id}")
            return False
            
        # Set camera properties for better performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        logger.info(f"Camera {self.camera_id} initialized successfully")
        return True

    async def recv(self):
        try:
            self.frame_count += 1
            
            # Check if camera is still opened
            if not self.cap or not self.cap.isOpened():
                logger.warning("Camera not available, attempting to reinitialize...")
                if not self.initialize_camera():
                    # Return a black frame if camera fails
                    black_frame = VideoFrame.from_ndarray(
                        [[0] * 640 * 3] * 480, format="rgb24"
                    )
                    black_frame.pts = self.frame_count
                    black_frame.time_base = fractions.Fraction(1, 30)
                    return black_frame
            
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Failed to read frame from camera")
                # Try to reinitialize camera
                self.initialize_camera()
                # Return a black frame for now
                black_frame = VideoFrame.from_ndarray(
                    [[0] * 640 * 3] * 480, format="rgb24"
                )
                black_frame.pts = self.frame_count
                black_frame.time_base = fractions.Fraction(1, 30)
                return black_frame
                                     
            # Add timestamp to the frame
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.7, (0, 255, 0), 2, cv2.LINE_AA)
            
            # Add frame count
            cv2.putText(frame, f"Frame: {self.frame_count}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

            # Convert BGR to RGB for VideoFrame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            video_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
            video_frame.pts = self.frame_count
            video_frame.time_base = fractions.Fraction(1, 30)
            
            return video_frame
            
        except Exception as e:
            logger.error(f"Error in recv(): {e}")
            # Return a black frame on error
            black_frame = VideoFrame.from_ndarray(
                [[0] * 640 * 3] * 480, format="rgb24"
            )
            black_frame.pts = self.frame_count
            black_frame.time_base = fractions.Fraction(1, 30)
            return black_frame

    def cleanup(self):
        """Clean up camera resources"""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logger.info("Camera resources cleaned up")

class WebRTCServer:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.video_track = None
        self.running = False
        
    async def handle_single_connection(self, ip_address, port):
        """Handle a single WebRTC connection"""
        signaling = None
        pc = None
        
        try:
            logger.info(f"Setting up new connection on {ip_address}:{port}")
            
            # Create new signaling and peer connection for this client
            signaling = TcpSocketSignaling(ip_address, port)
            pc = RTCPeerConnection()
            
            # Create new video track for this connection
            self.video_track = CustomVideoStreamTrack(self.camera_id)
            pc.addTrack(self.video_track)

            # Create data channel
            data_channel = pc.createDataChannel("clicks", ordered=True)
            
            @data_channel.on("open")
            def on_data_channel_open():
                logger.info("Data channel opened - ready to receive click coordinates")

            @data_channel.on("close")
            def on_data_channel_close():
                logger.info("Data channel closed")

            @data_channel.on("message")
            def on_data_channel_message(message):
                try:
                    click_data = json.loads(message)
                    print(f"Received click data: {click_data}")
                    x = click_data.get("x", "")
                    y = click_data.get("y", "")
                    logger.info(f"Received click coordinates: x={x}, y={y}")
                    
                    # Add your click handling logic here
                    # Example: save coordinates, trigger actions, etc.
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing message: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

            # Connection state monitoring
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state: {pc.connectionState}")
                if pc.connectionState == "connected":
                    logger.info("WebRTC connection established successfully")
                elif pc.connectionState in ["disconnected", "failed", "closed"]:
                    logger.info(f"Connection ended: {pc.connectionState}")

            # Set up signaling
            await signaling.connect()
            logger.info("Signaling connected, creating offer...")

            # Create and send offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            await signaling.send(pc.localDescription)
            logger.info("Offer sent, waiting for answer...")

            # Wait for answer and handle signaling
            connection_established = False
            while self.running:
                try:
                    obj = await asyncio.wait_for(signaling.receive(), timeout=1.0)
                    
                    if isinstance(obj, RTCSessionDescription):
                        await pc.setRemoteDescription(obj)
                        logger.info("Remote description set - connection established")
                        connection_established = True
                        break
                    elif obj is None:
                        logger.info("Signaling ended by remote peer")
                        break
                        
                except asyncio.TimeoutError:
                    # Check if connection is still alive
                    if pc.connectionState in ["failed", "closed"]:
                        logger.info("Connection failed during signaling")
                        break
                    continue
                except Exception as e:
                    logger.error(f"Error during signaling: {e}")
                    break

            if connection_established and self.running:
                logger.info("Connection established, streaming video...")
                
                # Keep connection alive and monitor state
                while self.running and pc.connectionState not in ["failed", "closed", "disconnected"]:
                    await asyncio.sleep(1)
                
                logger.info(f"Connection ended with state: {pc.connectionState}")

        except Exception as e:
            logger.error(f"Error in connection handling: {e}")
        finally:
            # Clean up this connection
            logger.info("Cleaning up connection...")
            
            if self.video_track:
                self.video_track.cleanup()
                self.video_track = None
                
            if pc:
                await pc.close()
              
            if signaling:
                await signaling.close()
      
                    
            logger.info("Connection cleanup completed")

    async def run_server(self, ip_address, port):
        """Main server loop that handles multiple connections"""
        self.running = True
        connection_count = 0
        
        logger.info(f"Starting WebRTC server on {ip_address}:{port}")
        logger.info("Server will automatically restart after client disconnections")
        
        while self.running:
            try:
                connection_count += 1
                logger.info(f"\n--- Waiting for connection #{connection_count} ---")
                
                await self.handle_single_connection(ip_address, port)
                
                if self.running:
                    logger.info("Client disconnected, waiting for next connection...")
                    await asyncio.sleep(2)  # Brief pause before accepting new connections
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                if self.running:
                    logger.info("Restarting server in 5 seconds...")
                    await asyncio.sleep(5)

    def stop(self):
        """Stop the server"""
        self.running = False
        if self.video_track:
            self.video_track.cleanup()

async def main():
    ip_address = "0.0.0.0"  # Listen on all interfaces
    port = 9999
    camera_id = 0

    server = WebRTCServer(camera_id)
    
    try:
        await server.run_server(ip_address, port)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        server.stop()
        logger.info("Server stopped")

if __name__ == "__main__":
    asyncio.run(main())