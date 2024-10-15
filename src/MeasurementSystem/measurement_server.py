from __future__ import annotations

import importlib
import json
import os
import queue
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Protocol, Union

from MeasurementSystem.core.comvisu.Command import Command
from MeasurementSystem.core.comvisu.ServerUtils import DataQueueThread, ServerConnection
from MeasurementSystem.core.driver.BaseClasses import (
    Channel,
    ChannelManager,
    ChannelProperties,
    Hardware,
    InputChannel,
    InputModule,
    Module,
    MultiChannel,
    MultiHardware,
    OutputChannel,
    OutputModule,
)
from MeasurementSystem.core.driver.Data import Data
from MeasurementSystem.core.driver.DigilentMCC118 import Channel_MCC118_VoltageChannel, Hardware_DigilentMCC118
from MeasurementSystem.core.driver.DigilentMCC134 import Channel_MCC134_ThermocoupleChannel, Hardware_DigilentMCC134
from MeasurementSystem.core.driver.Models import (
    KTYxModel,
    LinearModel,
    Model,
    ModelMeta,
    NTCModel,
    PTxModel,
    StackedModel,
)
from MeasurementSystem.core.driver.RaspberryPi import (
    Channel_RPI_BufferedDigitalInput,
    Channel_RPI_DigitalInput,
    Channel_RPI_DigitalOutput,
    Channel_RPI_FrequencyCounter,
    Channel_RPI_InternalTemperature,
    Hardware_RaspberryPi,
    Module_RPI_ServoMotor,
    Module_RPI_StepperMotor,
    Module_RPI_WeighScalesHX711,
)
from MeasurementSystem.core.Utils import OrderedPriorityQueue, Serializable

current_dir = os.path.dirname(os.path.realpath(__file__))

LOCKFILE = "/tmp/measurement_server.lock"

default_server_address = ("192.168.1.31", 8008)


