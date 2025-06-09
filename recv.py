import asyncio
import cv2
import numpy as np
import json
import threading
import base64
import time
import random
from flask import Flask, render_template, Response, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCDataChannel
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame
from datetime import datetime, timedelta
import logging
from flask_cors import CORS
import concurrent.futures
import weakref

# YOLO tracking imports
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    print("Warning: ultralytics not available. Install with: pip install ultralytics")
    YOLO_AVAILABLE = False

# Disable Flask logging for cleaner output
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
SERVE_REACT_FILES = 1
import os
if SERVE_REACT_FILES:
    static_folder = os.path.join('frontend', 'dist')
    app = Flask(__name__, static_folder=static_folder, 
                static_url_path='',
                template_folder=static_folder)
else:
    app = Flask(__name__)

app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)  # Enable CORS for all routes

class AutoTargetingSystem:
    def __init__(self):
        self.model = None
        self.tracking_enabled = False
        self.tracked_objects = {}
        self.current_target_id = None
        self.target_hold_start = None
        self.target_hold_duration = 5.0  # seconds
        self.min_hold_time = 3.0
        self.max_hold_time = 8.0
        self.last_targeting_update = time.time()
        
        # Auto firing settings
        self.auto_fire_enabled = False
        self.fire_duration = 2.0  # seconds to fire at target
        self.fire_cooldown = 1.0  # seconds between firing bursts
        self.fire_start_time = None
        self.fire_cooldown_start = None
        
        # Target selection criteria
        self.min_target_confidence = 0.5
        self.preferred_classes = ['person', 'car', 'truck', 'bicycle', 'motorcycle']
        
        if YOLO_AVAILABLE:
            try:
                # Load YOLO model (you can use different models)
                self.model = YOLO("yolo11n.pt")  # or yolo11s.pt, yolo11m.pt, etc.
                print("YOLO model loaded successfully")
            except Exception as e:
                print(f"Failed to load YOLO model: {e}")
                self.model = None
    
    def update_tracking(self, frame):
        """Update object tracking on the current frame"""
        if not self.model or not self.tracking_enabled:
            return frame, []
        
        try:
            # Run YOLO tracking
            results = self.model.track(frame, persist=True, verbose=False)
            
            if not results or len(results) == 0:
                return frame, []
            
            result = results[0]
            tracked_objects = []
            
            # Process tracked objects
            if result.boxes is not None and result.boxes.id is not None:
                boxes = result.boxes.xywh.cpu().numpy()
                track_ids = result.boxes.id.int().cpu().tolist()
                confidences = result.boxes.conf.cpu().numpy()
                classes = result.boxes.cls.int().cpu().tolist()
                
                current_time = time.time()
                
                for box, track_id, conf, cls in zip(boxes, track_ids, confidences, classes):
                    if conf < self.min_target_confidence:
                        continue
                    
                    x_center, y_center, width, height = box
                    
                    # Calculate bounding box coordinates
                    x1 = int(x_center - width/2)
                    y1 = int(y_center - height/2)
                    x2 = int(x_center + width/2)
                    y2 = int(y_center + height/2)
                    
                    # Calculate bottom center point (targeting point)
                    target_x = int(x_center)
                    target_y = int(y2)  # Bottom of bounding box
                    
                    class_name = self.model.names[cls] if cls < len(self.model.names) else f"class_{cls}"
                    
                    # Store tracked object info
                    self.tracked_objects[track_id] = {
                        'bbox': (x1, y1, x2, y2),
                        'center': (int(x_center), int(y_center)),
                        'target_point': (target_x, target_y),
                        'confidence': conf,
                        'class': class_name,
                        'class_id': cls,
                        'last_seen': current_time
                    }
                    
                    tracked_objects.append({
                        'id': track_id,
                        'bbox': (x1, y1, x2, y2),
                        'center': (int(x_center), int(y_center)),
                        'target_point': (target_x, target_y),
                        'confidence': conf,
                        'class': class_name,
                        'is_target': track_id == self.current_target_id
                    })
            
            # Clean up old tracks
            self._cleanup_old_tracks(current_time)
            
            # Update target selection
            self._update_target_selection()
            
            # Draw tracking overlays
            annotated_frame = self._draw_tracking_overlays(frame, tracked_objects)
            
            return annotated_frame, tracked_objects
            
        except Exception as e:
            print(f"Error in tracking update: {e}")
            return frame, []
    
    def _cleanup_old_tracks(self, current_time, timeout=2.0):
        """Remove tracks that haven't been seen recently"""
        to_remove = []
        for track_id, obj_info in self.tracked_objects.items():
            if current_time - obj_info['last_seen'] > timeout:
                to_remove.append(track_id)
        
        for track_id in to_remove:
            if track_id == self.current_target_id:
                self.current_target_id = None
                self.target_hold_start = None
            del self.tracked_objects[track_id]
    
    def _update_target_selection(self):
        """Update current target selection based on hold time and available targets"""
        current_time = time.time()
        
        # Check if we need to select a new target
        need_new_target = False
        
        if self.current_target_id is None:
            need_new_target = True
        elif self.current_target_id not in self.tracked_objects:
            # Current target lost
            need_new_target = True
            self.current_target_id = None
            self.target_hold_start = None
        elif self.target_hold_start and (current_time - self.target_hold_start) >= self.target_hold_duration:
            # Hold time expired
            need_new_target = True
        
        if need_new_target and self.tracked_objects:
            # Select new target
            self._select_new_target()
    
    def _select_new_target(self):
        """Select a new target from available tracked objects"""
        if not self.tracked_objects:
            self.current_target_id = None
            return
        
        # Filter preferred targets
        preferred_targets = []
        other_targets = []
        
        for track_id, obj_info in self.tracked_objects.items():
            if obj_info['class'] in self.preferred_classes:
                preferred_targets.append(track_id)
            else:
                other_targets.append(track_id)
        
        # Choose from preferred targets first, then others
        available_targets = preferred_targets if preferred_targets else other_targets
        
        if available_targets:
            # Randomly select a target
            self.current_target_id = random.choice(available_targets)
            self.target_hold_start = time.time()
            
            # Randomize hold duration
            self.target_hold_duration = random.uniform(self.min_hold_time, self.max_hold_time)
            
            print(f"Selected new target: ID {self.current_target_id} "
                  f"({self.tracked_objects[self.current_target_id]['class']}) "
                  f"for {self.target_hold_duration:.1f}s")
    
    def _draw_tracking_overlays(self, frame, tracked_objects):
        """Draw tracking information on the frame"""
        for obj in tracked_objects:
            track_id = obj['id']
            bbox = obj['bbox']
            center = obj['center']
            target_point = obj['target_point']
            confidence = obj['confidence']
            class_name = obj['class']
            is_target = obj['is_target']
            
            x1, y1, x2, y2 = bbox
            
            # Choose colors
            if is_target:
                bbox_color = (0, 0, 255)  # Red for current target
                text_color = (255, 255, 255)
                thickness = 3
            else:
                bbox_color = (0, 255, 0)  # Green for other tracks
                text_color = (255, 255, 255)
                thickness = 2
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), bbox_color, thickness)
            
            # Draw target point (bottom center)
            cv2.circle(frame, target_point, 5, bbox_color, -1)
            cv2.circle(frame, target_point, 8, bbox_color, 2)
            
            # Draw center point
            cv2.circle(frame, center, 3, (255, 0, 255), -1)
            
            # Draw ID and class label
            label = f"ID:{track_id} {class_name} {confidence:.2f}"
            if is_target:
                remaining_time = self.target_hold_duration - (time.time() - self.target_hold_start) if self.target_hold_start else 0
                label += f" TARGET ({remaining_time:.1f}s)"
            
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(frame, (x1, y1-25), (x1 + label_size[0], y1), bbox_color, -1)
            cv2.putText(frame, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
        
        # Draw targeting status
        status_text = []
        if self.tracking_enabled:
            status_text.append(f"AUTO TARGETING: ON ({len(tracked_objects)} objects)")
            if self.current_target_id:
                target_info = self.tracked_objects.get(self.current_target_id)
                if target_info:
                    remaining = self.target_hold_duration - (time.time() - self.target_hold_start) if self.target_hold_start else 0
                    status_text.append(f"TARGET: ID {self.current_target_id} ({target_info['class']}) - {remaining:.1f}s")
            else:
                status_text.append("TARGET: None")
                
            if self.auto_fire_enabled:
                fire_status = self._get_fire_status()
                status_text.append(f"AUTO FIRE: {fire_status}")
        else:
            status_text.append("AUTO TARGETING: OFF")
        
        # Draw status text
        for i, text in enumerate(status_text):
            y_pos = 30 + i * 25
            cv2.rectangle(frame, (10, y_pos-20), (10 + len(text)*12, y_pos+5), (0, 0, 0), -1)
            cv2.putText(frame, text, (15, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        return frame
    
    def get_target_position(self):
        """Get current target position for aiming"""
        if not self.current_target_id or self.current_target_id not in self.tracked_objects:
            return None
        
        target_info = self.tracked_objects[self.current_target_id]
        return target_info['target_point']
    
    def _get_fire_status(self):
        """Get current firing status"""
        current_time = time.time()
        
        if self.fire_start_time and (current_time - self.fire_start_time) < self.fire_duration:
            return "FIRING"
        elif self.fire_cooldown_start and (current_time - self.fire_cooldown_start) < self.fire_cooldown:
            return "COOLDOWN"
        else:
            return "READY"
    
    def update_auto_fire(self):
        """Update automatic firing logic"""
        if not self.auto_fire_enabled or not self.current_target_id:
            return False
        
        current_time = time.time()
        
        # Check if we're currently firing
        if self.fire_start_time and (current_time - self.fire_start_time) < self.fire_duration:
            return True
        
        # Check if we're in cooldown
        if self.fire_cooldown_start and (current_time - self.fire_cooldown_start) < self.fire_cooldown:
            return False
        
        # Start new firing cycle if target is available
        if self.current_target_id in self.tracked_objects:
            self.fire_start_time = current_time
            self.fire_cooldown_start = None
            print(f"Auto fire started on target {self.current_target_id}")
            return True
        
        return False
    
    def stop_auto_fire(self):
        """Stop current firing and start cooldown"""
        if self.fire_start_time:
            self.fire_cooldown_start = time.time()
            self.fire_start_time = None
    
    def set_tracking_enabled(self, enabled):
        """Enable or disable tracking"""
        self.tracking_enabled = enabled
        if not enabled:
            self.tracked_objects.clear()
            self.current_target_id = None
            self.target_hold_start = None
            self.fire_start_time = None
            self.fire_cooldown_start = None
    
    def set_auto_fire_enabled(self, enabled):
        """Enable or disable auto firing"""
        self.auto_fire_enabled = enabled
        if not enabled:
            self.fire_start_time = None
            self.fire_cooldown_start = None

class SprayerController:
    def __init__(self):
        self.track = None
        self.data_channel = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        # WebRTC connection state
        self.pc = None
        self.signaling = None
        self.webrtc_connected = False
        self.connection_task = None
        self.background_loop = None
        self.background_thread = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        # Control state
        self.control_state = {
            "pan": 0.0,     # degrees from center (-90 to +90)
            "tilt": 0.0,    # degrees from center (-45 to +45)
            "trigger": False,
            "mode": "cursor"
        }
        self.control_lock = threading.Lock()
        
        # Auto targeting system
        self.auto_targeting = AutoTargetingSystem()
        
        # Settings
        self.settings = {
            "targeting_mode": "cursor",
            "firing_mode": "toggle", 
            "pan_sensitivity": 1.0,
            "tilt_sensitivity": 1.0,
            "server_address": "localhost:5000",
            "camera_address": "127.0.0.1:9999",  # Default camera signaling address
            "auto_fire_enabled": False,
            "target_hold_time_min": 3.0,
            "target_hold_time_max": 8.0,
            "fire_duration": 2.0,
            "fire_cooldown": 1.0
        }
        
        # Remote device info
        self.remote_device_ip = None
        self.device_connected = False
        
        # Start background event loop
        self._start_background_loop()

    def _start_background_loop(self):
        """Start a dedicated background event loop for WebRTC operations"""
        def run_loop():
            self.background_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.background_loop)
            try:
                self.background_loop.run_forever()
            except Exception as e:
                print(f"Background loop error: {e}")
            finally:
                print("Background loop finished")
        
        self.background_thread = threading.Thread(target=run_loop, daemon=True)
        self.background_thread.start()
        
        # Wait for loop to be ready
        while self.background_loop is None:
            time.sleep(0.01)

    def _run_in_background(self, coro):
        """Run a coroutine in the background event loop"""
        if self.background_loop and not self.background_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(coro, self.background_loop)
            return future
        else:
            raise RuntimeError("Background loop is not available")

    def update_control(self, pan, tilt, trigger, mode="cursor"):
        """Update pan/tilt/trigger control state"""
        with self.control_lock:
            self.control_state["pan"] = max(-90, min(90, pan))
            self.control_state["tilt"] = max(-45, min(45, tilt))
            self.control_state["trigger"] = trigger
            self.control_state["mode"] = mode
            
            print(f"Control Update - Pan: {pan:.1f}°, Tilt: {tilt:.1f}°, Trigger: {trigger}")

    def update_auto_targeting_control(self, frame_width, frame_height):
        """Update control based on auto targeting"""
        if self.control_state["mode"] != "automatic":
            return
        
        target_pos = self.auto_targeting.get_target_position()
        if target_pos:
            target_x, target_y = target_pos
            
            # Convert pixel coordinates to pan/tilt degrees
            # Assuming frame center is (0, 0) in pan/tilt space
            center_x = frame_width / 2
            center_y = frame_height / 2
            
            # Calculate pan/tilt from target position
            pan_degrees = ((target_x - center_x) / center_x) * 90 * self.settings["pan_sensitivity"]
            tilt_degrees = ((target_y - center_y) / center_y) * 45 * self.settings["tilt_sensitivity"]
            
            # Update auto fire
            auto_fire = False
            if self.settings.get("auto_fire_enabled", False):
                auto_fire = self.auto_targeting.update_auto_fire()
            
            with self.control_lock:
                self.control_state["pan"] = max(-90, min(90, pan_degrees))
                self.control_state["tilt"] = max(-45, min(45, tilt_degrees))
                self.control_state["trigger"] = auto_fire

    def send_control_to_device(self):
        """Send control state to remote device via WebRTC data channel"""
        if not self.data_channel or self.data_channel.readyState != "open":
            return
            
        with self.control_lock:
            try:
                message = json.dumps({
                    "type": "control",
                    "pan": self.control_state["pan"],
                    "tilt": self.control_state["tilt"], 
                    "trigger": self.control_state["trigger"],
                    "mode": self.control_state["mode"],
                    "timestamp": time.time()
                })
                self.data_channel.send(message)
                #print(f"Sent control to device: {message}")
            except Exception as e:
                print(f"Error sending control data: {e}")

    async def handle_track(self, track):
        print("Starting video track handler")
        self.track = track
        
        try:
            while True:
                try:
                    frame = await asyncio.wait_for(track.recv(), timeout=1.0)
                    frame_array = frame.to_ndarray(format="bgr24")
                    
                    # Update auto targeting if enabled
                    tracked_objects = []
                    if self.control_state["mode"] == "automatic":
                        self.auto_targeting.set_tracking_enabled(True)
                        frame_array, tracked_objects = self.auto_targeting.update_tracking(frame_array)
                        
                        # Update control based on targeting
                        self.update_auto_targeting_control(frame_array.shape[1], frame_array.shape[0])
                    else:
                        self.auto_targeting.set_tracking_enabled(False)
                  
                    # Add timestamp and control state overlay
                    current_time = datetime.now()
                    timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    
                    # Add timestamp
                    cv2.putText(frame_array, timestamp, (10, frame_array.shape[0] - 50), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                    
                    # Add control state info
                    with self.control_lock:
                        control_text = f"Pan: {self.control_state['pan']:.1f}° Tilt: {self.control_state['tilt']:.1f}°"
                        trigger_text = f"Trigger: {'ON' if self.control_state['trigger'] else 'OFF'}"
                        mode_text = f"Mode: {self.control_state['mode'].upper()}"
                        
                    cv2.putText(frame_array, control_text, (10, frame_array.shape[0] - 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2, cv2.LINE_AA)
                    cv2.putText(frame_array, trigger_text, (10, frame_array.shape[0] - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                               (0, 0, 255) if self.control_state['trigger'] else (255, 255, 255), 
                               2, cv2.LINE_AA)
                    cv2.putText(frame_array, mode_text, (frame_array.shape[1] - 200, frame_array.shape[0] - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2, cv2.LINE_AA)

                    # Store the latest frame for web streaming
                    with self.frame_lock:
                        self.latest_frame = frame_array.copy()
                    
                    # Send control updates to device
                    self.send_control_to_device()
                    
                    # Emit frame and tracking data to web clients
                    socketio.emit('video_frame', self.frame_to_base64(frame_array))
                    if tracked_objects:
                        pass
                        # socketio.emit('tracking_update', {
                        #     'objects': tracked_objects,
                        #     'current_target': self.auto_targeting.current_target_id,
                        #     'auto_fire_enabled': self.settings.get("auto_fire_enabled", False),
                        #     'fire_status': self.auto_targeting._get_fire_status() if self.auto_targeting.auto_fire_enabled else "OFF"
                        # })
                        
                except asyncio.TimeoutError:
                    # Still send control updates even on timeout
                    self.send_control_to_device()
                except Exception as e:
                    print(f"Error in handle_track: {e}")
                    break
        except Exception as e:
            print(f"Track handler error: {e}")
        finally:
            print("Exiting video track handler")

    def frame_to_base64(self, frame):
        """Convert frame to base64 for web transmission"""
        _, buffer = cv2.imencode('.jpg', frame)
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        return jpg_as_text

    def get_mjpeg_stream(self):
        """Generator for MJPEG streaming"""
        while True:
            with self.frame_lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
                else:
                    # Create a black frame with status info
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "Waiting for video...", (50, 240), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    
                    # Show control state even without video
                    with self.control_lock:
                        control_text = f"Pan: {self.control_state['pan']:.1f}° Tilt: {self.control_state['tilt']:.1f}°"
                        trigger_text = f"Trigger: {'ON' if self.control_state['trigger'] else 'OFF'}"
                        
                    cv2.putText(frame, control_text, (50, 300), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(frame, trigger_text, (50, 330), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                               (0, 0, 255) if self.control_state['trigger'] else (255, 255, 255), 2)

            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.033)  # ~30 FPS

    async def _connect_to_camera_async(self, camera_address):
        """Async WebRTC connection logic"""
        try:
            # Parse camera address
            if ':' in camera_address:
                host, port = camera_address.split(':')
                port = int(port)
            else:
                host = camera_address
                port = 9999
            
            print(f"Connecting to camera at {host}:{port}")
            
            # Create new connection
            self.signaling = TcpSocketSignaling(host, port)
            self.pc = RTCPeerConnection()
            
            # Set up event handlers
            @self.pc.on("track")
            def on_track(track):
                if isinstance(track, MediaStreamTrack):
                    print(f"Receiving {track.kind} track")
                    # Use the same background loop for track handling
                    asyncio.create_task(self.handle_track(track))

            @self.pc.on("datachannel")
            def on_datachannel(channel):
                print(f"Data channel established: {channel.label}")
                self.data_channel = channel
                self.device_connected = True
                
                @channel.on("open")
                def on_open():
                    print("Data channel opened - ready to send control commands")
                
                @channel.on("close")
                def on_close():
                    print("Data channel closed")
                    self.device_connected = False
                
                @channel.on("message")
                def on_message(message):
                    print(f"Received message from device: {message}")
                    try:
                        data = json.loads(message)
                        if data.get("type") == "device_info":
                            self.remote_device_ip = data.get("ip")
                            print(f"Device IP: {self.remote_device_ip}")
                    except:
                        pass

            @self.pc.on("connectionstatechange")
            async def on_connectionstatechange():
                print(f"WebRTC connection state: {self.pc.connectionState}")
                if self.pc.connectionState == "connected":
                    print("WebRTC connection established successfully")
                    self.webrtc_connected = True
                    self.device_connected = True
                elif self.pc.connectionState in ["disconnected", "failed", "closed"]:
                    self.webrtc_connected = False
                    self.device_connected = False

            # Connect and establish WebRTC
            await self.signaling.connect()
            
            print("Waiting for offer from device...")
            offer = await self.signaling.receive()
            print("Offer received from device")
            await self.pc.setRemoteDescription(offer)
            print("Remote description set")

            answer = await self.pc.createAnswer()
            print("Answer created")
            await self.pc.setLocalDescription(answer)
            print("Local description set")

            await self.signaling.send(self.pc.localDescription)
            print("Answer sent to device")

            print("Waiting for connection to be established...")
            # Wait for connection with timeout
            timeout = 30  # 30 seconds timeout
            start_time = time.time()
            while self.pc.connectionState != "connected" and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.1)
            
            if self.pc.connectionState == "connected":
                print("WebRTC connection established successfully!")
                self.webrtc_connected = True
                return True
            else:
                print("WebRTC connection timed out")
                await self._disconnect_camera_async()
                return False
                
        except Exception as e:
            print(f"Error connecting to camera: {e}")
            await self._disconnect_camera_async()
            return False

    async def _disconnect_camera_async(self):
        """Async camera disconnection logic"""
        print("Disconnecting from camera...")
        
        self.webrtc_connected = False
        self.device_connected = False
        self.data_channel = None
        self.track = None
        
        # Disable auto targeting
        self.auto_targeting.set_tracking_enabled(False)
        self.auto_targeting.set_auto_fire_enabled(False)
        
        # Close peer connection gracefully
        if self.pc:
            try:
                # Give some time for cleanup
                await asyncio.sleep(0.1)
                await self.pc.close()
            except Exception as e:
                print(f"Error closing peer connection: {e}")
            finally:
                self.pc = None
            
        # Close signaling
        if self.signaling:
            try:
                await self.signaling.close()
            except Exception as e:
                print(f"Error closing signaling: {e}")
            finally:
                self.signaling = None
        
        # Clear latest frame
        with self.frame_lock:
            self.latest_frame = None
            
        print("Camera disconnected")

    def connect_to_camera(self, camera_address):
        """Connect to camera via WebRTC (synchronous wrapper)"""
        try:
            # Update settings
            self.settings['camera_address'] = camera_address
            
            # Run the async connection in the background loop
            future = self._run_in_background(self._connect_to_camera_async(camera_address))
            # Wait for completion with timeout
            return future.result(timeout=35)  # Slightly longer than internal timeout
            
        except Exception as e:
            print(f"Camera connection error: {e}")
            return False

    def disconnect_camera(self):
        """Disconnect from camera (synchronous wrapper)"""
        try:
            # Run the async disconnection in the background loop
            future = self._run_in_background(self._disconnect_camera_async())
            future.result(timeout=10)  # 10 second timeout for cleanup
        except Exception as e:
            print(f"Camera disconnection error: {e}")

    def shutdown(self):
        """Clean shutdown of controller"""
        print("Shutting down controller...")
        
        # Disconnect camera first
        if self.webrtc_connected:
            self.disconnect_camera()
        
        # Stop background loop
        if self.background_loop and not self.background_loop.is_closed():
            self.background_loop.call_soon_threadsafe(self.background_loop.stop)
        
        # Wait for background thread to finish
        if self.background_thread and self.background_thread.is_alive():
            self.background_thread.join(timeout=5)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        print("Controller shutdown complete")

# Global controller instance
controller = SprayerController()

@app.route('/video_feed')
def video_feed():
    return Response(controller.get_mjpeg_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# New control endpoint for pan/tilt/trigger
@app.route('/control', methods=['POST'])
def handle_control():
    data = request.get_json()
    pan = data.get('pan', 0)
    tilt = data.get('tilt', 0)
    trigger = data.get('trigger', False)
    mode = data.get('mode', 'cursor')
    
    controller.update_control(pan, tilt, trigger, mode)
    
    # Update auto targeting settings based on mode
    if mode == "automatic":
        controller.auto_targeting.set_auto_fire_enabled(controller.settings.get("auto_fire_enabled", False))
    else:
        controller.auto_targeting.set_auto_fire_enabled(False)
    
    return jsonify({'status': 'success'})

# Settings endpoint
@app.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.get_json()
        controller.settings.update(data)
        
        # Update auto targeting settings
        if 'target_hold_time_min' in data:
            controller.auto_targeting.min_hold_time = data['target_hold_time_min']
        if 'target_hold_time_max' in data:
            controller.auto_targeting.max_hold_time = data['target_hold_time_max']
        if 'fire_duration' in data:
            controller.auto_targeting.fire_duration = data['fire_duration']
        if 'fire_cooldown' in data:
            controller.auto_targeting.fire_cooldown = data['fire_cooldown']
        if 'auto_fire_enabled' in data:
            controller.auto_targeting.set_auto_fire_enabled(data['auto_fire_enabled'])
            
        print(f"Settings updated: {controller.settings}")
        return jsonify({'status': 'success'})
    else:
        return jsonify(controller.settings)

# Auto targeting specific endpoints
@app.route('/targeting/status', methods=['GET'])
def targeting_status():
    """Get current targeting status"""
    return jsonify({
        'tracking_enabled': controller.auto_targeting.tracking_enabled,
        'tracked_objects': len(controller.auto_targeting.tracked_objects),
        'current_target': controller.auto_targeting.current_target_id,
        'auto_fire_enabled': controller.auto_targeting.auto_fire_enabled,
        'fire_status': controller.auto_targeting._get_fire_status(),
        'yolo_available': YOLO_AVAILABLE
    })

@app.route('/targeting/toggle_fire', methods=['POST'])
def toggle_auto_fire():
    """Toggle automatic firing"""
    enabled = controller.auto_targeting.auto_fire_enabled
    controller.auto_targeting.set_auto_fire_enabled(not enabled)
    controller.settings['auto_fire_enabled'] = not enabled
    
    return jsonify({
        'status': 'success',
        'auto_fire_enabled': not enabled
    })

# WebRTC connection endpoints
@app.route('/camera/connect', methods=['POST'])
def connect_camera():
    """Initiate WebRTC connection to camera"""
    data = request.get_json()
    camera_address = data.get('camera_address', controller.settings.get('camera_address', '127.0.0.1:9999'))
    
    try:
        success = controller.connect_to_camera(camera_address)
        return jsonify({
            'status': 'success' if success else 'failed',
            'connected': success,
            'camera_address': camera_address,
            'yolo_available': YOLO_AVAILABLE
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'connected': False
        }), 500

@app.route('/camera/disconnect', methods=['POST'])
def disconnect_camera():
    """Disconnect from camera"""
    try:
        controller.disconnect_camera()
        return jsonify({'status': 'success', 'connected': False})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

# Device connection info endpoint
@app.route('/device/status', methods=['GET'])
def device_status():
    return jsonify({
        'connected': controller.device_connected,
        'webrtc_connected': controller.webrtc_connected,
        'remote_ip': controller.remote_device_ip,
        'data_channel_ready': controller.data_channel and controller.data_channel.readyState == "open",
        'camera_address': controller.settings.get('camera_address', '127.0.0.1:9999'),
        'tracking_status': {
            'enabled': controller.auto_targeting.tracking_enabled,
            'objects_tracked': len(controller.auto_targeting.tracked_objects),
            'current_target': controller.auto_targeting.current_target_id,
            'yolo_available': YOLO_AVAILABLE
        }
    })

if SERVE_REACT_FILES:
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    @app.errorhandler(404)
    def serve_react_app(path):
        return send_from_directory(app.static_folder, 'index.html')

# WebSocket events
@socketio.on('control_update')
def handle_control_update(data):
    pan = data.get('pan', 0)
    tilt = data.get('tilt', 0)
    trigger = data.get('trigger', False)
    mode = data.get('mode', 'cursor')
    
    # Store client IP for potential remote device targeting
    client_ip = request.environ.get('REMOTE_ADDR')
    print(f"Control update from {client_ip}: Pan={pan}, Tilt={tilt}, Trigger={trigger}, Mode={mode}")
    
    controller.update_control(pan, tilt, trigger, mode)
    
    # Update auto targeting settings based on mode
    if mode == "automatic":
        controller.auto_targeting.set_auto_fire_enabled(controller.settings.get("auto_fire_enabled", False))
    else:
        controller.auto_targeting.set_auto_fire_enabled(False)
    
    # Echo back to confirm
    emit('control_confirmed', {
        'pan': pan,
        'tilt': tilt, 
        'trigger': trigger,
        'mode': mode,
        'timestamp': time.time()
    })

@socketio.on('connect')
def handle_connect():
    client_ip = request.environ.get('REMOTE_ADDR')
    print(f"Client connected from {client_ip}")
    
    # Send current control state to new client
    with controller.control_lock:
        emit('control_state', controller.control_state)
    
    # Send targeting status
    emit('targeting_status', {
        'yolo_available': YOLO_AVAILABLE,
        'tracking_enabled': controller.auto_targeting.tracking_enabled,
        'auto_fire_enabled': controller.auto_targeting.auto_fire_enabled
    })

@socketio.on('disconnect')
def handle_disconnect():
    client_ip = request.environ.get('REMOTE_ADDR')
    print(f"Client disconnected from {client_ip}")

def run_flask():
    socketio.run(app, host='0.0.0.0', port=5002, debug=False, use_reloader=False)

def main():
    """Main function - only starts Flask server, WebRTC connection is initiated via API"""
    print("Sprayer Control Server starting...")
    print("Server will be available at http://localhost:5002")
    print("WebRTC connection will be initiated when requested by frontend")
    if YOLO_AVAILABLE:
        print("YOLO tracking is available for auto targeting mode")
    else:
        print("Warning: YOLO not available. Install ultralytics for auto targeting: pip install ultralytics")
    
    try:
        # Only start Flask server
        run_flask()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        # Clean shutdown
        controller.shutdown()

if __name__ == "__main__":
    main()