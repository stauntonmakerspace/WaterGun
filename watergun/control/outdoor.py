import socket
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
    # Set up socket server
    HOST = '0.0.0.0'  # Listen on all available interfaces
    PORT = 1632        # Port to listen on
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    print(f"Server listening on {HOST}:{PORT}")

    # Set up serial connection
    # ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    # time.sleep(2)  # Wait for the connection to establish

    logger = None
    if enable_logging:
        logger = setup_logger()

    print("pan_angle,tilt_angle,trigger,red_button", file=sys.stderr)

    update_interval = 1.0 / 30  # 30 updates per second
    last_update_time = time.time()

    try:
        conn, addr = server_socket.accept()
        print(f"Connected by {addr}")
        while True:
            data = conn.recv(1024)
            if not data:
                break

            decoded_data = data.decode('utf-8').strip()
            print(f"Received from client: {decoded_data}")

            current_time = time.time()
            if current_time - last_update_time >= update_interval:
                # Send data over serial
                # ser.write(data)

                if logger:
                    logger.info(decoded_data)

                last_update_time = current_time

    except KeyboardInterrupt:
        print("Exiting...", file=sys.stderr)
    finally:
        if 'conn' in locals():
            conn.close()
        server_socket.close()
        # ser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Joystick data receiver server with 30 updates per second")
    parser.add_argument("--log", action="store_true", help="Enable logging to stdout")
    args = parser.parse_args()

    main(args.log)