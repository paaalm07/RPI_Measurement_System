from __future__ import annotations

import socket


def receive_messages(host, port):
    # Create a socket object
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Connect to the server
        print(f"connect to: {host}:{port}")
        client_socket.connect((host, port))

        print("wait for receiving data...")

        while True:
            # Receive data from the server
            message = client_socket.recv(1024).decode()

            # If the message is empty, the server has closed the connection
            if not message:
                print("Server closed the connection.")
                break

            # Print the received message
            print("Received:", message)

    except ConnectionRefusedError:
        print("Connection refused. Make sure the server is running.")
    except Exception as e:
        print("An error occurred:", e)
    finally:
        # Close the socket
        client_socket.close()


if __name__ == "__main__":
    # Set the host and port of the server
    host = "192.168.1.42"  # 42=IFX, 20=PC
    port = 8008

    receive_messages(host, port)
