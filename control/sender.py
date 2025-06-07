import asyncio
import cv2
import json
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame
import fractions
from datetime import datetime

class CustomVideoStreamTrack(VideoStreamTrack):
    def __init__(self, camera_id):
        super().__init__()
        self.cap = cv2.VideoCapture(camera_id)
        self.frame_count = 0
        print(f"Sending frame {self.frame_count}")

    async def recv(self):
        self.frame_count += 1
        ret, frame = self.cap.read()
        if not ret:
            print("Failed to read frame from camera")
            return None
            
        
        # Add timestamp to the frame (on BGR version for display)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

        # Convert the processed BGR frame back to RGB for VideoFrame
        frame_rgb_final = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = VideoFrame.from_ndarray(frame_rgb_final, format="rgb24")
        video_frame.pts = self.frame_count
        video_frame.time_base = fractions.Fraction(1, 30)
        return video_frame

async def setup_webrtc_and_run(ip_address, port, camera_id):
    signaling = TcpSocketSignaling(ip_address, port)
    pc = RTCPeerConnection()
    video_sender = CustomVideoStreamTrack(camera_id)
    pc.addTrack(video_sender)

    # Create data channel on sender side (offering peer)
    data_channel = pc.createDataChannel("clicks", ordered=True)
    
    @data_channel.on("open")
    def on_data_channel_open():
        print("Data channel opened - ready to receive click coordinates")
    
    @data_channel.on("close")
    def on_data_channel_close():
        print("Data channel closed")
    
    @data_channel.on("message")
    def on_data_channel_message(message):
        try:
            # Parse the click coordinates
            click_data = json.loads(message)
            x = click_data.get("x", "")
            y = click_data.get("y", "")
            print(f"Received click coordinates from receiver: x={x}, y={y}")
            
            # You can add your logic here to handle the click coordinates
            # For example, you could:
            # - Store the coordinates for later use
            # - Trigger some action based on the click
            # - Send a response back through the data channel
            
        except json.JSONDecodeError as e:
            print(f"Error parsing message: {e}")
        except Exception as e:
            print(f"Error handling message: {e}")

    try:
        await signaling.connect()

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"Connection state is {pc.connectionState}")
            if pc.connectionState == "connected":
                print("WebRTC connection established successfully")

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await signaling.send(pc.localDescription)

        while True:
            obj = await signaling.receive()
            if isinstance(obj, RTCSessionDescription):
                await pc.setRemoteDescription(obj)
                print("Remote description set")
            elif obj is None:
                print("Signaling ended")
                break
        print("Closing connection")
    finally:
        # Clean up camera
        video_sender.cap.release()
        await pc.close()

async def main():
    ip_address = "0.0.0.0"  # IP Address of Remote Server/Machine
    port = 9999
    camera_id = 0  # Change this to the appropriate camera ID
    await setup_webrtc_and_run(ip_address, port, camera_id)

if __name__ == "__main__":
    asyncio.run(main())