class HardwareInterface(Serializable):
    """
    A class representing the hardware interface.

    This class provides a way to manage and interact with the hardware interface.

    :param name: The name of the hardware interface.
    :type name: str

    :return: HardwareInterface instance
    :rtype: HardwareInterface
    """

    def __init__(self, name):
        self.name = name
        self.multi_hardware = MultiHardware(name="MeasurementSystem")

    def initialize(self) -> None:
        # Hardware: Raspberry Pi 5
        """
        Initialize the hardware interface.

        :return: None
        :rtype: None
        """

        _rpi_hardware = Hardware_RaspberryPi(name="RPI5")

        rpi_input_channels = [
            Channel_RPI_FrequencyCounter(
                handle=_rpi_hardware.handle,
                name="Speed1",
                pin=18,
                unit="rpm",
                model=LinearModel(offset=0, gain=1),
                sample_rate=1,
                chart_number=701,
                enabled=True,
            ),
            Channel_RPI_InternalTemperature(
                name="Temperature",
                unit="C",
                model=LinearModel(offset=0, gain=1),
                sample_rate=2,
                chart_number=729,
                enabled=True,
            ),
            Channel_RPI_DigitalOutput(handle=_rpi_hardware.handle, name="KeepAliveLED", pin=19, enabled=True),
        ]
        _rpi_hardware.add_channels(rpi_input_channels)

        rpi_multi_channels = [
            Module_RPI_StepperMotor(
                handle=_rpi_hardware.handle,
                name="StepperMotor",
                step_pin=24,
                dir_pin=25,
                enable_pin=16,
                limitA_pin=20,
                limitB_pin=21,
                enabled=True,
            ),
            Module_RPI_WeighScalesHX711(
                handle=_rpi_hardware.handle,
                name="HX711",
                data_pin=5,
                clock_pin=6,
                model=LinearModel(offset=0, gain=1),
                sample_rate=1,
                chart_number=745,
                enabled=True,
            ),
        ]
        _rpi_hardware.add_channels(rpi_multi_channels)

        # Hardware: Digilent MCC118
        _mcc118_hardware = Hardware_DigilentMCC118(name="MCC118", hat_address=0)

        mcc118_input_channels = [
            Channel_MCC118_VoltageChannel(
                handle=_mcc118_hardware._handle,
                channel=0,
                name="MCC118_0",
                unit="V",
                model=LinearModel(offset=0, gain=1),
                sample_rate=0.5,
                chart_number=767,
                enabled=True,
            ),
            Channel_MCC118_VoltageChannel(
                handle=_mcc118_hardware._handle,
                channel=1,
                name="MCC118_1",
                unit="V",
                model=LinearModel(offset=0, gain=1),
                sample_rate=1,
                chart_number=781,
                enabled=True,
            ),
            Channel_MCC118_VoltageChannel(
                handle=_mcc118_hardware._handle,
                channel=2,
                name="MCC118_2",
                unit="V",
                model=LinearModel(offset=0, gain=1),
                sample_rate=2,
                chart_number=789,
                enabled=True,
            ),
        ]

        _mcc118_hardware.add_channels(mcc118_input_channels)

        # Hardware: Digilent MCC134
        _mcc134_hardware = Hardware_DigilentMCC134(name="MCC134", hat_address=1)

        mcc134_input_channels = [
            Channel_MCC134_ThermocoupleChannel(
                handle=_mcc134_hardware._handle,
                channel=0,
                name="MCC134_0",
                unit="C",
                model=LinearModel(offset=0, gain=1),
                sample_rate=1,
                chart_number=721,
                enabled=True,
            ),
            Channel_MCC134_ThermocoupleChannel(
                handle=_mcc134_hardware._handle,
                channel=3,
                name="MCC134_3",
                unit="C",
                model=LinearModel(offset=0, gain=1),
                sample_rate=1,
                chart_number=724,
                enabled=True,
            ),
        ]
        _mcc134_hardware.add_channels(mcc134_input_channels)

        # MultiHardware
        self.multi_hardware.add_hardware(_rpi_hardware)
        self.multi_hardware.add_hardware(_mcc118_hardware)
        self.multi_hardware.add_hardware(_mcc134_hardware)

    def close(self) -> None:
        """
        Close the hardware interface.

        This method will close the hardware interface and remove all hardware
        instances from the internal list. This is necessary to prevent a memory
        leak when the hardware interface is recreated.

        :return: None
        :rtype: None
        """
        self.multi_hardware.close()
        self.multi_hardware.hardware_list.clear()  # NOTE: this may fix the bug????

    ############################
    # JSON Serialization
    #
    def to_json(
        self,
        hardware_file: str = "hardware.json",
        channels_file: str = "channels.json",
        modules_file: str = "modules.json",
    ):
        """
        Serialize the hardware interface to JSON files.

        This method will serialize the hardware interface to three JSON files: one
        for hardware, one for channels, and one for modules. The JSON files will be
        saved in the current working directory.

        The hardware file will contain a list of dictionaries, each representing a
        hardware object. The dictionaries will contain the hardware object's
        attributes, excluding any attributes that are lists or dicts containing
        Channel instances.

        The channels file will contain a list of dictionaries, each representing a
        channel object. The dictionaries will contain the channel object's
        attributes, including a reference to the parent hardware object.

        The modules file will contain a list of dictionaries, each representing a
        module object. The dictionaries will contain the module object's
        attributes, including a reference to the parent hardware object.

        :param hardware_file: The filename for the hardware file. Defaults to
            "hardware.json".
        :type hardware_file: str
        :param channels_file: The filename for the channels file. Defaults to
            "channels.json".
        :type channels_file: str
        :param modules_file: The filename for the modules file. Defaults to
            "modules.json".
        :type modules_file: str
        """

        hardware_objects = []
        channel_objects = []
        module_objects = []

        # Iterate over hardware and extract channels separately
        for hw in self.multi_hardware.hardware_list:
            # Convert hardware object to dictionary but exclude channels
            hardware_dict = hw.to_dict()

            # Remove attributes that are lists or dicts containing Channel instances
            def exclude_channels_and_modules(d):
                if isinstance(d, dict):
                    result = {}
                    for k, v in d.items():
                        if isinstance(v, list):
                            # Skip lists that contain Channel or Module instances
                            if any(isinstance(item, (Channel, Module)) for item in v):
                                continue
                            result[k] = exclude_channels_and_modules(v)
                        elif isinstance(v, dict):
                            result[k] = exclude_channels_and_modules(v)
                        else:
                            result[k] = v
                    return result
                return d

            hardware_dict["attributes"] = exclude_channels_and_modules(hardware_dict["attributes"])
            hardware_objects.append(hardware_dict)

            # Extract and serialize channels
            for channel in hw.get_channels():
                if not isinstance(channel, Module):
                    channel_dict = channel.to_dict()
                    channel_dict["parent_hardware"] = {
                        "id": id(hw),
                        "name": hw.name,
                        "class": hw.__class__.__name__,
                        "module": hw.__module__,
                    }
                    channel_objects.append(channel_dict)

            # Extract and serialize modules
            for module in hw.get_modules():
                module_dict = module.to_dict()
                module_dict["parent_hardware"] = {
                    "id": id(hw),
                    "name": hw.name,
                    "class": hw.__class__.__name__,
                    "module": hw.__module__,
                }
                module_objects.append(module_dict)

        # Save to JSON files
        with open(hardware_file, "w") as f:
            json.dump(
                hardware_objects,
                f,
                indent=4,
                default=lambda o: o.to_dict() if isinstance(o, Serializable) else None,
            )

        with open(channels_file, "w") as f:
            json.dump(
                channel_objects,
                f,
                indent=4,
                default=lambda o: o.to_dict() if isinstance(o, Serializable) else None,
            )

        with open(modules_file, "w") as f:
            json.dump(
                module_objects,
                f,
                indent=4,
                default=lambda o: o.to_dict() if isinstance(o, Serializable) else None,
            )

    @classmethod
    def from_json(
        cls,
        hardware_file: str = "hardware.json",
        channels_file: str = "channels.json",
        modules_file: str = "modules.json",
    ):
        """
        Restore a HardwareInterface from JSON files.

        :param hardware_file: The filename for the hardware file. Defaults to
            "hardware.json".
        :type hardware_file: str
        :param channels_file: The filename for the channels file. Defaults to
            "channels.json".
        :type channels_file: str
        :param modules_file: The filename for the modules file. Defaults to
            "modules.json".
        :type modules_file: str

        :return: A restored HardwareInterface instance.
        :rtype: HardwareInterface
        """

        with open(hardware_file) as f:
            hardware_data = json.load(f)

        with open(channels_file) as f:
            channel_data = json.load(f)

        with open(modules_file) as f:
            module_data = json.load(f)

        # Create a HardwareInterface instance
        instance = cls(name="RestoredHardwareInterface")

        # Deserialize hardware
        hardware_references = {}
        hardware_objects = [Serializable.from_dict(item, hardware_references) for item in hardware_data]
        hardware_map = {hw_data["id"]: hw for hw_data, hw in zip(hardware_data, hardware_objects)}

        for hw in hardware_objects:
            instance.multi_hardware.add_hardware(hw)

        # Deserialize channels
        for channel_dict in channel_data:
            parent_info = channel_dict.get("parent_hardware")
            if parent_info:
                parent_hw_id = parent_info["id"]
                parent_hw = hardware_map.get(parent_hw_id)
                if parent_hw:
                    handle = parent_hw._handle
                    channel = cls._create_object_with_handle(
                        channel_dict, hardware_references, handle, obj_type="channel"
                    )
                    parent_hw.add_channels(channel)

        # Deserialize modules
        for module_dict in module_data:
            parent_hw_info = module_dict.get("parent_hardware")
            if parent_hw_info:
                parent_hw_id = parent_hw_info["id"]
                parent_hw = hardware_map.get(parent_hw_id)
                if parent_hw:
                    handle = parent_hw._handle
                    module = cls._create_object_with_handle(module_dict, hardware_references, handle, obj_type="module")
                    parent_hw.add_channels(module)

        return instance

    @classmethod
    def _create_object_with_handle(
        cls,
        obj_dict: Dict[str, Any],
        references: Dict[int, Any],
        handle: Any,
        obj_type: str,
    ):
        """
        Helper function to create an instance of a Serializable object with a handle.

        :param obj_dict: The dictionary representation of the object.
        :type obj_dict: Dict[str, Any]
        :param references: A dictionary to store references to created objects.
        :type references: Dict[int, Any]
        :param handle: The handle to the object.
        :type handle: Any
        :param obj_type: The type of the object (either "channel" or "module").
        :type obj_type: str

        :return: Instance of the object.
        :rtype: Any
        """

        module_name = obj_dict["module"]
        class_name = obj_dict["class"]
        module = importlib.import_module(module_name)
        obj_cls = getattr(module, class_name)

        instance = obj_cls.__new__(obj_cls)
        references[obj_dict["id"]] = instance
        attributes = obj_dict.get("attributes", {})
        for key, value in attributes.items():
            if isinstance(value, dict) and "class" in value and "module" in value:
                if obj_type == "module":
                    setattr(instance, key, Serializable.from_dict(value, references))
                else:  # For channels
                    setattr(
                        instance,
                        key,
                        cls._create_object_with_handle(value, references, handle, obj_type),
                    )
                setattr(instance, key, Serializable.from_dict(value, references))
            elif isinstance(value, list):
                setattr(
                    instance,
                    key,
                    [
                        (
                            cls._create_object_with_handle(item, references, handle, obj_type)
                            if isinstance(item, dict)
                            else item
                        )
                        for item in value
                    ],
                )
            else:
                setattr(instance, key, value)

        # Set handle before initializing
        instance._handle = handle
        if hasattr(instance, "initialize"):
            instance.initialize()

        return instance


