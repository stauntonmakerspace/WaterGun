import asyncio
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame
import numpy as np
import fractions
from datetime import datetime

class CustomVideoStreamTrack(VideoStreamTrack):
    def __init__(self, camera_id):
        super().__init__()
        self.cap = cv2.VideoCapture(camera_id)
        self.frame_count = 0
        
        # Set video properties for better looping
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        # Get total frame count for reference
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"Video has {self.total_frames} total frames")

    async def recv(self):
        self.frame_count += 1
        print(f"Sending frame {self.frame_count}")
        
        ret, frame = self.cap.read()
        
        # If we can't read a frame (end of video), loop back to the beginning
        if not ret:
            print("End of video reached, looping back to start")
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to beginning
            ret, frame = self.cap.read()
            
            # If still can't read, there's an issue with the video file
            if not ret:
                print("Failed to read frame from video file")
                # Create a black frame as fallback
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Add timestamp to the frame (before color conversion)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
        
        # Convert from BGR to RGB for VideoFrame
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create VideoFrame
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = self.frame_count
        video_frame.time_base = fractions.Fraction(1, 30)
        
        return video_frame
    
    def __del__(self):
        # Clean up video capture when object is destroyed
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

async def setup_webrtc_and_run(ip_address, port, camera_id):
    signaling = TcpSocketSignaling(ip_address, port)
    pc = RTCPeerConnection()
    video_sender = CustomVideoStreamTrack(camera_id)
    pc.addTrack(video_sender)
    
    try:
        await signaling.connect()
        
        @pc.on("datachannel")
        def on_datachannel(channel):
            print(f"Data channel established: {channel.label}")
        
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"Connection state is {pc.connectionState}")
            if pc.connectionState == "connected":
                print("WebRTC connection established successfully")
        
        # Create and send offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await signaling.send(pc.localDescription)
        
        # Handle signaling
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
        # Clean up
        video_sender.cap.release()
        await pc.close()

async def main():
    ip_address = "192.168.1.151"  # IP Address of Remote Server/Machine
    port = 9999
    camera_id = "/home/walkenz1/Projects/WaterGun/loop.mp4"  # Video file path
    
    await setup_webrtc_and_run(ip_address, port, camera_id)

if __name__ == "__main__":
    asyncio.run(main())