from __future__ import annotations

import os
import sys
from typing import Generator, List, Union

from MeasurementSystem.core.common.Data import Data
from MeasurementSystem.core.common.Models import Model, ModelMeta, StackedModel
from MeasurementSystem.core.common.Utils import Serializable


class ChannelProperties:
    """
    A class representing the properties of a channel.
    """

    class Type:
        """
        :class:`Type` provides valid data types for ChannelProperties.Type
        """

        DIGITAL_IN = "digital_input"
        DIGITAL_OUT = "digital_output"
        FREQUENCY = "frequency"
        TEMPERATURE = "temperature"
        VOLTAGE = "voltage"
        CURRENT = "current"
        WEIGHT = "weight"
        PRESSURE = "pressure"
        FORCE = "force"
        TORQUE = "torque"
        ANGLE = "angle"
        VELOCITY = "velocity"
        OTHER = "other"

        @classmethod
        def valid_types(cls):
            return set(vars(cls).values())

        @classmethod
        def is_valid(cls, type: str) -> bool:
            return type in cls.valid_types()


class Channel(Serializable):
    """
    A class representing a single channel, encapsulating its properties and behavior.

    :param name: The name of the channel.
    :type name: str
    :param type: The type of the channel.
    :type type: ChannelProperties.Type
    :param unit: The unit of measurement of the channel.
    :type unit: str
    :param model: The model of the channel.
    :type model: Model

    :return: Channel instance
    :rtype: Channel
    """

    def __init__(self, name: str, type: ChannelProperties, unit: str, model: Model):
        if not ChannelProperties.Type.is_valid(type):
            raise ValueError(f"Invalid channel type: {type}")

        self.name = name
        self.type = type
        self.unit = unit
        self.model = model

    def initialize(self) -> None:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")

    def close(self) -> None:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")

    def set_model_from_str(self, model_str: str) -> None:
        """
        Set the model of the channel from a string representation using the model registry.

        :param model_str: The string representation of the model.
        :type model_str: str

        :return: None
        :rtype: None

        :raise: ValueError
        """

        try:
            # Prepare the execution environment with available classes
            model_registry = ModelMeta.model_registry
            env = {
                "ModelMeta": ModelMeta,
                "StackedModel": StackedModel,
                **model_registry,
            }

            # Extract the model class name and arguments
            class_name = model_str.split("(")[0]
            args_str = model_str.split("(", 1)[1].rstrip(")")

            if class_name == "StackedModel":
                # Handle StackedModel by parsing the list of models
                model_list = Model.parse_model_list(args_str, model_registry)
                self.model = StackedModel(model_list)
            else:
                # Handle other models
                exec_code = f"model = ModelMeta.model_registry.get('{class_name}')({args_str})"
                exec(exec_code, {}, env)
                self.model = env["model"]

            if self.model is None:
                raise ValueError("Model instantiation failed.")

        except Exception as e:
            print(f"Error setting model from string: {e}")
            raise e


class InputChannel(Channel):
    """
    A class representing an input channel.

    :param name: The name of the channel.
    :type name: str
    :param type: The type of the channel.
    :type type: ChannelProperties.Type
    :param unit: The unit of measurement of the channel.
    :type unit: str
    :param model: The model of the channel.
    :type model: Model

    :return: InputChannel instance
    :rtype: InputChannel
    """

    def __init__(self, name: str, type: str, unit: str, model: Model):
        super().__init__(name=name, type=type, unit=unit, model=model)

    def read(self) -> Data:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")


class OutputChannel(Channel):
    """
    A class representing an output channel.

    :param name: The name of the channel.
    :type name: str
    :param type: The type of the channel.
    :type type: ChannelProperties.Type
    :param unit: The unit of measurement of the channel.
    :type unit: str
    :param model: The model of the channel.
    :type model: Model

    :return: OutputChannel instance
    :rtype: OutputChannel
    """

    def __init__(self, name: str, type: str, unit: str, model: Model):
        super().__init__(name=name, type=type, unit=unit, model=model)

    def write(self) -> None:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")


