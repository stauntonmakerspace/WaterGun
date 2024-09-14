from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2
import numpy as np
import socket
import time
from boxmot import DeepOCSORT
from ultralytics import YOLO
import json
from watergun.common import calculate_pan_tilt, pixel_to_meter
import os
import logging
import sys
import pygame
from watergun.common.draw import draw_crosshair



def setup_logger():
    logger = logging.getLogger('video_tracking_logger')
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s,%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def load_floor_corners(file_path, frame_width, frame_height):
    try:
        floor_corners = np.load(file_path)
        src_pts = np.array([[0, 0], [frame_width-1, 0], [frame_width-1, frame_height-1], [0, frame_height-1]], dtype=np.float32)
        dst_pts = floor_corners.astype(np.float32)
        perspective_transform = cv2.getPerspectiveTransform(src_pts, dst_pts)
        inverse_perspective_transform = cv2.getPerspectiveTransform(dst_pts, src_pts)
        print("Floor corners loaded and perspective transform matrices calculated.")
        return floor_corners, perspective_transform, inverse_perspective_transform
    except Exception as e:
        print(f"Failed to load floor corners: {e}")
        return None, None, None
    
class VideoTrackingApp:
    def __init__(self, window, video_source=0):
        self.window = window
        self.window.title("Sprayer Control App")

        self.vid = cv2.VideoCapture(video_source)
        self.frame_width = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Set maximum display dimensions
        self.max_display_width = 800
        self.max_display_height = 600

        # Initialize display dimensions
        self.display_width = self.max_display_width
        self.display_height = self.max_display_height

        # Calculate the initial scaling factor
        self.update_scale_factor()

        self.yolo_model = YOLO('models/yolov8n.pt')
        self.tracker = DeepOCSORT(
            model_weights=Path('models/osnet_x0_25_msmt17.pt'),
            device='cpu',
            fp16=False,
        )

        self.floor_corners, self.perspective_transform, self.inverse_perspective_transform = load_floor_corners(
            os.getenv('FLOOR_CORNERS_FILE','assets/floor_corners.npy'), self.frame_width, self.frame_height)
        with open("calibration_results.json", "r") as f:
            self.calibration_results = json.load(f)

        self.current_target_index = 0
        self.tracks = []
        self.debug_mode = tk.BooleanVar(value=False)
        self.targeting_mode = tk.StringVar(value="cursor")
        self.firing_mode = tk.StringVar(value="toggle")
        self.target_hold_time = tk.DoubleVar(value=5.0)
        self.cursor_target = [self.frame_width // 2, self.frame_height // 2]
        self.last_target_switch_time = 0

        self.sprayer_address = tk.StringVar(value="127.0.0.1")
        self.sprayer_port = tk.IntVar(value=1632)
        self.connection_status = tk.StringVar(value="Disconnected")
        self.socket = None
        self.is_firing = False
        self.logger = setup_logger()

        self.update_interval = 1.0 / 30  # 30 updates per second
        self.last_update_time = time.time()

        self.joystick = None
        # if pygame.joystick.get_count() > 0:
        #     self.joystick = pygame.joystick.Joystick(0)
        #     self.joystick.init()

        self.create_ui()

    def create_ui(self):
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.window)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        video_frame = ttk.Frame(main_frame)
        video_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)

        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=1, padx=10, pady=10, sticky="n")

        self.canvas = tk.Canvas(video_frame, width=self.display_width, height=self.display_height)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)


        ttk.Checkbutton(control_frame, text="Debug Mode", variable=self.debug_mode).pack(anchor="w", pady=5)

        ttk.Label(control_frame, text="Targeting Mode:").pack(anchor="w", pady=5)
        ttk.Radiobutton(control_frame, text="Auto", variable=self.targeting_mode, value="automatic").pack(anchor="w")
        ttk.Radiobutton(control_frame, text="Cursor", variable=self.targeting_mode, value="cursor").pack(anchor="w")
        ttk.Radiobutton(control_frame, text="Joystick", variable=self.targeting_mode, value="joystick").pack(anchor="w")

        ttk.Label(control_frame, text="(Cursor) Firing Mode:").pack(anchor="w", pady=5)
        ttk.Radiobutton(control_frame, text="Toggle", variable=self.firing_mode, value="toggle").pack(anchor="w")
        ttk.Radiobutton(control_frame, text="Hold to Fire", variable=self.firing_mode, value="hold").pack(anchor="w")

        ttk.Label(control_frame, text="(Auto) Target Hold Time (s):").pack(anchor="w", pady=5)
        ttk.Scale(control_frame, from_=1, to=10, variable=self.target_hold_time, orient="horizontal").pack(anchor="w")

        ttk.Label(control_frame, text="Sprayer Address:").pack(anchor="w", pady=5)
        ttk.Entry(control_frame, textvariable=self.sprayer_address).pack(anchor="w")

        ttk.Label(control_frame, text="Sprayer Port:").pack(anchor="w", pady=5)
        ttk.Entry(control_frame, textvariable=self.sprayer_port).pack(anchor="w")

        ttk.Label(control_frame, text="Connection Status:").pack(anchor="w", pady=5)
        ttk.Label(control_frame, textvariable=self.connection_status).pack(anchor="w")

        ttk.Button(control_frame, text="Refresh Connection", command=self.refresh_connection).pack(anchor="w", pady=5)

        self.window.after(10, self.update)

    def on_canvas_click(self, event):
        if self.targeting_mode.get() == "cursor":
            if self.firing_mode.get() == "toggle":
                self.is_firing = not self.is_firing
            elif self.firing_mode.get() == "hold":
                self.is_firing = True

    def on_canvas_release(self, event):
        if self.targeting_mode.get() == "cursor" and self.firing_mode.get() == "hold":
            self.is_firing = False

    def refresh_connection(self):
        if self.socket:
            self.socket.close()

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.sprayer_address.get(), self.sprayer_port.get()))
            self.connection_status.set("Connected")
        except Exception as e:
            self.connection_status.set(f"Connection failed: {str(e)}")
            self.socket = None

    def send_sprayer_command(self, pan_angle, tilt_angle, trigger):
        if self.socket:
            try:
                data = f"{pan_angle},{tilt_angle},{trigger},0\n"  # 0 for red_button as it's not used
                self.socket.sendall(data.encode())
                self.logger.info(f"{pan_angle},{tilt_angle},{trigger}")
            except Exception as e:
                print(f"Error sending command: {str(e)}")
                self.connection_status.set("Connection lost")
                self.socket = None

    def update_scale_factor(self):
        # Calculate the scaling factor while maintaining aspect ratio
        width_scale = self.display_width / self.frame_width
        height_scale = self.display_height / self.frame_height
        self.scale_factor = min(width_scale, height_scale)

        # Update the actual display dimensions to maintain aspect ratio
        self.display_width = int(self.frame_width * self.scale_factor)
        self.display_height = int(self.frame_height * self.scale_factor)

    def on_canvas_resize(self, event):
        # Update the canvas size
        self.display_width = event.width
        self.display_height = event.height
        
        # Recalculate the scaling factor and update display dimensions
        self.update_scale_factor()

    def update(self):
        ret, frame = self.vid.read()
        if ret:
            current_time = time.time()
            if current_time - self.last_update_time >= self.update_interval:
                self.process_frame(frame)
                self.last_update_time = current_time

            if self.debug_mode.get():
                self.draw_debug_info(frame)

            # Resize the frame for display while maintaining aspect ratio
            display_frame = cv2.resize(frame, (self.display_width, self.display_height))
            
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)))
            
            # Calculate position to center the image on the canvas
            x_position = (self.canvas.winfo_width() - self.display_width) // 2
            y_position = (self.canvas.winfo_height() - self.display_height) // 2
            
            # Clear previous image and draw new one
            self.canvas.delete("all")
            self.canvas.create_image(x_position, y_position, image=self.photo, anchor=tk.NW)

        self.window.after(10, self.update)

    def on_mouse_move(self, event):
        if self.targeting_mode.get() == "cursor":
            # Convert display coordinates to original frame coordinates
            canvas_x = self.canvas.winfo_width()
            canvas_y = self.canvas.winfo_height()
            x_offset = (canvas_x - self.display_width) // 2
            y_offset = (canvas_y - self.display_height) // 2
            
            x = int((event.x - x_offset) / self.scale_factor)
            y = int((event.y - y_offset) / self.scale_factor)
            
            # Ensure coordinates are within frame boundaries
            x = max(0, min(x, self.frame_width - 1))
            y = max(0, min(y, self.frame_height - 1))
            
            self.cursor_target = [x, y]
    def process_frame(self, frame):
        mode = self.targeting_mode.get()
        if mode == "automatic":
            target = self.process_automatic_mode(frame)
        elif mode == "cursor":
            target = self.process_cursor_mode(frame)
        elif mode == "joystick":
            target = self.process_joystick_mode(frame)
        else:
            target = None

        if target:
            pixel_x, pixel_y, is_firing = target
            draw_crosshair(frame, pixel_x, pixel_y)
            meter_x, meter_y = pixel_to_meter(pixel_x, pixel_y, self.perspective_transform)
            pan, tilt = calculate_pan_tilt(meter_x, meter_y, 0, 
                                           [self.calibration_results["height"],
                                            self.calibration_results["initial_pan"],
                                            self.calibration_results["initial_tilt"],
                                            self.calibration_results["initial_roll"]])
            self.send_sprayer_command(pan, tilt, 1 if is_firing else 0)

    def process_yolo_results(self, results):
        dets = []
        total_area = self.frame_width * self.frame_height
        min_area = 0.003 * total_area  # 0.3% of total area
        max_area = 0.9 * total_area    # 30% of total area

        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = box.conf[0].cpu().numpy()
                cls = box.cls[0].cpu().numpy()
                
                # Calculate the area of the detection
                area = (x2 - x1) * (y2 - y1)
                
                # Only include detections within the specified area range
                if min_area <= area <= max_area:
                    dets.append([x1, y1, x2, y2, conf, cls])

        return np.array(dets)

    def process_automatic_mode(self, frame):
        results = self.yolo_model(frame, verbose=False)
        dets = self.process_yolo_results(results)

        if len(dets) > 0:
            self.tracks = self.tracker.update(dets, frame)
        else:
            self.tracks = self.tracker.update(np.empty((0, 6)), frame)

        current_time = time.time()
        if current_time - self.last_target_switch_time > self.target_hold_time.get():
            self.current_target_index = (self.current_target_index + 1) % max(1, len(self.tracks))
            self.last_target_switch_time = current_time

        for i, track in enumerate(self.tracks):
            x1, y1, x2, y2, track_id = track[:5]
            center_x = int((x1 + x2) / 2)
            bottom_y = int(y2)

            if i == self.current_target_index:
                return center_x, bottom_y, self.is_firing

        return None

    def process_cursor_mode(self, frame):
        x, y = self.cursor_target
        return x, y, self.is_firing


    def process_joystick_mode(self, frame):
        if self.joystick:
            pygame.event.pump()
            x = -self.joystick.get_axis(0)
            y = -self.joystick.get_axis(1)
            trigger = self.joystick.get_button(5)

            pan_angle = int((x + 1) * 90)  # Map -1 to 1 to 0 to 180
            tilt_angle = int((-y + 1) * 90)  # Map -1 to 1 to 0 to 180, and invert y

            x_pixel = int(pan_angle / 180 * self.frame_width)
            y_pixel = int((180 - tilt_angle) / 180 * self.frame_height)

            return x_pixel, y_pixel, trigger == 1

        return None
   
    def draw_debug_info(self, frame):
        for i in range(4):
            cv2.line(frame, tuple(self.floor_corners[i]), tuple(self.floor_corners[(i+1)%4]), (0, 255, 255), 2)

        for track in self.tracks:
            x1, y1, x2, y2, track_id = track[:5]
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(frame, f"ID: {int(track_id)}", (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoTrackingApp(root)
    root.mainloop()