class MeasurementTask:
    """
    Represents a measurement task that can be executed by the measurement system.

    :param channel: The channel or module to measure.
    :type channel: Union[InputChannel, InputModule]
    :param send_command_callback: A callback function to send commands to the control interface.
    :type send_command_callback: SendCommandCallbackType

    :return: A MeasurementTask instance.
    :rtype: MeasurementTask
    """

    class SendCommandCallbackType_2(Protocol):
        """
        A callback type for sending commands.
        """

        def __call__(self, command: Command, priority: int = 5) -> None: ...

    def __init__(
        self,
        channel: Union[InputChannel, InputModule],
        send_command_callback: SendCommandCallbackType_2,
    ):
        self.channel = channel
        self.send_command_callback = send_command_callback

        self._measurement_thread = None
        self._measurement_thread_stop_event = threading.Event()

        self.time_start = None

        # Determine channels based on Y-axis channel
        if hasattr(channel, "config"):
            if not hasattr(channel.config, "chart_number") or not hasattr(channel.config, "sample_rate"):
                raise ValueError(f"Channel {channel} has no attribute chart_number or sample_rate defined in config.")

        self.chart_y_axis_channel = channel.config.chart_number  # Y-axis               e.g. 705
        self.chart_control_channel = (self.chart_y_axis_channel // 10) * 10  # decade below Y-axis    -> 700
        self.chart_x_axis_channel = (self.chart_y_axis_channel // 10) * 10 + 10  # decade above Y-axis    -> 710

    def start(self) -> None:
        """
        Start the measurement task.

        This method starts a new thread that runs the measurement loop.
        The measurement loop clears the diagram, sets the X-axis and Y-axis limits,
        and then starts the measurement.
        The measurement loop runs indefinitely until the stop method is called.
        """

        self._measurement_thread = threading.Thread(target=self._measurement_loop)
        self._measurement_thread.daemon = True
        self.time_start = time.time_ns()
        self._measurement_thread.start()

    def stop(self) -> None:
        """
        Stop the measurement task.

        This method stops the measurement loop by setting the stop event,
        and then waits for the measurement thread to finish with a timeout
        of 10 seconds or the sample rate of the channel plus one second,
        whichever is smaller.
        """

        if self._measurement_thread is not None:
            self._measurement_thread_stop_event.set()
            timeout = 10
            if hasattr(self.channel, "config"):
                if hasattr(self.channel.config, "sample_rate"):
                    timeout = min(self.channel.config.sample_rate + 1, 10)  # NOTE: ADDED TIMEOUT HERE!!!!
            self._measurement_thread.join(timeout=timeout)
            self._measurement_thread = None
            self._measurement_thread_stop_event.clear()

    def _measurement_loop(self) -> None:
        """
        Measurement loop.

        This method runs indefinitely until the stop method is called.
        The method performs a measurement task and send the result to the server.

        :return: None
        :rtype: None
        """

        # Clear diagram, e.g. 700 Control Channel
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.STRING, "Clear"))

        # # X-Axis
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.FLOAT, 0))
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.STRING, "Xmin"))
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.FLOAT, 11))
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.STRING, "Xmax"))

        # # Y-Axis
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.FLOAT, 0))
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.STRING, "Ymin"))
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.FLOAT, 10))
        self.send_command_callback(Command(self.chart_control_channel, Command.Type.STRING, "Ymax"))

        y_storage = []
        y_min = 0
        y_max = 0

        idx = 0
        while not self._measurement_thread_stop_event.is_set():
            idx += 1

            try:
                data = self.channel.read()
                if data.get_count() > 0:
                    value, t_value = data.get_last()  # TODO: handle list data
                else:
                    print("INFO: 'empty data' should never happen --> to be debugged!")
                    continue

                y_storage.append(value)

                rel_time = (t_value - self.time_start) * 10**-9  # convert to seconds

                self.send_command_callback(Command(self.chart_y_axis_channel, Command.Type.FLOAT, value))
                self.send_command_callback(Command(self.chart_x_axis_channel, Command.Type.FLOAT, rel_time))

                # TODO: dynamic update of X-Axis & Y-Axis limits dependent on values

                # dynamic update of X-Axis
                if idx > 1 and idx % 10 == 0:
                    self.send_command_callback(
                        Command(
                            self.chart_control_channel,
                            Command.Type.FLOAT,
                            rel_time + 10,
                        )
                    )
                    self.send_command_callback(Command(self.chart_control_channel, Command.Type.STRING, "Xmax"))

                # dynamic update of Y-Axis
                if len(y_storage) > 1:
                    y_adder = (max(y_storage) - min(y_storage)) * 0.2  # add 20% to the y-axis range
                    y_min_new = min(y_storage) - y_adder
                    y_max_new = max(y_storage) + y_adder

                    if (
                        y_min_new != y_min or y_max_new != y_max
                    ):  # IMPORTANT TODO: this will overwrite min/max from other channels if same chart is used!!!!
                        y_min = y_min_new
                        y_max = y_max_new

                        self.send_command_callback(Command(self.chart_control_channel, Command.Type.FLOAT, y_min))
                        self.send_command_callback(Command(self.chart_control_channel, Command.Type.STRING, "Ymin"))
                        self.send_command_callback(Command(self.chart_control_channel, Command.Type.FLOAT, y_max))
                        self.send_command_callback(Command(self.chart_control_channel, Command.Type.STRING, "Ymax"))

                # Wait time
                if self.channel.config.sample_rate <= 0:
                    pass  # NOTE: no sleep --> full speed (NOT RECOMMENDED!!!)
                else:
                    time.sleep(1 / self.channel.config.sample_rate)

            except Exception as e:
                # break  # stop measurement loop
                raise Exception(">>> STOPPED MEASUREMENT TASK:", self.channel.name, "Exception:", e)