class ChannelManager(Serializable):
    """
    A class responsible for managing channels.
    The ChannelManager class provides a centralized interface for creating, configuring, and managing multiple channels such input and output or multi (mixed) channels.

    :param input_channels: A list of input channels. Defaults to an empty list.
    :type input_channels: List[InputChannel]
    :param output_channels: A list of output channels. Defaults to an empty list.
    :type output_channels: List[OutputChannel]
    :param multi_channels: A list of multi channels. Defaults to an empty list.
    :type multi_channels: List[MultiChannel]

    :return: ChannelManager instance
    :rtype: ChannelManager

    """

    def __init__(self):
        self.input_channels = []  # TODO: IMPROVEMENT: combine to single generic list and make differentiation in functions later
        self.output_channels = []
        self.multi_channels = []

        self._existing_channel_names = set()  # Used to check for duplicate channel names

    def add_channels(
        self,
        channels: Union[
            InputChannel,
            List[InputChannel],
            OutputChannel,
            List[OutputChannel],
            MultiChannel,
            List[MultiChannel],
        ] = None,
    ) -> None:
        """
        Add channels to the ChannelManager instance.

        :param channels: The channels to add to the ChannelManager instance. Defaults to an empty list.
        :type channels: Union[InputChannel, List[InputChannel], OutputChannel, List[OutputChannel], MultiChannel, List[MultiChannel]]

        :return: None
        :rtype: None

        :raise: ValueError
            If a channel with a duplicate name is added.
        :raise: TypeError
            If the channel is not an instance of InputChannel, OutputChannel, or MultiChannel.
        """

        if not isinstance(channels, list):
            channels = [channels]
            assert isinstance(channels, list)

        for channel in channels:
            if channel.name in self._existing_channel_names:
                raise ValueError(f"Duplicate channel name: {channel.name}")

            if isinstance(channel, InputChannel):
                self.input_channels.append(channel)
            elif isinstance(channel, OutputChannel):
                self.output_channels.append(channel)
            elif isinstance(channel, MultiChannel):
                self.multi_channels.append(channel)
            else:
                raise TypeError("Channel must be an instance of InputChannel, OutputChannel, or MultiChannel")

            self._existing_channel_names.add(channel.name)

    def get_channels(self) -> Generator[Channel, None, None]:
        """
        Returns a generator of all channels in the ChannelManager instance.

        This method returns a generator of all channels in the ChannelManager
        instance. The generator yields each channel in the order they were
        added to the ChannelManager instance.

        :return: A generator of all channels in the ChannelManager instance.
        :rtype: Generator[Channel, None, None]
        """
        for channel in (
            self.input_channels + self.output_channels + self.multi_channels
        ):  # TODO: check if self.multi_channels should be excluded!!
            yield channel

    def get_channels_by_name(self, name: str) -> Generator[Channel, None, None]:
        """
        Returns a generator of channels in the ChannelManager instance with the given name.

        :param name: The name of the channel to search for.
        :type name: str

        :return: A generator of channels in the ChannelManager instance with the given name.
        :rtype: Generator[Channel, None, None]

        :raise: ValueError
            If no channel with the given name is found in the ChannelManager instance.
        """
        for channel in self.get_channels():
            if channel.name == name:
                yield channel
        raise ValueError(f"Channel not found: {name}")

    def get_channels_by_type(self, type: str) -> Generator[Channel, None, None]:
        """
        Returns a generator of channels in the ChannelManager instance with the given type.

        :param type: The type of the channel to search for.
        :type type: str

        :return: A generator of channels in the ChannelManager instance with the given type.
        :rtype: Generator[Channel, None, None]
        """
        for channel in self.get_channels():
            if ChannelProperties.Type == type:
                yield channel
        # raise ValueError(f"Type not found: {type}")  # TODO: check if needed

    def get_modules(self) -> Generator[Module, None, None]:
        """
        Returns a generator of modules in the ChannelManager instance.

        :return: A generator of modules in the ChannelManager instance.
        :rtype: Generator[Module, None, None]
        """
        for module in self.multi_channels:
            yield module

    def close(self) -> None:
        """
        Close all channels in the ChannelManager instance.

        This method closes all channels in the ChannelManager instance by calling
        the close method on each channel. The close method is called only once
        for each channel, even if the channel is part of multiple lists (e.g.
        input_channels and output_channels).

        :return: None
        :rtype: None
        """
        closed_channels = set()
        for channel in self.get_channels():
            if channel not in closed_channels:
                channel.close()
                closed_channels.add(channel)


class MultiChannel(ChannelManager):
    """
    A class that extends ChannelManager to support multiple channels.

    The MultiChannel class builds upon the ChannelManager's functionality by providing features for managing multiple channels simultaneously.

    :param name: The name of the MultiChannel instance.
    :type name: str
    :param input_channels: A list of input channels to add to the MultiChannel instance. Defaults to an empty list.
    :type input_channels: List[InputChannel]
    :param output_channels: A list of output channels to add to the MultiChannel instance. Defaults to an empty list.
    :type output_channels: List[OutputChannel]

    :return: MultiChannel instance
    :rtype: MultiChannel
    """

    def __init__(
        self,
        name: str,
        input_channels: List[InputChannel] = [],
        output_channels: List[OutputChannel] = [],
    ):
        super().__init__()
        self.name = name

        self.add_channels(input_channels)
        self.add_channels(output_channels)

    def close(self) -> None:
        """
        Close all channels in the MultiChannel instance.

        :return: None
        :rtype: None
        """
        super().close()


