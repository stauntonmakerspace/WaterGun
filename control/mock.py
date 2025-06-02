#!/usr/bin/env python3
"""
Mock Sprayer Device Server
Simulates a sprayer device that streams video from an MP4 file and receives control commands.

USAGE:
1. Start mock device: python mock_sprayer_device.py
2. In Vue.js app, set Device Address to "127.0.0.1" 
3. Click Connect - you should see:
   - UDP control connection established (port 5632)
   - WebRTC video stream connected (port 8080)
   - Real-time targeting crosshair on video
   - Command logging in console

Compatible with Tauri backend UDP command format: "tilt,pan,trigger,1"
"""

import asyncio
import cv2
import json
import logging
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import fractions
import argparse

# WebRTC imports
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCDataChannel
from aiortc.contrib.signaling import create_signaling
from av import VideoFrame

# WebSocket imports for signaling
import websockets
from websockets.server import serve

class MP4VideoStreamTrack(VideoStreamTrack):
    """Custom video track that streams from an MP4 file in a loop"""
    
    def __init__(self, video_path, fps=30):
        super().__init__()
        self.video_path = video_path
        self.fps = fps
        self.cap = None
        self.frame_count = 0
        self.total_frames = 0
        self.setup_video()
        
    def setup_video(self):
        """Initialize video capture"""
        if not Path(self.video_path).exists():
            print(f"Warning: Video file {self.video_path} not found. Using synthetic video.")
            self.cap = None
            return
            
        self.cap = cv2.VideoCapture(self.video_path)
        if self.cap.isOpened():
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            print(f"Loaded video: {self.video_path}")
            print(f"Total frames: {self.total_frames}, FPS: {actual_fps}")
        else:
            print(f"Failed to open video file: {self.video_path}")
            self.cap = None

    def create_synthetic_frame(self, width=640, height=480):
        """Create a synthetic test frame with timestamp and frame counter"""
        import numpy as np
        
        # Create a gradient background
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Create gradient effect
        for y in range(height):
            for x in range(width):
                frame[y, x] = [
                    int((x / width) * 255),  # Red gradient
                    int((y / height) * 255), # Green gradient
                    128  # Blue constant
                ]
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(frame, f"MOCK CAMERA", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, timestamp, (20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Frame: {self.frame_count}", (20, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add moving elements to simulate action
        circle_x = int((self.frame_count % 200) * (width / 200))
        cv2.circle(frame, (circle_x, height//2), 20, (0, 255, 255), -1)
        
        # Add targeting overlay if available (access parent device state)
        if hasattr(self, '_device_ref') and self._device_ref:
            device = self._device_ref
            target_x = int((device.current_target['x'] / 100.0) * width)
            target_y = int((device.current_target['y'] / 100.0) * height)
            
            # Draw crosshair
            color = (0, 0, 255) if device.is_firing else (255, 255, 0)
            cv2.line(frame, (target_x - 20, target_y), (target_x + 20, target_y), color, 2)
            cv2.line(frame, (target_x, target_y - 20), (target_x, target_y + 20), color, 2)
            
            # Add status text
            status_text = f"Target: ({device.current_target['x']:.1f}%, {device.current_target['y']:.1f}%)"
            cv2.putText(frame, status_text, (20, 160), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            fire_text = "FIRING" if device.is_firing else "READY"
            fire_color = (0, 0, 255) if device.is_firing else (0, 255, 0)
            cv2.putText(frame, fire_text, (20, 180), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, fire_color, 2)
        
        return frame

    async def recv(self):
        """Receive the next video frame"""
        self.frame_count += 1
        
        if self.cap is not None and self.cap.isOpened():
            # Read from MP4 file
            ret, frame = self.cap.read()
            
            # Loop video when it reaches the end
            if not ret:
                print("End of video reached, looping...")
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                
            if not ret:
                print("Failed to read frame, using synthetic frame")
                frame = self.create_synthetic_frame()
            else:
                # Add overlay to show it's from MP4
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                cv2.putText(frame, f"MP4: {Path(self.video_path).name}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, timestamp, (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                # Add targeting overlay if available (access parent device state)
                if hasattr(self, '_device_ref') and self._device_ref:
                    device = self._device_ref
                    target_x = int((device.current_target['x'] / 100.0) * frame.shape[1])
                    target_y = int((device.current_target['y'] / 100.0) * frame.shape[0])
                    
                    # Draw crosshair
                    color = (0, 0, 255) if device.is_firing else (255, 255, 0)
                    cv2.line(frame, (target_x - 20, target_y), (target_x + 20, target_y), color, 2)
                    cv2.line(frame, (target_x, target_y - 20), (target_x, target_y + 20), color, 2)
                    
                    # Add status text
                    status_text = f"Target: ({device.current_target['x']:.1f}%, {device.current_target['y']:.1f}%)"
                    cv2.putText(frame, status_text, (10, 90), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    fire_text = "FIRING" if device.is_firing else "READY"
                    fire_color = (0, 0, 255) if device.is_firing else (0, 255, 0)
                    cv2.putText(frame, fire_text, (10, 110), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, fire_color, 2)
        else:
            # Use synthetic frame if no video file
            frame = self.create_synthetic_frame()
        
        # Convert BGR to RGB for WebRTC
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create video frame
        video_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        video_frame.pts = self.frame_count
        video_frame.time_base = fractions.Fraction(1, self.fps)
        
        return video_frame

    def __del__(self):
        """Cleanup video capture"""
        if self.cap is not None:
            self.cap.release()

class MockSprayerDevice:
    """Mock sprayer device that handles WebRTC video streaming and control commands"""
    
    def __init__(self, video_path="test_video.mp4", control_port=5632, video_port=8080):
        self.video_path = video_path
        self.control_port = control_port
        self.video_port = video_port
        self.video_track = None
        self.connections = {}
        self.control_socket = None
        self.logger = self.setup_logger()
        
        # Device state
        self.current_target = {"x": 50, "y": 50}  # Percentages
        self.is_firing = False
        self.targeting_mode = "cursor"
        
    def setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger('mock_sprayer')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    async def handle_webrtc_signaling(self, websocket, path):
        """Handle WebRTC signaling via WebSocket"""
        client_id = f"client_{len(self.connections)}"
        self.logger.info(f"New WebSocket connection: {client_id} on path: {path}")
        
        # Only handle connections to /websocket path
        if path != "/websocket":
            self.logger.warning(f"Invalid path: {path}, expected /websocket")
            await websocket.close()
            return
        
        try:
            # Create peer connection
            pc = RTCPeerConnection()
            self.connections[client_id] = {'pc': pc, 'websocket': websocket}
            
            # Add video track
            if self.video_track is None:
                self.video_track = MP4VideoStreamTrack(self.video_path)
                self.video_track._device_ref = self  # Pass reference for overlay
            pc.addTrack(self.video_track)
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                self.logger.info(f"Client {client_id} connection state: {pc.connectionState}")
                if pc.connectionState == "failed" or pc.connectionState == "closed":
                    if client_id in self.connections:
                        del self.connections[client_id]
            
            # Handle incoming messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_signaling_message(pc, websocket, data)
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON received: {message}")
                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
        finally:
            if client_id in self.connections:
                await self.connections[client_id]['pc'].close()
                del self.connections[client_id]

    async def handle_signaling_message(self, pc, websocket, data):
        """Handle signaling messages"""
        message_type = data.get('type')
        
        if message_type == 'request_stream':
            # Client requests video stream
            self.logger.info("Client requested video stream")
            
            # Create offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # Send offer to client
            await websocket.send(json.dumps({
                'type': 'offer',
                'offer': {
                    'type': offer.type,
                    'sdp': offer.sdp
                }
            }))
            
        elif message_type == 'answer':
            # Receive answer from client
            answer_data = data['answer']
            answer = RTCSessionDescription(sdp=answer_data['sdp'], type=answer_data['type'])
            await pc.setRemoteDescription(answer)
            self.logger.info("Received answer from client")
            
            # Notify client that stream is ready
            await websocket.send(json.dumps({
                'type': 'stream_ready'
            }))
            
        elif message_type == 'ice-candidate':
            # Handle ICE candidate
            candidate_data = data.get('candidate')
            if candidate_data:
                await pc.addIceCandidate(candidate_data)

    async def start_control_server(self):
        """Start the UDP control command server (compatible with Tauri backend)"""
        # Create UDP socket for receiving commands from Tauri backend
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.control_socket.bind(('0.0.0.0', self.control_port))
        
        self.logger.info(f"UDP control server listening on port {self.control_port}")
        
        def handle_udp_commands():
            while True:
                try:
                    data, addr = self.control_socket.recvfrom(1024)
                    command_str = data.decode('utf-8').strip()
                    self.process_udp_command(command_str, addr)
                except Exception as e:
                    self.logger.error(f"UDP command error: {e}")
        
        # Run in separate thread to not block async event loop
        control_thread = threading.Thread(target=handle_udp_commands)
        control_thread.daemon = True
        control_thread.start()

    def process_udp_command(self, command_str, addr):
        """Process UDP commands from Tauri backend"""
        self.logger.info(f"Received UDP command from {addr}: {command_str}")
        
        try:
            # Parse Tauri backend command format: "tilt,pan,trigger,1"
            parts = command_str.strip().split(',')
            if len(parts) >= 3:
                tilt = float(parts[0])
                pan = float(parts[1])
                trigger = int(parts[2]) > 0
                
                # Convert pan/tilt back to percentage coordinates for display
                self.current_target = {
                    'x': (pan / 180.0) * 100.0,  # Convert 0-180 to 0-100%
                    'y': (tilt / 180.0) * 100.0  # Convert 0-180 to 0-100%
                }
                self.is_firing = trigger
                
                self.logger.info(f"Parsed command - Pan: {pan}°, Tilt: {tilt}°, Trigger: {trigger}")
                self.logger.info(f"Target: {self.current_target['x']:.1f}%, {self.current_target['y']:.1f}%")
                
        except (ValueError, IndexError) as e:
            self.logger.error(f"Failed to parse command '{command_str}': {e}")

    async def start_video_server(self):
        """Start the WebRTC video server"""
        self.logger.info(f"Starting WebRTC video server on port {self.video_port}")
        
        # Start WebSocket server for signaling
        server = await serve(
            self.handle_webrtc_signaling,
            "0.0.0.0",
            self.video_port,
            subprotocols=["webrtc"]
        )
        
        self.logger.info(f"WebRTC signaling server started on ws://0.0.0.0:{self.video_port}")
        return server

    async def run(self):
        """Run the mock sprayer device"""
        self.logger.info("Starting Mock Sprayer Device")
        self.logger.info(f"Video file: {self.video_path}")
        self.logger.info(f"Control port: {self.control_port}")
        self.logger.info(f"Video port: {self.video_port}")
        
        # Start control server
        await self.start_control_server()
        
        # Start video server
        video_server = await self.start_video_server()
        
        try:
            # Run forever
            self.logger.info("Mock sprayer device is running. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        finally:
            # Cleanup
            video_server.close()
            await video_server.wait_closed()
            
            # Close UDP socket
            if self.control_socket:
                self.control_socket.close()
            
            # Close all WebRTC connections
            for client_data in self.connections.values():
                await client_data['pc'].close()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Mock Sprayer Device Server")
    parser.add_argument("--video", "-v", default="test_video.mp4", 
                       help="Path to MP4 video file (default: test_video.mp4)")
    parser.add_argument("--control-port", "-c", type=int, default=5632,
                       help="Port for control commands (default: 5632)")
    parser.add_argument("--video-port", "-p", type=int, default=8080,
                       help="Port for video streaming (default: 8080)")
    parser.add_argument("--create-test-video", action="store_true",
                       help="Create a test video file and exit")
    
    args = parser.parse_args()
    
    if args.create_test_video:
        create_test_video("test_video.mp4")
        return
    
    # Create and run mock device
    device = MockSprayerDevice(
        video_path=args.video,
        control_port=args.control_port,
        video_port=args.video_port
    )
    
    try:
        asyncio.run(device.run())
    except KeyboardInterrupt:
        print("\nShutting down...")

def create_test_video(filename="test_video.mp4", duration=10, fps=30):
    """Create a test video file for demonstration"""
    import numpy as np
    
    print(f"Creating test video: {filename}")
    
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    total_frames = duration * fps
    
    for frame_num in range(total_frames):
        # Create colorful test pattern
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Animated background
        time_factor = frame_num / total_frames
        for y in range(height):
            for x in range(width):
                frame[y, x] = [
                    int(128 + 127 * np.sin(time_factor * 2 * np.pi + x * 0.01)),
                    int(128 + 127 * np.sin(time_factor * 2 * np.pi + y * 0.01)),
                    int(128 + 127 * np.sin(time_factor * 2 * np.pi + (x + y) * 0.005))
                ]
        
        # Add text overlay
        cv2.putText(frame, f"Test Video Frame {frame_num}", (20, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, f"Time: {frame_num/fps:.1f}s", (20, 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add moving objects
        circle_x = int((frame_num % 60) * (width / 60))
        cv2.circle(frame, (circle_x, height//3), 15, (0, 255, 255), -1)
        
        rect_y = int((frame_num % 80) * (height / 80))
        cv2.rectangle(frame, (width-100, rect_y), (width-50, rect_y+30), (255, 0, 255), -1)
        
        out.write(frame)
        
        if frame_num % 30 == 0:
            print(f"Generated {frame_num}/{total_frames} frames...")
    
    out.release()
    print(f"Test video created: {filename}")

if __name__ == "__main__":
    main()