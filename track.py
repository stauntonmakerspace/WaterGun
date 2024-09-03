import cv2
import numpy as np
from pathlib import Path
from boxmot import DeepOCSORT
from ultralytics import YOLO
import json
from watergun.common import calculate_pan_tilt
import os
from dotenv import load_dotenv

def load_crosshair(crosshair_file, pixels_per_meter, crosshair_scale):
    crosshair = cv2.imread(crosshair_file, cv2.IMREAD_UNCHANGED)
    if crosshair is None:
        print(f"Failed to load crosshair image: {crosshair_file}")
        return None
    
    max_size = 100
    h, w = crosshair.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        crosshair = cv2.resize(crosshair, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        print(f"Resized crosshair to fit within {max_size}x{max_size}")
    
    crosshair_size_meters = (crosshair.shape[1] / pixels_per_meter * crosshair_scale, 
                            crosshair.shape[0] / pixels_per_meter * crosshair_scale)
    print(f"Crosshair size: {crosshair_size_meters[0]:.2f}m x {crosshair_size_meters[1]:.2f}m")
    return crosshair

def load_floor_corners(floor_corners_file, frame_width, frame_height):
    try:
        floor_corners = np.load(floor_corners_file)
        
        # Calculate perspective transform matrix
        src_pts = np.array([[0, 0], [frame_width-1, 0], [frame_width-1, frame_height-1], [0, frame_height-1]], dtype=np.float32)
        dst_pts = floor_corners.astype(np.float32)
        perspective_transform = cv2.getPerspectiveTransform(src_pts, dst_pts)
        
        print("Floor corners loaded and perspective transform matrix calculated.")
        return floor_corners, perspective_transform
    except Exception as e:
        print(f"Failed to load floor corners: {e}")
        return None, None

def create_crosshair_variants(crosshair_img):
    if crosshair_img.shape[2] == 4:
        selected_crosshair = crosshair_img.copy()
    else:
        selected_crosshair = cv2.cvtColor(crosshair_img, cv2.COLOR_BGR2BGRA)

    non_selected_crosshair = selected_crosshair.copy()
    non_selected_crosshair[:, :, [0, 2]] = non_selected_crosshair[:, :, [2, 0]]

    return selected_crosshair, non_selected_crosshair

def pixel_to_meter(pixel_x, pixel_y, perspective_transform):
    px_homogeneous = np.array([[pixel_x, pixel_y, 1]], dtype=np.float32).T
    meter_homogeneous = perspective_transform @ px_homogeneous
    meter_x, meter_y, _ = meter_homogeneous.ravel() / meter_homogeneous[2]
    return meter_x, meter_y

def main():
    # Load environment variables
    load_dotenv()

    # Load calibration results
    with open("calibration_results.json", "r") as f:
        calibration_results = json.load(f)

    # Initialize the tracker
    tracker = DeepOCSORT(
        model_weights=Path('models/osnet_x0_25_msmt17.pt'),
        device='cuda:0',
        fp16=False,
    )

    # Initialize YOLOv8 model
    yolo_model = YOLO('models/yolov8n.pt')

    # Open video stream
    vid = cv2.VideoCapture(0)#os.getenv('MJPG_STREAM_URL'))

    # Get video properties
    frame_width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Initialize variables
    current_target_index = 0
    image_offset = [0, 0]  # [x, y] offset in meters
    pixels_per_meter = int(os.getenv('PIXELS_PER_METER', 100))
    crosshair_scale = float(os.getenv('CROSSHAIR_SCALE', 1.0))

    # Load crosshair and floor corners
    crosshair_img = load_crosshair(os.getenv('CROSSHAIR_FILE'), pixels_per_meter, crosshair_scale)
    floor_corners, perspective_transform = load_floor_corners(os.getenv('FLOOR_CORNERS_FILE'), frame_width, frame_height)

    # Create crosshair variants
    selected_crosshair, non_selected_crosshair = create_crosshair_variants(crosshair_img)

    # Pre-calculate the crosshair transform matrix
    src_pts = np.array([[0, 0], [frame_width-1, 0], [frame_width-1, frame_height-1], [0, frame_height-1]], dtype=np.float32)
    src_center = np.mean(src_pts, axis=0)
    dst_center = np.mean(floor_corners, axis=0)
    translation = dst_center - src_center
    src_pts += translation
    crosshair_transform = cv2.getPerspectiveTransform(src_pts, floor_corners.astype(np.float32))

    while True:
        ret, im = vid.read()
        if not ret:
            break

        # Run YOLOv8 detection
        results = yolo_model(im,verbose=False)

        # Extract detections in the format required by DeepOCSORT
        dets = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = box.conf[0].cpu().numpy()
                cls = box.cls[0].cpu().numpy()
                dets.append([x1, y1, x2, y2, conf, cls])
        dets = np.array(dets)

        if len(dets) > 0:
            # Update tracker
            tracks = tracker.update(dets, im)
        else:
            tracks = tracker.update(np.empty((0, 6)), im)

        # Ensure current_target_index is within bounds
        if tracks.shape[0] > 0:
            current_target_index = current_target_index % tracks.shape[0]
        else:
            current_target_index = 0

        # Create a list to store crosshair positions and selection status
        crosshair_data = []

        # Process tracks
        for i, track in enumerate(tracks):
            x1, y1, x2, y2, track_id = track[:5]
            center_x = int((x1 + x2) / 2)
            bottom_y = int(y2)

            is_selected = (i == current_target_index)
            crosshair_data.append((center_x, bottom_y, is_selected))

            if is_selected:
                # Selected track: calculate pan/tilt
                meter_x, meter_y = pixel_to_meter(center_x, bottom_y, perspective_transform)

                pan, tilt = calculate_pan_tilt(meter_x, meter_y, 0, 
                                               [calibration_results["height"],
                                                calibration_results["initial_pan"],
                                                calibration_results["initial_tilt"],
                                                calibration_results["initial_roll"]])

                # Display pan and tilt for selected track
                cv2.putText(im, f"ID: {track_id}, Pan: {pan:.2f}, Tilt: {tilt:.2f}", 
                            (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Create a single crosshair frame for all tracks
        all_crosshairs = np.zeros((im.shape[0], im.shape[1], 4), dtype=np.uint8)

        # Draw all crosshairs
        for center_x, bottom_y, is_selected in crosshair_data:
            crosshair = selected_crosshair if is_selected else non_selected_crosshair
            ch_height, ch_width = crosshair.shape[:2]
            x_offset = int(center_x - ch_width // 2)
            y_offset = int(bottom_y - ch_height)

            # Ensure the crosshair is within the frame bounds
            x_start = max(0, x_offset)
            y_start = max(0, y_offset)
            x_end = min(all_crosshairs.shape[1], x_offset + ch_width)
            y_end = min(all_crosshairs.shape[0], y_offset + ch_height)

            ch_x_start = x_start - x_offset
            ch_y_start = y_start - y_offset
            ch_x_end = ch_x_start + (x_end - x_start)
            ch_y_end = ch_y_start + (y_end - y_start)

            all_crosshairs[y_start:y_end, x_start:x_end] = cv2.add(
                all_crosshairs[y_start:y_end, x_start:x_end],
                crosshair[ch_y_start:ch_y_end, ch_x_start:ch_x_end]
            )

        # Project all crosshairs at once
        warped = cv2.warpPerspective(all_crosshairs, crosshair_transform, (im.shape[1], im.shape[0]))
        alpha = warped[:,:,3] / 255.0
        for c in range(3):
            im[:,:,c] = im[:,:,c] * (1 - alpha) + warped[:,:,c] * alpha

        # Display offset information
        cv2.putText(im, f"Offset: {image_offset[0]:.2f}m, {image_offset[1]:.2f}m", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Display the image
        cv2.imshow('YOLOv8 + DeepOCSORT tracking with Projected Crosshair', im)

        # Handle key presses
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d'):  # Left arrow
            image_offset[0] -= 0.1
        elif key == ord('a'):  # Right arrow
            image_offset[0] += 0.1
        elif key == ord('s'):  # Up arrow
            image_offset[1] -= 0.1
        elif key == ord('w'):  # Down arrow
            image_offset[1] += 0.1
        elif key == 82:  # Up arrow
            current_target_index = (current_target_index - 1) % max(1, tracks.shape[0])
        elif key == 84:  # Down arrow
            current_target_index = (current_target_index + 1) % max(1, tracks.shape[0])

    vid.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()