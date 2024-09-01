import pygame
import serial
import time
import logging
import sys
import argparse
def setup_logger():
    logger = logging.getLogger('joystick_logger')
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s,%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def main(enable_logging):
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No joystick detected. Please connect a Sony controller.", file=sys.stderr)
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    ser = serial.Serial('/dev/tty.usbmodem11301', 115200, timeout=1)
    time.sleep(2)  # Wait for the connection to establish

    logger = None
    if enable_logging:
        logger = setup_logger()
        print("pan_angle,tilt_angle,trigger,red_button", file=sys.stderr)

    update_interval = 1.0 / 30  # 30 updates per second
    last_update_time = time.time()

    try:
        while True:
            current_time = time.time()
            if current_time - last_update_time >= update_interval:
                pygame.event.pump()
                
                x = joystick.get_axis(0)
                y = joystick.get_axis(1)
                trigger = int(joystick.get_button(5))  # Convert to int (0 or 1)
                red_button = int(joystick.get_button(1))  # Convert to int (0 or 1)
                
                # Convert joystick values to angles (0-180)
                pan_angle = int((x + 1) * 90)  # Map -1 to 1 to 0 to 180
                tilt_angle = int((-y + 1) * 90)  # Map -1 to 1 to 0 to 180, and invert y
                
                data = f"{pan_angle},{tilt_angle},{trigger},{red_button}\n"
                ser.write(data.encode())
                
                if logger:
                    logger.info(f"{pan_angle},{tilt_angle},{trigger},{red_button}")
                
                last_update_time = current_time

    except KeyboardInterrupt:
        print("Exiting...", file=sys.stderr)
        ser.close()
        pygame.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Joystick reader with 30 updates per second")
    parser.add_argument("--log", action="store_true", help="Enable logging to stdout")
    args = parser.parse_args()

    main(args.log)