class MeasurementTaskManager:
    """
    Manages a collection of measurement tasks and provides functionality to start and stop them all.

    :param measurement_system: An instance of MeasurementSystem class.
    :type measurement_system: MeasurementSystem

    :return: MeasurementTaskManager instance
    :rtype: MeasurementTaskManager
    """

    def __init__(self, measurement_system: MeasurementSystem):
        self.measurement_system = measurement_system
        self.send_command_callback = self.measurement_system.add_command_to_send_queue
        self.tasks = []

    def initialize_tasks(self) -> None:
        """
        Initialize all measurement tasks.

        This method iterates over all channels in the hardware interface and
        creates a MeasurementTask instance for each enabled input channel. The
        created tasks are stored in the tasks list.

        :return: None
        :rtype: None
        """

        self.tasks = []
        for channel in self.measurement_system.hardware_interface.multi_hardware.get_channels():
            if isinstance(channel, (InputChannel, InputModule)):
                if hasattr(channel, "config"):
                    if not hasattr(channel.config, "enabled"):
                        raise ValueError(f"Channel {channel} has no attribute 'config.enabled' defined")

                if channel.config.enabled:
                    task = MeasurementTask(channel, self.send_command_callback)
                    self.tasks.append(task)

    def start_tasks(self) -> None:
        """
        Start all measurement tasks.

        This method iterates over all measurement tasks in the tasks list and
        calls their start method.

        :return: None
        :rtype: None
        """

        for task in self.tasks:
            assert isinstance(task, MeasurementTask)
            task.start()

    def stop_tasks(self) -> None:
        """
        Stop all measurement tasks.

        This method iterates over all measurement tasks in the tasks list and
        calls their stop method in parallel using a ThreadPoolExecutor. This
        allows for faster stopping of all measurement tasks.

        :return: None
        :rtype: None
        """

        # Serial execution of task.stop() --> very slow, dependent on channel.config.sample_rate
        # for task in self.tasks:
        #     assert isinstance(task, MeasurementTask)
        #     task.stop()

        # Parllel execution of task.stop()

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(task.stop) for task in self.tasks]
            for future in as_completed(futures):
                try:
                    future.result(timeout=10)
                except Exception as e:
                    print(f">> An error occurred while stopping a task: {e}")


