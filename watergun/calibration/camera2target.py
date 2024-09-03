import cv2
import numpy as np

def select_floor_corners():
    cap = cv2.VideoCapture(0)
    floor_corners = []
    corner_names = ["top-left", "top-right", "bottom-right", "bottom-left"]

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(floor_corners) < 4:
            floor_corners.append((x, y))
            print(f"Selected {corner_names[len(floor_corners)-1]} corner: ({x}, {y})")

    cv2.namedWindow('Floor Selection')
    cv2.setMouseCallback('Floor Selection', mouse_callback)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        for corner in floor_corners:
            cv2.circle(frame, corner, 5, (0, 255, 0), -1)

        remaining_corners = 4 - len(floor_corners)
        if remaining_corners > 0:
            current_corner = corner_names[len(floor_corners)]
            cv2.putText(frame, f"Select {current_corner} corner", 
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Remaining: {remaining_corners}", 
                        (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            print(f"\rNext corner to select: {current_corner}", end="", flush=True)
        else:
            cv2.putText(frame, "All corners selected. Press 'q' to quit.", 
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            print("\rAll corners selected. Press 'q' to quit.", end="", flush=True)

        cv2.imshow('Floor Selection', frame)

        if cv2.waitKey(1) & 0xFF == ord('q') or len(floor_corners) == 4:
            break

    cap.release()
    cv2.destroyAllWindows()
    
    # Save floor corners
    np.save('assets/floor_corners.npy', floor_corners)
    print("\nFloor corners saved to 'floor_corners.npy'")
    return floor_corners

if __name__ == "__main__":
    print("\nStarting floor corner selection...")
    print("Please select the corners in this order: top-left, top-right, bottom-right, bottom-left")
    select_floor_corners()
    
    print("\nSetup and calibration complete!")