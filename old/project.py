import cv2
import numpy as np
import logging
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Global variables
crosshair_img = None
floor_corners = None
image_offset = [0, 0]  # [x, y] offset in meters
pixels_per_meter = int(os.getenv('PIXELS_PER_METER', 100))
crosshair_scale = float(os.getenv('CROSSHAIR_SCALE', 1.0))

def load_crosshair(crosshair_file):
    global crosshair_img
    crosshair = cv2.imread(crosshair_file, cv2.IMREAD_UNCHANGED)
    if crosshair is None:
        logging.error(f"Failed to load crosshair image: {crosshair_file}")
        return None
    
    max_size = 100
    h, w = crosshair.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        crosshair = cv2.resize(crosshair, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        logging.info(f"Resized crosshair to fit within {max_size}x{max_size}")
    
    crosshair_size_meters = (crosshair.shape[1] / pixels_per_meter * crosshair_scale, 
                            crosshair.shape[0] / pixels_per_meter * crosshair_scale)
    logging.info(f"Crosshair size: {crosshair_size_meters[0]:.2f}m x {crosshair_size_meters[1]:.2f}m")
    crosshair_img = crosshair

def load_floor_corners(floor_corners_file):
    global floor_corners
    try:
        floor_corners = np.load(floor_corners_file)
    except Exception as e:
        logging.error(f"Failed to load floor corners: {e}")

def project_crosshair(frame):
    if crosshair_img is None or floor_corners is None:
        return frame

    h, w = frame.shape[:2]
    crosshair_h, crosshair_w = crosshair_img.shape[:2]

    crosshair_frame = np.zeros((h, w, 4), dtype=np.uint8)

    x = (w - crosshair_w) // 2
    y = (h - crosshair_h) // 2

    if crosshair_img.shape[2] == 4:
        crosshair_frame[y:y+crosshair_h, x:x+crosshair_w] = crosshair_img
    else:
        crosshair_frame[y:y+crosshair_h, x:x+crosshair_w, :3] = crosshair_img
        crosshair_frame[y:y+crosshair_h, x:x+crosshair_w, 3] = 255

    offset_x = int(image_offset[0] * pixels_per_meter)
    offset_y = int(image_offset[1] * pixels_per_meter)

    src_pts = np.array([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]], dtype=np.float32)

    src_center = np.mean(src_pts, axis=0)
    dst_center = np.mean(floor_corners, axis=0)
    translation = dst_center - src_center
    src_pts += translation

    src_pts += np.array([offset_x, offset_y])

    dst_pts = floor_corners.astype(np.float32)

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)

    warped = cv2.warpPerspective(crosshair_frame, M, (w, h))

    alpha = warped[:,:,3] / 255.0
    for c in range(3):
        frame[:,:,c] = frame[:,:,c] * (1 - alpha) + warped[:,:,c] * alpha

    return frame

def process_stream():
    cap = cv2.VideoCapture(os.getenv('MJPG_STREAM_URL'))

    while True:
        ret, frame = cap.read()
        if not ret:
            logging.warning("Failed to read frame from stream")
            break

        frame_with_crosshair = project_crosshair(frame)

        cv2.putText(frame_with_crosshair, f"Offset: {image_offset[0]:.2f}m, {image_offset[1]:.2f}m", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('MJPG Stream with Projected Crosshair', frame_with_crosshair)

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

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    load_crosshair(os.getenv('CROSSHAIR_FILE'))
    load_floor_corners(os.getenv('FLOOR_CORNERS_FILE'))
    process_stream()
    
    
# get_box_area = lambda box: box[0]
# get_box_center = lambda box: (int(box[0] + ((box[2] - box[0])//2)), int(box[1] + ((box[3] - box[1]) //2)))
# distance = lambda p1, p2: ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**.5

# try:
#     camera = VideoStream(usePiCamera=True)
#     camera.start()
#     camera_matrix = np.load("camera_matrix.npy")
#     dist_coefficients = np.load("dist_coefficients.npy")
# except Exception as e:
#     raise(e)

# water_gun = WaterGun()
# water_gun.start()
# water_gun.center()

# tracker = NCS2_Wrapper(filter_for = set(["person", "dog"]))
# #tracker = TFLite_Wrapper("Sample_TFLite_model")

# lock_start = time.time()
# last_detection = time.time()

# scan_mode_started = False
# scan_pass_start = time.time()
# scan_time = 2
# scan_value = 100
# while True:
#     frame = camera.read()
#     frame = cv2.flip(frame, 0)
#     #frame = cv2.undistort(frame, camera_matrix, dist_coefficients, None, camera_matrix)
    