class ControlTask:
    """
    Represents a control task that can be executed by the system to perform a specific control action.

    :param measurement_system: An instance of MeasurementSystem class.
    :type measurement_system: MeasurementSystem
    :param send_command_callback: A callback function that is called when a command is sent to the measurement system.
    :type send_command_callback: SendCommandCallbackType

    :return: ControlTask instance
    :rtype: ControlTask
    """

    class SendCommandCallbackType(Protocol):
        """
        A callback type for sending commands.
        """

        def __call__(self, command: Command, priority: int = 5) -> None: ...

    def __init__(
        self,
        measurement_system: MeasurementSystem,
        send_command_callback: SendCommandCallbackType,
    ):
        self.measurement_system = measurement_system
        self.send_command_callback = send_command_callback

        self._control_thread = None
        self._control_thread_stop_event = threading.Event()
        self._lock = threading.Lock()

        self._command_queue = OrderedPriorityQueue(name="CommandQueue")

        self._command_storage = None

    def start(self) -> None:
        """
        Starts the control loop.

        This method starts the control loop in a separate thread. The thread
        will continue to run until the stop method is called.

        :return: None
        :rtype: None
        """

        self._control_thread = threading.Thread(target=self._control_loop)
        self._control_thread.daemon = True
        self._control_thread.start()

    def stop(self) -> None:
        """
        Stops the control loop.

        This method stops the control loop thread and waits for the thread to finish.
        If the control loop is not running, this method does nothing.

        :return: None
        :rtype: None
        """

        if self._control_thread is not None:
            self._control_thread_stop_event.set()
            self._control_thread.join()
            self._control_thread = None
            self._control_thread_stop_event.clear()

    def add_command(self, command: Command, priority: int = 5) -> None:
        """
        Adds a command to the control loop queue.

        This method adds a command to the control loop queue with a given priority.
        The control loop will execute the command in the order of priority.

        :param command: The command to add to the queue.
        :type command: Command
        :param priority: The priority of the command. Higher priority commands are executed first.
        :type priority: int
        :return: None
        :rtype: None
        """

        self._command_queue.put(command, priority)

    def _control_loop(self) -> None:
        """
        Control loop thread.

        This method runs in a separate thread and executes the commands in the command queue.
        The commands are executed in the order of priority. If the command queue is empty, the
        thread waits for a command to be added to the queue.

        :return: None
        :rtype: None
        """

        while not self._control_thread_stop_event.is_set():
            try:
                command, priority = self._command_queue.get(timeout=1)  # Wait for a command
                self.send_command_callback(command, priority)
                self._execute_command(command)

            except queue.Empty:
                continue

    def _execute_command(self, command: Command) -> None:
        """
        Executes a control command.

        This method executes a control command. The command is executed immediately.

        :param command: The command to execute.
        :type command: Command
        """

        # Helper functions
        def _calculate_name(diagram_channel, selected_index) -> str:
            """
            Helper function to calculate the name of a chart control channel based on the selected diagram channel and index.

            The channel number of the chart control channel is calculated as follows:
            base_name_number + (diagram_index * names_per_diagram) + (selected_index - 1)
            where:
            - base_name_number is 701
            - diagram_index is the index of the selected diagram (0-4)
            - names_per_diagram is 20
            - selected_index is the index of the selected channel in the diagram (1-20)

            :param diagram_channel: The channel number of the selected diagram (801-805).
            :type diagram_channel: int
            :param selected_index: The index of the selected channel in the diagram (1-20).
            :type selected_index: int

            :return: The name of the chart control channel.
            :rtype: str
            """

            diagram_channel = int(diagram_channel)
            selected_index = int(selected_index)
            # TODO: error handling
            #   - selected_index > 0 --> error
            #   - diagram_channel != 801-805 --> error

            base_name_number = 701
            names_per_diagram = 20

            diagram_index = diagram_channel - 801
            base_for_diagram = base_name_number + (diagram_index * names_per_diagram)  # 701-719, 720-739, ...
            return int(base_for_diagram + (selected_index - 1))

        def _reset_channel_selection(self: ControlTask) -> None:
            """
            Helper function to reset the channel selection in the control interface.

            This method resets the channel selection in the control interface by sending commands to the server.
            The commands are sent with priority 0.

            :param self: The instance of the control task.
            :type self: ControlTask

            :return: None
            :rtype: None
            """

            for channel in range(801, 805 + 1):
                channel = channel + 10  # according contol channel (811 - 815)
                self.send_command_callback(Command(channel, Command.Type.F, 0))
            self.send_command_callback(Command(820, Command.Type.S, "Kein Kanal ausgewählt!"))

        # Control Commands Execution
        try:
            # Channel selection for chart control
            if 801 <= command.channel <= 805:
                self._command_storage = command
                msg = f"Received control command with channel number = {command.value}, waiting for next control command + value"
                self.measurement_system.printConsole(msg)
                print(">>", msg)

                # Return: send all other channels for chart control to 0
                for channel in range(801, 805 + 1):
                    if channel != command.channel:
                        channel = channel + 10  # according contol channel (811 - 815)
                        self.send_command_callback(Command(channel, Command.Type.F, "0"))

                # Kanal Anzeige
                if command.value != 0:
                    channel_name = _calculate_name(command.channel, command.value)
                    cmd = Command(820, Command.Type.S, f"Kanal {channel_name} ausgewählt!")
                else:
                    cmd = Command(820, Command.Type.S, "Kein Kanal ausgewählt!")
                self.send_command_callback(cmd)

                # Find channel
                channels = []
                for channel in self.measurement_system.hardware_interface.multi_hardware.get_channels():
                    # check if channel has config attribute
                    if hasattr(channel, "config"):
                        if hasattr(channel.config, "chart_number"):
                            if channel.config.chart_number == channel_name:
                                channels.append(channel)
                # channels = [ch for ch in self.measurement_system.hardware_interface.multi_hardware.get_channels() if ch.config.chart_number == channel_name]

                if len(channels) == 0:
                    cmd = Command(829, Command.Type.F, 0)
                    self.send_command_callback(cmd)

                    # cmd = Command(821, Command.Type.S, f"Offset: not found!")
                    # self.send_command_callback(cmd)

                    # cmd = Command(822, Command.Type.S, f"Gain: not found!")
                    # self.send_command_callback(cmd)

                    cmd = Command(823, Command.Type.S, "SR: not found!")
                    self.send_command_callback(cmd)

                elif len(channels) == 1:
                    channel = channels[0]

                    # Enable Anzeige
                    enable = int(channel.config.enabled) + 1
                    cmd = Command(829, Command.Type.F, enable)
                    self.send_command_callback(cmd)

                    # Model Anzeige
                    cmd = Command(821, Command.Type.S, channel.model.to_string())
                    self.send_command_callback(cmd)

                    # # Offset Anzeige
                    # cmd = Command(821, Command.Type.S, f"Offset: {channel.offset}")
                    # self.send_command_callback(cmd)

                    # # Gain Anzeige
                    # cmd = Command(822, Command.Type.S, f"Gain: {channel.gain}")
                    # self.send_command_callback(cmd)

                    # Sample Rate Anzeige
                    cmd = Command(823, Command.Type.S, f"SR: {channel.config.sample_rate}")
                    self.send_command_callback(cmd)

                else:
                    raise Exception("Multiple channels with same chart number found!!!")  # TODO: error handling

            # Channel Enable
            elif command.channel == 830:
                if self._command_storage is not None:
                    msg = f"Received control command for channel enable: value = {command.value}"
                    self.measurement_system.printConsole(msg)
                    print(">>", msg)

                    # Find channel with chart_name
                    channel_name = _calculate_name(self._command_storage.channel, self._command_storage.value)

                    channels = []
                    for channel in self.measurement_system.hardware_interface.multi_hardware.get_channels():
                        # check if channel has config attribute
                        if hasattr(channel, "config"):
                            if hasattr(channel.config, "chart_number"):
                                if channel.config.chart_number == channel_name:
                                    channels.append(channel)
                    # channels = [ch for ch in self.measurement_system.hardware_interface.multi_hardware.get_channels() if ch.config.chart_number == channel_name]

                    if len(channels) == 0:
                        raise Exception(
                            f"No channels with chart number '{channel_name}' found!!!"
                        )  # TODO: error handling

                    if len(channels) == 1:
                        channel = channels[0]

                        self.measurement_system.printConsole(
                            f"CH {channel_name} enable update: replacing {channel.config.enabled} with {command.value}"
                        )
                        with self._lock:
                            channel.config.enabled = float(command.value) == 2

                        # Update Enable Anzeige
                        self.send_command_callback(Command(829, Command.Type.F, int(channel.config.enabled) + 1))

                    else:
                        raise Exception(
                            f"Multiple ({len(channels)}) channels with same chart number '{channel_name}' found!!!"
                        )  # TODO: error handling

                    # Reset channel selection
                    _reset_channel_selection(self)
                    self._command_storage.value = None

                else:
                    msg = "Channel enable command received without setting chart channel first"
                    self.measurement_system.printConsole(msg)
                    print(">>", msg)

            # Model Selection
            elif command.channel == 831:
                control_command = "'model selction'"

                if self._command_storage is not None:
                    msg = f"Received control command for {control_command}: value = {command.value}"
                    self.measurement_system.printConsole(msg)
                    print(">>", msg)

                    # Find channel with chart_name
                    channel_name = _calculate_name(self._command_storage.channel, self._command_storage.value)

                    channels = []
                    for channel in self.measurement_system.hardware_interface.multi_hardware.get_channels():
                        # check if channel has config attribute
                        if hasattr(channel, "config"):
                            if hasattr(channel.config, "chart_number"):
                                if channel.config.chart_number == channel_name:
                                    channels.append(channel)
                    # channels = [ch for ch in self.measurement_system.hardware_interface.multi_hardware.get_channels() if ch.config.chart_number == channel_name]

                    if len(channels) == 0:
                        raise Exception(
                            f"No channels with chart number '{channel_name}' found!!!"
                        )  # TODO: error handling

                    if len(channels) == 1:
                        channel = channels[0]

                        self.measurement_system.printConsole(
                            f"CH {channel_name} {control_command} update: replacing {channel.model.to_string()} with {command.value}"
                        )

                        with self._lock:
                            channel.set_model_from_str(command.value)

                        # Update Offset Anzeige
                        self.send_command_callback(
                            Command(
                                command.channel - 10,
                                Command.Type.S,
                                f"Model: {channel.model.to_string()}",
                            )
                        )

                    else:
                        raise Exception(
                            f"Multiple ({len(channels)}) channels with same chart number '{channel_name}' found!!!"
                        )  # TODO: error handling

                    # Reset channel selection
                    _reset_channel_selection(self)
                    self._command_storage.value = None

                else:
                    msg = f"{control_command} command received without setting chart channel first"
                    self.measurement_system.printConsole(msg)
                    print(">>", msg)

            # SampleRate Selection
            elif command.channel == 833:
                control_command = "'sample rate selection'"

                if self._command_storage is not None:
                    msg = f"Received control command for {control_command}: value = {command.value}"
                    self.measurement_system.printConsole(msg)
                    print(">>", msg)

                    # Find channel with chart_name
                    channel_name = _calculate_name(self._command_storage.channel, self._command_storage.value)

                    channels = []
                    for channel in self.measurement_system.hardware_interface.multi_hardware.get_channels():
                        # check if channel has config attribute
                        if hasattr(channel, "config"):
                            if hasattr(channel.config, "chart_number"):
                                if channel.config.chart_number == channel_name:
                                    channels.append(channel)

                    if len(channels) == 0:
                        raise Exception(
                            f"No channels with chart number '{channel_name}' found!!!"
                        )  # TODO: error handling

                    if len(channels) == 1:
                        channel = channels[0]

                        self.measurement_system.printConsole(
                            f"CH {channel_name} {control_command} update: replacing {channel.config.sample_rate} with {command.value}"
                        )
                        with self._lock:
                            channel.config.sample_rate = float(command.value)

                        # Update SampleRate Anzeige
                        self.send_command_callback(
                            Command(
                                command.channel - 10,
                                Command.Type.S,
                                f"SR: {channel.config.sample_rate}",
                            )
                        )

                    else:
                        raise Exception(
                            f"Multiple ({len(channels)}) channels with same chart number '{channel_name}' found!!!"
                        )  # TODO: error handling

                    # Reset channel selection
                    _reset_channel_selection(self)
                    self._command_storage.value = None
                else:
                    msg = f"{control_command} command received without setting chart channel first"
                    self.measurement_system.printConsole(msg)
                    print(">>", msg)

            # SAVE CONFIG
            elif command.channel == 890:
                hardware_file = os.path.join(current_dir, "config", "hardware_user.json")
                channels_file = os.path.join(current_dir, "config", "channels_user.json")
                modules_file = os.path.join(current_dir, "config", "modules_user.json")

                self.measurement_system.hardware_interface.to_json(
                    hardware_file=hardware_file,
                    channels_file=channels_file,
                    modules_file=modules_file,
                )

                msg = f"Saving config to '{hardware_file}', '{channels_file}' and '{modules_file}'"
                self.measurement_system.printConsole(msg)
                print(">>", msg)

            # LOAD CONFIG
            elif 891 <= command.channel <= 892:
                if command.channel == 892:  # default config
                    name_postfix = "_default"
                else:
                    name_postfix = "_user"  # user defined
                hardware_file = os.path.join(current_dir, "config", f"hardware{name_postfix}.json")
                channels_file = os.path.join(current_dir, "config", f"channels{name_postfix}.json")
                modules_file = os.path.join(current_dir, "config", f"modules{name_postfix}.json")

                msg = f"Loading config from '{hardware_file}', '{channels_file}' and '{modules_file}'"
                self.measurement_system.printConsole(msg)
                print(">>", msg)

                # Stop measurement tasks and close hardware interface
                self.measurement_system.measurement_task_manager.stop_tasks()  # stop measurement tasks
                self.measurement_system.hardware_interface.close()  # close hardware interface
                self.measurement_system.init_comvisu()  # init comvisu

                # Load config and initialize new hardware interface
                self.measurement_system.hardware_interface = self.measurement_system.hardware_interface.from_json(
                    hardware_file=hardware_file,
                    channels_file=channels_file,
                    modules_file=modules_file,
                )

                # Recreate measurement tasks
                self.measurement_system.measurement_task_manager.initialize_tasks()

            ##################################
            # IMPLEMENT MORE CONTROL COMMANDS HERE
            # elif command.channel == ...:

            else:
                msg = f"Unknown control command: {command.to_string()}"
                self.measurement_system.printConsole(msg)
                print(">>", msg)

        except Exception as e:
            print(f"Error executing command: {command.to_string()}, error: {e}")


