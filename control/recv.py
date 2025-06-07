import asyncio
import cv2
import numpy as np
import json
import threading
import base64
from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO, emit
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCDataChannel
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame
from datetime import datetime, timedelta
import logging

# Disable Flask logging for cleaner output
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

class VideoReceiver:
    def __init__(self):
        self.track = None
        self.data_channel = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()

    def handle_click(self, x, y):
        """Handle click coordinates from web interface"""
        if self.data_channel and self.data_channel.readyState == "open":
            try:
                click_data = {"x": str(x), "y": str(y)}
                message = json.dumps(click_data)
                print(f"Sending mouse data: {message}")
                self.data_channel.send(message)
            except Exception as e:
                print(f"Error sending click data: {e}")
        else:
            print("Data channel not available or not open")

    async def handle_track(self, track):
        print("Inside handle track")
        self.track = track
         
        while True:
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=1.0)
                frame_array = frame.to_ndarray(format="bgr24")
              
                # Add timestamp to the frame
                current_time = datetime.now()
                timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                cv2.putText(frame_array, timestamp, (10, frame_array.shape[0] - 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

                # Store the latest frame for web streaming
                with self.frame_lock:
                    self.latest_frame = frame_array.copy()
                
                # Emit frame to web clients
                socketio.emit('video_frame', self.frame_to_base64(frame_array))
                    
            except asyncio.TimeoutError:
                print("Timeout waiting for frame, continuing...")
            except Exception as e:
                print(f"Error in handle_track: {e}")
                break
        
        print("Exiting handle_track")

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
                    # Create a black frame if no video available
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "Waiting for video...", (50, 240), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            asyncio.sleep(0.033)  # ~30 FPS

# Global video receiver instance
video_receiver = VideoReceiver()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(video_receiver.get_mjpeg_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@socketio.on('mouse_click')
def handle_mouse_click(data):
    x = data.get('x')
    y = data.get('y')
    print(f"Received click at ({x}, {y}) from web interface")
    video_receiver.handle_click(x, y)

@app.route('/click', methods=['POST'])
def handle_click_endpoint():
    data = request.get_json()
    x = data.get('x')
    y = data.get('y')
    video_receiver.handle_click(x, y)
    return jsonify({'status': 'success'})

async def run_webrtc(pc, signaling):
    await signaling.connect()

    @pc.on("track")
    def on_track(track):
        if isinstance(track, MediaStreamTrack):
            print(f"Receiving {track.kind} track")
            asyncio.ensure_future(video_receiver.handle_track(track))

    @pc.on("datachannel")
    def on_datachannel(channel):
        print(f"Data channel established: {channel.label}")
        video_receiver.data_channel = channel
        
        @channel.on("open")
        def on_open():
            print("Data channel opened - ready to send click coordinates")
        
        @channel.on("close")
        def on_close():
            print("Data channel closed")
        
        @channel.on("message")
        def on_message(message):
            print(f"Received message from sender: {message}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "connected":
            print("WebRTC connection established successfully")

    print("Waiting for offer from sender...")
    offer = await signaling.receive()
    print("Offer received")
    await pc.setRemoteDescription(offer)
    print("Remote description set")

    answer = await pc.createAnswer()
    print("Answer created")
    await pc.setLocalDescription(answer)
    print("Local description set")

    await signaling.send(pc.localDescription)
    print("Answer sent to sender")

    print("Waiting for connection to be established...")
    while pc.connectionState != "connected":
        await asyncio.sleep(0.1)

    print("Connection established, waiting for frames...")
    print("Open http://localhost:5000 in your browser to view the video and click!")

def run_flask():
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)

async def main():
    signaling = TcpSocketSignaling("127.0.0.1", 9999)
    pc = RTCPeerConnection()

    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Web server started at http://localhost:5000")

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