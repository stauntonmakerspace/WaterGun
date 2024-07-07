import cv2
import numpy as np
from pathlib import Path
from boxmot import DeepOCSORT
from ultralytics import YOLO

# Initialize the tracker
tracker = DeepOCSORT(
    model_weights=Path('models/osnet_x0_25_msmt17.pt'),  # which ReID model to use
    device='cuda:0',
    fp16=False,
)

# Initialize YOLOv8 model
yolo_model = YOLO('models/yolov8n.pt')

# Open video stream
vid = cv2.VideoCapture('http://192.168.1.161:8000/stream.mjpg')

while True:
    ret, im = vid.read()
    if not ret:
        break

    # Run YOLOv8 detection
    results = yolo_model(im)

    # Extract detections in the format required by DeepOCSORT
    dets = []
    for r in results:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()  # Convert to CPU and then to numpy
            conf = box.conf[0].cpu().numpy()
            cls = box.cls[0].cpu().numpy()
            dets.append([x1, y1, x2, y2, conf, cls])

    dets = np.array(dets)

    if len(dets) > 0:
        # Update tracker
        tracker.update(dets, im)  # --> M X (x, y, x, y, id, conf, cls, ind)
        
        # Plot results
        tracker.plot_results(im, show_trajectories=True)
    else:
        tracker.update(np.empty((0, 6)),im)

    # Display the image
    cv2.imshow('YOLOv8 + DeepOCSORT tracking', im)

    # Break on pressing q or space
    key = cv2.waitKey(1) & 0xFF
    if key == ord(' ') or key == ord('q'):
        break

vid.release()
cv2.destroyAllWindows()