class ControlTaskManager:
    """
    Manages a collection of control tasks and provides functionality to start and stop them all.

    :param measurement_system: An instance of MeasurementSystem class.
    :type measurement_system: MeasurementSystem

    :return: ControlTaskManager instance
    :rtype: ControlTaskManager
    """

    def __init__(self, measurement_system: MeasurementSystem):
        self.measurement_system = measurement_system
        self.send_command_callback = self.measurement_system.add_command_to_send_queue
        self.tasks = []

    def initialize_tasks(self) -> None:
        """
        Initialize the control tasks.

        :return: None
        :rtype: None
        """

        task = ControlTask(self.measurement_system, self.send_command_callback)
        self.tasks.append(task)

    def start_tasks(self) -> None:
        """
        Start all control tasks.

        This method iterates over all control tasks in the tasks list and calls
        their start method.

        :return: None
        :rtype: None
        """

        for task in self.tasks:
            assert isinstance(task, ControlTask)
            task.start()

    def stop_tasks(self) -> None:
        """
        Stop all control tasks.

        This method iterates over all control tasks in the tasks list and calls
        their stop method.

        :return: None
        :rtype: None
        """

        for task in self.tasks:
            assert isinstance(task, ControlTask)
            task.stop()

    def add_command_to_task(self, command: Command, priority: int = 5) -> None:
        """
        Add a command to the control task.

        This method adds a command to the control task with a given priority.
        The control task will execute the command in the order of priority.

        :param command: The command to add to the control task.
        :type command: Command
        :param priority: The priority of the command. Higher priority commands are executed first.
        :type priority: int
        :return: None
        :rtype: None
        """

        for task in self.tasks:
            assert isinstance(task, ControlTask)
            task.add_command(command)


