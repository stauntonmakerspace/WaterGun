send_command()

import socket
import threading

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432        # Port to listen on (non-privileged ports are > 1023)

def handle_client(conn, addr):
    print(f"Connected by {addr}")
    while True:
        data = conn.recv(1024)
        if not data:
            break
        print(f"Received from {addr}: {data.decode('utf-8')}")
        conn.sendall(data)  # Echo back the received data
    print(f"Connection closed by {addr}")
    conn.close()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()

if __name__ == "__main__":
    start_server()