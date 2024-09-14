import cv2 
import os 
def draw_crosshair_on_floor():
    pass
def load_image(file_path, max_size=100):
    img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Failed to load image: {file_path}")
        return None
    
    h, w = img.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        print(f"Resized image to fit within {max_size}x{max_size}")
    
    return img

crosshair_img = load_image('/Users/walkenz1/Projects/WatGn/WaterGun/assets/crosshair.png')
def draw_crosshair(frame, center_x, center_y):
    ch_height, ch_width = crosshair_img.shape[:2]
    x_offset = int(center_x - ch_width // 2)
    y_offset = int(center_y - ch_height // 2)

    x_start = max(0, x_offset)
    y_start = max(0, y_offset)
    x_end = min(frame.shape[1], x_offset + ch_width)
    y_end = min(frame.shape[0], y_offset + ch_height)

    ch_x_start = x_start - x_offset
    ch_y_start = y_start - y_offset
    ch_x_end = ch_x_start + (x_end - x_start)
    ch_y_end = ch_y_start + (y_end - y_start)

    if x_end > x_start and y_end > y_start:
        alpha_s = crosshair_img[ch_y_start:ch_y_end, ch_x_start:ch_x_end, 3] / 255.0
        alpha_l = 1.0 - alpha_s

        for c in range(0, 3):
            frame[y_start:y_end, x_start:x_end, c] = (alpha_s * crosshair_img[ch_y_start:ch_y_end, ch_x_start:ch_x_end, c] +
                                                        alpha_l * frame[y_start:y_end, x_start:x_end, c])