class MeasurementSystem:
    """
    Represents a measurement system that collects and processes data from various measurement sources.

    The MeasurementSystem class provides a framework for managing measurement data, including data acquisition,
    processing, and storage. It can be used to integrate data from multiple measurement sources, such as sensors,
    instruments, or other data acquisition systems.
    """

    def __init__(self, server_address):
        # Server Connection
        """
        Initialize a MeasurementSystem object.

        This method initializes a MeasurementSystem object with a given server
        address. It creates a ServerConnection object, a DataQueue object, a
        DataQueueThread object and a HardwareInterface object. It also
        initializes a MeasurementTaskManager and a ControlTaskManager object.

        :param server_address: The address of the server to connect to.
        :type server_address: str
        :return: None
        :rtype: None
        """

        self.server_connection = ServerConnection("ComVisu", server_address)
        self.server_connection.connect()

        # Data Queue
        self.data_queue = OrderedPriorityQueue(name="DataQueue")

        # Send Thread
        self.data_queue_processor = DataQueueThread(self.data_queue, self.server_connection.send)
        self.data_queue_processor.start()

        # Hardware Interface
        self.hardware_interface = HardwareInterface(name="MeasurementSystemInterface")
        self.hardware_interface.initialize()  # TODO: to be replaced by reading a json file (default.json if no correct config file is provided)

        # Measurement Task Manager
        self.measurement_task_manager = MeasurementTaskManager(self)
        # NOTE: tasks are initialized at measurement start

        # Control Task
        self.control_task_manager = ControlTaskManager(self)
        self.control_task_manager.initialize_tasks()
        self.control_task_manager.start_tasks()

        # Initialize ComVisu
        self.init_comvisu()

    def close(self) -> None:
        """
        Close the MeasurementSystem object.

        This method stops all measurement tasks and control tasks,
        closes the hardware interface, stops the data queue processor and
        disconnects from the server.

        :return: None
        :rtype: None
        """

        self.measurement_task_manager.stop_tasks()  # stop measurement tasks
        self.control_task_manager.stop_tasks()  # stop control tasks
        self.hardware_interface.close()  # close measurement
        self.data_queue_processor.stop()  # stop data queue processor
        self.server_connection.disconnect()  # close server connection

    def printConsole(self, *args, sep=" ", end="") -> None:
        """
        Prints a message to the ComVisu console #999 with a timestamp and replaces any semicolons or hashes in the message with underscores.

        :param args: The arguments to be joined into a message string.
        :type args: Any
        :param sep: The separator to join the arguments with. Default is a space.
        :type sep: str
        :param end: The string to append to the end of the message. Default is an empty string.
        :type end: str
        :return: None
        :rtype: None
        """

        message = sep.join(map(str, args)) + end

        # replace not allowed characters
        message = message.replace(";", "_")
        message = message.replace("#", "_")

        timestamp = datetime.now().strftime("%Y-%m-%d, %H:%M:%S.%f")
        message = f"{timestamp}: {message}"

        cmd = Command(999, Command.Type.STRING, message)
        self.add_command_to_send_queue(cmd, priority=0)

    def add_command_to_send_queue(self, command: Command, priority=5) -> None:
        """
        Sends a command to the server with a given priority.

        :param command: The command to send to the server.
        :type command: Command
        :param priority: The priority of the command. Higher priority commands are executed first.
        :type priority: int
        :return: None
        :rtype: None
        """
        self.data_queue.put(command, priority)

    def init_comvisu(self):
        """
        Initialize the ComVisu server.

        This method sends commands to the server to initialize the ComVisu interface.
        The commands are sent with priority 0.

        The following commands are sent:
            - Set "Mess-System" to "STOP".
            - Set "Diagramm X - Kanal auswahl" to "-" for all diagrams.
            - Set "Kanal X: Enable" to "-".
            - Clear all diagrams.

        :return: None
        :rtype: None
        """

        self.add_command_to_send_queue(Command(901, Command.Type.FLOAT, 1), priority=0)  # set "Mess-System" to "STOP"

        for ch in range(811, 816):
            self.add_command_to_send_queue(
                Command(ch, Command.Type.FLOAT, 0), priority=0
            )  # set "Diagramm X - Kanal auswahl" to "-"

        self.add_command_to_send_queue(Command(829, Command.Type.FLOAT, 0), priority=0)  # set "Kanal X: Enable" to "-"

        for ch in [700, 720, 740, 760, 780]:
            self.add_command_to_send_queue(Command(ch, Command.Type.STRING, "Clear"), priority=0)  # clear all diagrams

        ##################################
        # IMPLEMENT MORE COMMANDS HERE

    def process_commands(self, commands: List[Command]) -> None:
        """
        Process commands received from the ComVisu server.

        This method processes commands received from the ComVisu server.
        The commands are processed according to the channel number and type.

        The following commands are processed:
            - Start/Stop Measurement System
            - Slider Test
            - Control Commands - Calibration
            - Keep Alive Signal

        Other commands are logged as "Unknown command".

        :param commands: The commands to process.
        :type commands: List[Command]
        :return: None
        :rtype: None
        """

        for command in commands:
            ##################################
            # Start/Stop Measurement System
            if command.channel == 900:  # Start Measurement System
                if command.value == 2:
                    self.measurement_task_manager.initialize_tasks()  # NOTE: in case of anything has changes in the meanwhile
                    self.measurement_task_manager.start_tasks()
                    self.printConsole("Measurement system started")
                else:
                    self.measurement_task_manager.stop_tasks()
                    self.printConsole("Measurement system stopped")
                    self.add_command_to_send_queue(Command(901, Command.Type.F, "0"), priority=0)

            ##################################
            # Slider Test
            elif command.channel == 510:  # == "#510F12;"
                self.printConsole(
                    "Channel: ",
                    command.channel,
                    ", type: ",
                    command.type,
                    ", value:",
                    command.value,
                )

                # # TEST: overwrite gain value of InternalTemperatureChannel
                # channel = self.hardware_interface._rpi_hardware.channels[1]
                # channel.gain = command.value

            ##################################
            # Control Commands - Calibration
            elif command.channel >= 800 and command.channel <= 899:
                self.printConsole(
                    "Channel: ",
                    command.channel,
                    ", type: ",
                    command.type,
                    ", value:",
                    command.value,
                )
                self.control_task_manager.add_command_to_task(command)

            ##################################
            # Keep Alive Signal
            elif command.channel == 980:  # Keep alive signal received
                self.add_command_to_send_queue(
                    Command(981, Command.Type.FLOAT, "1"), priority=0
                )  # send Mess-Sytem-KeepAlive Signal

                # Blink LED
                channel = self.hardware_interface.multi_hardware.get_channels_by_name("KeepAliveLED")
                try:
                    channel = next(channel)  # Generator to item
                    assert isinstance(channel, Channel_RPI_DigitalOutput)
                    if channel.level == 0:
                        channel.write(1)
                    else:
                        channel.write(0)
                except:
                    pass

            ##################################
            # IMPLEMENT MORE COMMANDS HERE
            # elif command.channel == ...:

            ##################################
            # Unknown Command
            else:
                self.printConsole("Unknown command:", command)
                print("Unknown command:", command.to_string())


