import asyncio
import cv2
import numpy as np
import json
import threading
import base64
import time
from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO, emit
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCDataChannel
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame
from datetime import datetime, timedelta
import logging
from flask_cors import CORS

# Disable Flask logging for cleaner output
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)  # Enable CORS for all routes

class SprayerController:
    def __init__(self):
        self.track = None
        self.data_channel = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        # Control state
        self.control_state = {
            "pan": 0.0,     # degrees from center (-90 to +90)
            "tilt": 0.0,    # degrees from center (-45 to +45)
            "trigger": False,
            "mode": "cursor"
        }
        self.control_lock = threading.Lock()
        
        # Settings
        self.settings = {
            "targeting_mode": "cursor",
            "firing_mode": "toggle", 
            "pan_sensitivity": 1.0,
            "tilt_sensitivity": 1.0,
            "server_address": "localhost:5000"
        }
        
        # Remote device info
        self.remote_device_ip = None
        self.device_connected = False

    def update_control(self, pan, tilt, trigger, mode="cursor"):
        """Update pan/tilt/trigger control state"""
        with self.control_lock:
            self.control_state["pan"] = max(-90, min(90, pan))
            self.control_state["tilt"] = max(-45, min(45, tilt))
            self.control_state["trigger"] = trigger
            self.control_state["mode"] = mode
            
            print(f"Control Update - Pan: {pan:.1f}°, Tilt: {tilt:.1f}°, Trigger: {trigger}")

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
                print(f"Sent control to device: {message}")
            except Exception as e:
                print(f"Error sending control data: {e}")

    async def handle_track(self, track):
        print("Starting video track handler")
        self.track = track
        
        while True:
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=1.0)
                frame_array = frame.to_ndarray(format="bgr24")
              
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
                    
                cv2.putText(frame_array, control_text, (10, frame_array.shape[0] - 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2, cv2.LINE_AA)
                cv2.putText(frame_array, trigger_text, (10, frame_array.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                           (0, 0, 255) if self.control_state['trigger'] else (255, 255, 255), 
                           2, cv2.LINE_AA)

                # Store the latest frame for web streaming
                with self.frame_lock:
                    self.latest_frame = frame_array.copy()
                
                # Send control updates to device
                self.send_control_to_device()
                
                # Emit frame to web clients
                socketio.emit('video_frame', self.frame_to_base64(frame_array))
                    
            except asyncio.TimeoutError:
                # Still send control updates even on timeout
                self.send_control_to_device()
            except Exception as e:
                print(f"Error in handle_track: {e}")
                break
        
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

# Global controller instance
controller = SprayerController()

@app.route('/')
def index():
    return render_template('index.html')

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
    return jsonify({'status': 'success'})

# Settings endpoint
@app.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.get_json()
        controller.settings.update(data)
        print(f"Settings updated: {controller.settings}")
        return jsonify({'status': 'success'})
    else:
        return jsonify(controller.settings)

# Device connection info endpoint
@app.route('/device/status', methods=['GET'])
def device_status():
    return jsonify({
        'connected': controller.device_connected,
        'remote_ip': controller.remote_device_ip,
        'data_channel_ready': controller.data_channel and controller.data_channel.readyState == "open"
    })

# WebSocket events
@socketio.on('control_update')
def handle_control_update(data):
    pan = data.get('pan', 0)
    tilt = data.get('tilt', 0)
    trigger = data.get('trigger', False)
    mode = data.get('mode', 'cursor')
    
    # Store client IP for potential remote device targeting
    client_ip = request.environ.get('REMOTE_ADDR')
    print(f"Control update from {client_ip}: Pan={pan}, Tilt={tilt}, Trigger={trigger}")
    
    controller.update_control(pan, tilt, trigger, mode)
    
    # Echo back to confirm
    emit('control_confirmed', {
        'pan': pan,
        'tilt': tilt, 
        'trigger': trigger,
        'timestamp': time.time()
    })

@socketio.on('connect')
def handle_connect():
    client_ip = request.environ.get('REMOTE_ADDR')
    print(f"Client connected from {client_ip}")
    
    # Send current control state to new client
    with controller.control_lock:
        emit('control_state', controller.control_state)

@socketio.on('disconnect')
def handle_disconnect():
    client_ip = request.environ.get('REMOTE_ADDR')
    print(f"Client disconnected from {client_ip}")

# Legacy click endpoint (for backwards compatibility)
@app.route('/click', methods=['POST'])
def handle_click_endpoint():
    """Legacy endpoint - converts clicks to pan/tilt"""
    data = request.get_json()
    x = data.get('x', 0)
    y = data.get('y', 0)
    
    # Convert click coordinates to pan/tilt (assuming click is percentage-based)
    # This is a simple conversion - you may want to adjust based on your coordinate system
    pan = ((x - 50) / 50) * 90  # Convert 0-100% to -90 to +90 degrees
    tilt = ((y - 50) / 50) * 45  # Convert 0-100% to -45 to +45 degrees
    
    controller.update_control(pan, tilt, False, "cursor")
    return jsonify({'status': 'success'})

async def run_webrtc(pc, signaling):
    await signaling.connect()

    @pc.on("track")
    def on_track(track):
        if isinstance(track, MediaStreamTrack):
            print(f"Receiving {track.kind} track")
            asyncio.ensure_future(controller.handle_track(track))

    @pc.on("datachannel")
    def on_datachannel(channel):
        print(f"Data channel established: {channel.label}")
        controller.data_channel = channel
        controller.device_connected = True
        
        @channel.on("open")
        def on_open():
            print("Data channel opened - ready to send control commands")
        
        @channel.on("close")
        def on_close():
            print("Data channel closed")
            controller.device_connected = False
        
        @channel.on("message")
        def on_message(message):
            print(f"Received message from device: {message}")
            try:
                data = json.loads(message)
                if data.get("type") == "device_info":
                    controller.remote_device_ip = data.get("ip")
                    print(f"Device IP: {controller.remote_device_ip}")
            except:
                pass

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"WebRTC connection state: {pc.connectionState}")
        if pc.connectionState == "connected":
            print("WebRTC connection established successfully")
            controller.device_connected = True
        elif pc.connectionState in ["disconnected", "failed", "closed"]:
            controller.device_connected = False

    print("Waiting for offer from device...")
    offer = await signaling.receive()
    print("Offer received from device")
    await pc.setRemoteDescription(offer)
    print("Remote description set")

    answer = await pc.createAnswer()
    print("Answer created")
    await pc.setLocalDescription(answer)
    print("Local description set")

    await signaling.send(pc.localDescription)
    print("Answer sent to device")

    print("Waiting for connection to be established...")
    while pc.connectionState != "connected":
        await asyncio.sleep(0.1)

    print("WebRTC connection established!")
    print("Web interface available at http://localhost:5000")
    print("Vue.js frontend can connect to this server for control")

def run_flask():
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)

async def main():
    signaling = TcpSocketSignaling("127.0.0.1", 9999)
    pc = RTCPeerConnection()

    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Sprayer Control Server started at http://localhost:5000")
    print("Waiting for device connection...")

    try:
        await run_webrtc(pc, signaling)
        
        # Keep the main thread alive
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"Error in main: {str(e)}")
    finally:
        print("Closing peer connection")
        await pc.close()

if __name__ == "__main__":
    asyncio.run(main())