import asyncio
import cv2
import numpy as np
import json
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCDataChannel
from aiortc.contrib.signaling import TcpSocketSignaling
from av import VideoFrame
from datetime import datetime, timedelta

class VideoReceiver:
    def __init__(self):
        self.track = None
        self.data_channel = None

    def mouse_callback(self, event, x, y, flags, param):
            # """Mouse callback function to handle click events"""
            if self.data_channel and self.data_channel.readyState == "open":
                try:
                    # Send click coordinates through data channel
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
        
        # Set up the display window and mouse callback
        cv2.namedWindow("Frame", cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback("Frame", self.mouse_callback)
        
        while True:
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=1.0)
                frame = frame.to_ndarray(format="bgr24")
              
                # Add timestamp to the frame
                current_time = datetime.now()
                timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                cv2.putText(frame, timestamp, (10, frame.shape[0] - 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

                # Display the frame
                cv2.imshow("Frame", frame)
                
                # Exit on 'q' key press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
            except asyncio.TimeoutError:
                print("Timeout waiting for frame, continuing...")
        
        # Clean up
        cv2.destroyAllWindows()
        print("Exiting handle_track")

async def run(pc, signaling):
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
    print("Click on the video window to send coordinates!")
    await asyncio.sleep(100)  # Wait for 100 seconds to receive frames

    print("Closing connection")

async def main():
    signaling = TcpSocketSignaling("127.0.0.1", 9999)
    pc = RTCPeerConnection()
    
    global video_receiver
    video_receiver = VideoReceiver()

    try:
        await run(pc, signaling)
    except Exception as e:
        print(f"Error in main: {str(e)}")
    finally:
        print("Closing peer connection")
        await pc.close()

if __name__ == "__main__":
    asyncio.run(main())