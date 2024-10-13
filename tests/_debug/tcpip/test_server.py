from __future__ import annotations

import socket

# Define host and port
HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65432  # Port to listen on (non-privileged ports are > 1023)

# Create a socket object
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
    # Bind the socket to the address and port
    server_socket.bind((HOST, PORT))

    # Listen for incoming connections
    server_socket.listen()

    print(f"Server is listening on {HOST}:{PORT}")

    # Accept connections from clients
    connection, address = server_socket.accept()
    with connection:
        print(f"Connected to {address}")

        while True:
            # Receive data from the client
            data = connection.recv(1024)
            if not data:
                break  # If no data is received, break the loop

            # Decode and print the received data
            print(f"Received message: {data.decode('utf-8')}")

            # You can add your processing logic here

            # Optionally, send a response back to the client
            # connection.sendall(response.encode('utf-8'))
