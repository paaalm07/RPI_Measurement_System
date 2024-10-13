from __future__ import annotations

import socket
import threading
import time
from typing import List, Protocol

from MeasurementSystem.core.comvisu.Command import Command
from MeasurementSystem.core.Utils import OrderedPriorityQueue


class ServerConnection:
    """
    A class representing a connection to a server.

    This class provides methods for establishing and managing a connection to a server.
    It allows for sending commands to the server and receiving data in response.

    :param name: The name of the connection.
    :type name: str
    :param server_address: The address of the server to connect to, given as a tuple of IP address and port.
    :type server_address: tuple
    :param timeout: The timeout for establishing the connection. Defaults to 5 seconds.
    :type timeout: int

    :return: Instance of ServerConnection
    :rtype: :class:`ServerConnection`
    """

    def __init__(self, name, server_address, timeout: int = 5):
        self.name = name
        self.server_address = server_address
        self._client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._client_socket.settimeout(timeout)
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """
        :return: True if the connection is open, False otherwise.
        :rtype: bool
        """
        return self._is_connected

    def connect(self) -> None:
        """
        Connect to the server.

        This method tries to connect to the server.
        If the connection is successful, the `is_connected` flag is
        set to `True`. If the connection fails, an exception is raised.

        :return: None
        :rtype: None

        :raises Exception: Any Exception raised.
        """
        try:
            print(f"try to connect to {self.server_address}...")
            self._client_socket.connect(self.server_address)
            self._is_connected = True
        except Exception as e:
            raise e

    def disconnect(self) -> None:
        """
        Disconnect from the server.

        This method closes the socket and sets the `is_connected` flag to `False`.

        :return: None
        :rtype: None
        """
        if self._is_connected:
            self._client_socket.close()
            self._is_connected = False

    def receive(self, bufsize: int = 1024) -> List[Command]:
        """
        Receive data from the server and return a list of Command objects.

        :param bufsize: The buffer size for receiving data. Defaults to 1024.
        :type bufsize: int

        :return: A list of Command objects containing the received data.
        :rtype: List[Command]

        :raises ConnectionError: If the connection to the server is lost.
        """

        try:
            print("receiving....")
            data = self._client_socket.recv(bufsize).decode()
            if not data:
                raise ConnectionError("Connection to the server lost.")

            print("Received:", data)

            split_data = data.split(";")
            commands = [Command(d + ";") for d in split_data[:-1]]

            return commands
        except Exception as e:
            raise e

    def send(self, command: Command) -> None:
        """
        Send a command to the server if connected.

        :param command: The Command object to send.
        :type command: Command

        :return: None
        :rtype: None

        :raises ConnectionError: If the connection to the server is lost.
        """

        if self._is_connected:
            try:
                self._client_socket.sendall(command.to_string().encode())
            except BrokenPipeError:
                raise ConnectionError("Connection to the server lost.")


class DataQueueThread:
    """
    A class representing a thread that processes a queue of data.

    :param data_queue: The queue of data to process.
    :type data_queue: OrderedPriorityQueue
    :param send_command_callback: A callback function to send commands to the server.
    :type send_command_callback: SendCommandCallbackType_3

    :return: Instance of DataQueueThread
    :rtype: :class:`DataQueueThread`
    """

    class SendCommandCallbackType_3(Protocol):
        """
        A protocol defining a callback function for sending commands.

        This protocol specifies the signature of a callback function that is called when sending a command.
        """

        def __call__(self, command: Command, priority: int = 5) -> None: ...

    def __init__(
        self,
        data_queue: OrderedPriorityQueue,
        send_command_callback: SendCommandCallbackType_3,
    ):
        self.data_queue = data_queue
        self.send_command_callback = send_command_callback

        self._stop_event = threading.Event()
        self._processing_thread = threading.Thread(target=self._dataqueue_processing_loop)
        self._processing_thread.daemon = True

    def start(self) -> None:
        """
        Starts the thread that runs the data queue processing loop.

        :return: None
        :rtype: None
        """
        self._processing_thread.start()

    def stop(self) -> None:
        """
        Stops the thread that runs the data queue processing loop. It also waits for the thread to finish.

        :return: None
        :rtype: None
        """
        self._stop_event.set()
        self._processing_thread.join()
        self._stop_event.clear()

    def _dataqueue_processing_loop(self) -> None:
        """
        Data queue processing loop.

        This method runs in a separate thread and processes the data queue. It gets
        commands from the queue, ueses the send_command_callback to send them to the server,
        and updates the queue status every 20 iterations. If the queue is empty, it sends a message to the server
        indicating that the queue is empty and waits for 0.5 seconds before checking the queue again.

        Data queue processing loop is stopped when the stop_event is set.

        :return: None
        :rtype: None
        """

        data_queue_empty_not_sent = True

        i_loop = 0
        while not self._stop_event.is_set():
            i_loop += 1

            try:
                if not self.data_queue.empty():
                    data_queue_empty_not_sent = True

                    command, priority = self.data_queue.get()
                    assert isinstance(command, Command)

                    # Send command to the server
                    self.send_command_callback(command)

                    if i_loop % 20 == 0:
                        # Queue status update
                        # self.send_command_callback(f"#990SData in queue: {self.data_queue.qsize()};")
                        self.send_command_callback(
                            Command(
                                990,
                                Command.Type.STRING,
                                f"Data in queue: {self.data_queue.qsize()}",
                            )
                        )

                    # delay for sending data (otherwise ComVisu overflow!)
                    time.sleep(0.01)
                else:
                    if data_queue_empty_not_sent:
                        # self.send_command_callback(f"#990SData Queue: empty;")
                        self.send_command_callback(Command(990, Command.Type.STRING, "Data Queue: empty"))
                        data_queue_empty_not_sent = False

                    time.sleep(0.5)  # Note: not too long for keep alive update
            except:
                break  # stop sending the data queue send loop