##############################
# MAIN
def main():
    """
    Main loop of the measurement system.

    The main loop receives commands from the server and executes them. The loop
    is executed until the program is interrupted by a keyboard interrupt (Ctrl+C).

    The main loop consists of two parts: the receive loop and the overall loop.

    The receive loop receives commands from the server and executes them. The
    receive loop is executed until an error occurs or the program is interrupted
    by a keyboard interrupt.

    The overall loop is executed until the program is interrupted by a keyboard
    interrupt. The overall loop timer is set to 0.5 seconds.

    If an error occurs, the program will print the error message and the
    traceback, and then exit with an error code.

    If the program is interrupted by a keyboard interrupt, the program will print
    a message and exit with an error code.

    :return: None
    :rtype: None
    """

    # Get server address from arguments, otherwise use default
    if len(sys.argv) == 2:
        address_str = sys.argv[1]

        try:
            ip_address, port_str = address_str.split(":")
            port = int(port_str)  # Convert port to an integer
        except ValueError:
            print("Invalid format. Expected format is IP_ADDRESS:PORT")
            sys.exit(1)

        server_address = (ip_address, port)
    else:
        server_address = default_server_address

    # Only one instance of the measurement system is allowed
    if os.path.exists(LOCKFILE):
        print(
            "Another instance of the measurement system is already running.",
            file=sys.stderr,
        )
        print(
            "The instance will be killed and lock released. Please try again.",
            file=sys.stderr,
        )

        # remove lockfile and kill itself
        os.remove(LOCKFILE)
        os.system("pkill -f measurement_server.py")
        sys.exit(1)  # never reached since pkill kills the process

    # Create lockfile
    with open(LOCKFILE, "w") as f:
        f.write(str(datetime.now()))
        print("Lockfile created:", LOCKFILE)

    # Main loop
    i_trials = 0
    while True:
        i_trials += 1
        print("Trial: ", i_trials)

        try:
            # server_address = ('192.168.1.31', 8008)
            measurementSystem = None
            measurementSystem = MeasurementSystem(server_address)
            measurementSystem.printConsole("Measurement system connected!")

            # Receive loop
            while True:
                commands = measurementSystem.server_connection.receive()  # blocking
                measurementSystem.process_commands(commands)
                time.sleep(0.5)  # Receive loop timer

        except KeyboardInterrupt:
            print("\n>> Exiting...")
            break

        except Exception as e:
            print(f">>> {type(e).__name__}:", e)
            traceback.print_exception(type(e), e, e.__traceback__)  # for debugging purpose only

        finally:
            try:
                if measurementSystem is not None:
                    measurementSystem.close()
                    measurementSystem = None
            except Exception as e:
                raise e

        # Overall loop timer
        time.sleep(0.5)
        print("\n----------------------------------------\n")

    # remove lockfile
    if os.path.exists(LOCKFILE):
        os.remove(LOCKFILE)
        print("Lockfile removed.")

    print("Application closed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