class Hardware(ChannelManager):
    """
    A class that extends ChannelManager to provide an interface for interacting with hardware components.

    :param name: The name of the hardware instance.
    :type name: str
    :param input_channels: A list of input channels to add to the hardware instance. Defaults to an empty list.
    :type input_channels: List[InputChannel]
    :param output_channels: A list of output channels to add to the hardware instance. Defaults to an empty list.
    :type output_channels: List[OutputChannel]
    :param multi_channels: A list of multi channels to add to the hardware instance. Defaults to an empty list.
    :type multi_channels: List[MultiChannel]

    :return: Hardware instance
    :rtype: Hardware
    """

    def __init__(
        self,
        name,
        input_channels: List[InputChannel] = None,
        output_channels: List[OutputChannel] = None,
        multi_channels: List[MultiChannel] = None,
    ):
        super().__init__()
        self.name = name

        if input_channels:
            self.add_channels(input_channels)

        if output_channels:
            self.add_channels(output_channels)

        if multi_channels:
            self.add_channels(multi_channels)

    def initialize(self) -> None:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")


class MultiHardware(Serializable):
    """
    A class representing a collection of hardware devices.

    :param name: The name of the multi-hardware instance.
    :type name: str
    :param hardware_list: A list of hardware instances to be included in the multi-hardware instance. Defaults to an empty list.
    :type hardware_list: List[Hardware]

    :return: A MultiHardware instance.
    :rtype: MultiHardware
    """

    def __init__(self, name, hardware_list: List[Hardware] = []):
        self.name = name
        self.hardware_list = hardware_list

    def add_hardware(self, hardware_instance) -> None:
        """
        Add a hardware instance to the collection.

        :param hardware_instance: The hardware instance to be added to the collection.
        :type hardware_instance: Hardware

        :return: None
        :rtype: None
        """
        if isinstance(hardware_instance, Hardware):
            self.hardware_list.append(hardware_instance)
        else:
            raise TypeError("hardware_instance must be an instance of Hardware")

    def close(self) -> None:
        """
        Close the MultiHardware instance.

        This method calls the close method of all hardware instances in the collection.

        :return: None
        :rtype: None
        """
        for hardware in self.hardware_list:
            hardware.close()

    def get_channels(self) -> Generator[Channel, None, None]:
        """
        :return: A generator of all channels in the multi-hardware instance.
        :rtype: Generator[Channel, None, None]
        """

        for hardware in self.hardware_list:
            for channel in hardware.get_channels():
                yield channel

    def get_channels_by_name(self, name: str) -> Generator[Channel, None, None]:
        """
        :param name: The name of the channel to search for.
        :type name: str

        :return: A generator of channels in the multi-hardware instance with the given name.
        :rtype: Generator[Channel, None, None]
        """
        for hardware in self.hardware_list:
            for channel in hardware.get_channels_by_name(name):
                yield channel

    def get_channels_by_type(self, channel_type: ChannelProperties.Type) -> Generator[Channel, None, None]:
        """
        :param channel_type: The type of the channel to search for.
        :type channel_type: ChannelProperties.Type

        :return: A generator of channels in the multi-hardware instance with the given type.
        :rtype: Generator[Channel, None, None]
        """
        for hardware in self.hardware_list:
            for channel in hardware.get_channels_by_type(channel_type):
                yield channel

    def get_hardware(self) -> Generator[Hardware, None, None]:
        """
        :return: A generator of all hardware in the multi-hardware instance.
        :rtype: Generator[Hardware, None, None]
        """
        for hardware in self.hardware_list:
            yield hardware

    def get_hardware_by_name(self, name: str) -> Generator[Hardware, None, None]:
        """
        :param name: The name of the hardware to search for.
        :type name: str

        :return: A generator of hardware in the multi-hardware instance with the given name.
        :rtype: Generator[Hardware, None, None]
        """
        for hardware in self.hardware_list:
            if hardware.name == name:
                yield hardware


class Module(Serializable):
    """
    A base class for module.

    :param name: The name of the module.
    :type name: str

    :return: Module instance
    :rtype: Module
    """

    def __init__(self, name: str):
        self.name = name

    def initialize(self) -> None:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")

    def close(self) -> None:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")


class InputModule(Module, Channel):
    """
    The InputModule base class is a subclass of Module and Channel, providing a specialized interface for handling input data.
    It defines the structure and behavior of an input module, which can be used to receive and process input data from various sources.

    :param name: The name of the module.
    :type name: str
    :param type: The type of the channel.
    :type type: ChannelProperties.Type
    :param unit: The unit of measurement of the channel.
    :type unit: str
    :param model: The model of the channel.
    :type model: Model

    :return: InputModule instance
    :rtype: InputModule
    """

    def __init__(self, name: str, type: ChannelProperties.Type, unit: str, model: Model):
        Module.__init__(self, name=name)
        Channel.__init__(self, name=name, type=type, unit=unit, model=model)

    def read(self) -> Data:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")


class OutputModule(Module):
    """
    The OutputModule base class is a subclass of Module, providing a specialized interface for handling output data.
    It defines the structure and behavior of an output module, which can be used to send and display output data to various destinations.

    :param name: The name of the module0.
    :type name: str

    :return: OutputModule instance
    :rtype: OutputModule
    """

    def __init__(self, name: str):
        super().__init__(name=name)

    def write(self) -> None:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")
