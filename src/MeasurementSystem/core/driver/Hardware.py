from __future__ import annotations

import math
import os
import re
import threading
import time
from collections.abc import Generator
from typing import Any, Dict, List, NewType, Tuple, Union

import lgpio
from daqhats import TcTypes, mcc118, mcc134
from daqhats.hats import OptionFlags

GPIOHandle = NewType("GPIOHandle", int)
Time_ns = NewType("Time_ns", int)

import importlib


class Data:
    """
    :class:`Data` provides a container for storing and managing data, including its values, units, and other relevant metadata.

    :return: None
    :rtype: None
    """

    def __init__(self) -> None:
        """
        Initialize a Data object.

        This method initializes a Data object. It creates an empty list to store
        data points.

        :return: None
        :rtype: None
        """

        self._data_list = []

    def add_value(self, value) -> None:
        """
        Add a value to the data list with the current timestamp in nanoseconds.

        :param value: The value to add to the data list.
        :type value: float

        :return: None
        :rtype: None
        """
        timestamp = time.time_ns()
        self._data_list.append((value, timestamp))

    def clear(self) -> None:
        """
        Clear all data points from the data list.

        :return: None
        :rtype: None
        """
        self._data_list.clear()

    def __iter__(self) -> Generator[Tuple[float, Time_ns], None, None]:
        """
        Iterate over the data points.

        :return: An iterator over the data points with the according timestamp.
        :rtype: Iterator[Tuple[float, Time_ns]]
        """
        return iter(self._data_list)

    def get_last(self) -> Tuple[float, Time_ns]:
        """
        Get the last data point.

        :return: The last data point in the data list. If the data list is empty, None is returned.
        :rtype: Tuple[float, Time_ns]
        """
        if self._data_list:
            return self._data_list[-1]  # TODO: check if .copy() is needed like in get_all
        return None  # TODO: check if raising an error is needed

    def get_all(self) -> List[Tuple[float, Time_ns]]:
        """
        Get a copy of all data points.

        :return: A copy of all data points in the data list.
        :rtype: List[Tuple[float, Time_ns]]
        """
        return self._data_list.copy()

    def get_count(self) -> int:
        """
        Get the number of data points in the data list.

        :return: The number of data points in the data list.
        :rtype: int
        """
        return len(self._data_list)


class Serializable:
    """
    A base class for objects that can be serialized and deserialized.

    The Serializable class provides a common interface for objects that need to be converted to and from a serialized format,
    such as JSON or XML. It defines methods for serializing and deserializing objects, allowing them to be easily stored or transmitted.
    """

    def to_dict(self):
        """
        Convert an object to a dictionary.

        This method returns a dictionary representation of an object. If the object
        has a __dict__ attribute, it is used to construct the dictionary. If not,
        the object is assumed to be a list and it is converted to a list of
        dictionaries by calling to_dict on each element.

        :return: A dictionary representation of the object.
        :rtype: Dict
        """

        if hasattr(self, "__dict__"):
            return {
                "id": id(self),
                "class": self.__class__.__name__,
                "module": self.__module__,
                "attributes": {
                    k: (v.to_dict() if isinstance(v, Serializable) else v)
                    for k, v in self.__dict__.items()
                    if not k.startswith("_")
                },
            }
        if isinstance(self, list):
            return [i.to_dict() for i in self]
        return self

    @classmethod
    def from_dict(cls, data: Dict[str, Any], references: Dict[int, Any] = None):
        """
        Create an instance of a Serializable class from a dictionary.

        This method creates an instance of a Serializable class from a dictionary.
        The dictionary should contain the following keys:
        - 'class': The name of the class to create an instance of.
        - 'module': The name of the module where the class is defined.
        - 'id': A unique identifier for the instance.
        - 'attributes': A dictionary of attributes to set on the instance.

        If the 'attributes' dictionary contains a key with a value that is a
        dictionary, it is assumed to be a Serializable object and is converted
        to an instance using from_dict. If the value is a list, each element of
        the list is converted to an instance using from_dict.

        If the 'attributes' dictionary contains a key with a value that is not
        a dictionary or a list, it is set as an attribute of the instance using
        setattr.

        If the instance has an 'initialize' method, it is called after all
        attributes have been set.

        :param data: The dictionary to create an instance from.
        :type data: Dict[str, Any]
        :param references: A dictionary to store references to created instances.
        :type references: Dict[int, Any]

        :return: The created instance.
        :rtype: Any
        """

        if references is None:
            references = {}

        if "reference" in data:
            return references[data["reference"]]

        module_name = data["module"]
        class_name = data["class"]
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)

        instance = cls.__new__(cls)
        references[data["id"]] = instance  # Store the instance in the references
        attributes = data.get("attributes", {})

        for key, value in attributes.items():
            if isinstance(value, dict) and "class" in value and "module" in value:
                setattr(instance, key, Serializable.from_dict(value))
            elif isinstance(value, list):
                setattr(
                    instance,
                    key,
                    [Serializable.from_dict(item) if isinstance(item, dict) else item for item in value],
                )
            else:
                # Check if the key corresponds to a property with a setter
                if (
                    hasattr(instance.__class__, key)
                    and isinstance(getattr(instance.__class__, key), property)
                    and getattr(instance.__class__, key).fset
                ):
                    getattr(instance, key, value)
                else:
                    setattr(instance, key, value)

        if hasattr(instance, "initialize"):
            instance.initialize()

        return instance


class Model(Serializable):
    """
    A base class for mathematical models.
    """

    @staticmethod
    def parse_model_list(model_list_str: str, model_registry: dict) -> List[Model]:
        """
        Parse a `string of model` instances into a list of Model instances.

        :param model_list_str: The string of model instances to parse.
        :type model_list_str: str
        :param model_registry: A dictionary containing the available models, where the keys are the model names and the values are the model classes.
        :type model_registry: dict

        :return: A list of Model instances parsed from the string.
        :rtype: List[Model]
        """

        # Remove the outer square brackets
        model_list_str = model_list_str.strip("[]")
        model_strs = re.split(r",\s*(?![^()]*\))", model_list_str)  # Split by comma not inside parentheses

        models = []
        for model_str in model_strs:
            model_str = model_str.strip()
            # Handle the instantiation of models using eval
            # Ensure that model_registry is accessible to eval
            model_str = f"{model_str}"  # Ensure the string is in the correct format
            model_instance = eval(model_str, {"ModelMeta": ModelMeta, **model_registry})
            models.append(model_instance)
        return models

    def apply(self, value: float) -> float:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")

    def to_string(self) -> str:
        """To be implemented by subclasses."""
        raise NotImplementedError("This method should be implemented by subclasses")


class ModelMeta(type):
    """
    A metaclass for Model classes that provides additional functionality and validation.

    The ModelMeta class is a metaclass that is used to create Model classes. It provides a way to define and enforce certain
    constraints and behaviors on Model classes, such as ensuring that they have certain methods or attributes.

    :param name: The name of the class.
    :type name: str
    :param bases: The base classes of the class.
    :type bases: tuple
    :param attrs: The attributes of the class.
    :type attrs: dict
    """

    model_registry = {}

    def __init__(cls, name, bases, attrs):
        """
        Register the model in the model registry.

        This method is called when a subclass of Model is defined. It registers the
        subclass in the model registry, which is a dictionary mapping model names to
        model classes.
        """
        super().__init__(name, bases, attrs)
        if name != "Model":
            ModelMeta.model_registry[name] = cls


class StackedModel(Model, metaclass=ModelMeta):
    """
    A Model that consists of multiple sub-models stacked together.

    The StackedModel class is a type of Model that combines multiple sub-models to produce a final output.
    It provides a way to create complex models by stacking simpler models together.

    The order of the models in the list is important. The first defined model is the first to be applied to the input value.



    :param models: A list of Model instances.
    :type models: List[Model]

    :return: A new StackedModel instance.
    :rtype: StackedModel

    Example:

        .. code-block:: python

            from MeasurementSystem.core.driver.Hardware import Channel
            from MeasurementSystem.core.driver.Hardware import StackedModel
            from MeasurementSystem.core.driver.Hardware import LinearModel
            channel = Channel("test", value=300, model=LinearModel(offset=0, gain=1))
            channel.set_model_from_str("StackedModel([LinearModel(offset=100, gain=1), LinearModel(offset=0, gain=10)])")

    """

    def __init__(self, models: List[Model]):
        self.models = models  # models are stored like a stack: 1st defined, 1st applied --> be aware of order!

    def apply(self, value: float) -> float:
        """
        Apply the stacked models to a value in order of the models in the list. The result
        of each model is passed as the input to the next model in the stack.

        :param value: The value to apply the stacked models to.
        :type value: float

        :return: The result of applying the stacked models to the given value.
        :rtype: float
        """

        for model in self.models:
            value = model.apply(value)
        return value

    def to_string(self) -> str:
        """
        :return: A string representation of the StackedModel instance.
        :rtype: str
        """

        models_str = ", ".join(model.to_string() for model in self.models)
        return f"StackedModel([{models_str}])"


class LinearModel(Model, metaclass=ModelMeta):
    """
    A model for a linear expression.
    output = input * gain + offset

    :param offset: The offset of the linear model.
    :type offset: float
    :param gain: The gain of the linear model.
    :type gain: float

    :return: A new LinearModel instance.
    :rtype: LinearModel
    """

    def __init__(self, offset: float, gain: float):
        self.name = "LinearModel"
        self.offset = offset
        self.gain = gain

    def apply(self, value: float) -> float:
        """
        Apply the linear model to a value.

        :param value: The value to apply the linear model to.
        :type value: float

        :return: The result of applying the linear model to the given value.
        :rtype: float
        """
        return value * self.gain + self.offset

    def to_string(self) -> str:
        """
        :return: A string representation of the LinearModel instance.
        :rtype: str
        """
        return f"LinearModel(offset={self.offset}, gain={self.gain})"


class NTCModel(Model, metaclass=ModelMeta):
    """
    A model for an NTC thermistor.
    The model describes the mathematical relationship between the resistance and temperature.

    :param r0: The nominal resistance of the NTC thermistor at the reference temperature T0.
    :type r0: float
    :param beta: The beta value of the NTC thermistor.
    :type beta: float
    :param t0: The reference temperature in Celsius. Defaults to 25 degrees Celsius.

    :return: A new NTCModel instance.
    :rtype: NTCModel
    """

    def __init__(self, r0: float, beta: float, t0: float = 25):
        self.name = "NTCModel"
        self.r0 = r0
        self.beta = beta
        self.t0 = t0 + 273.15  # convert T0 from Celsius to Kelvin

    def apply(self, resistance: float) -> float:
        """
        Apply the NTCModel to a given resistance value.

        :param resistance: The resistance value to apply the NTCModel to.
        :type resistance: float

        :return: The temperature in Celsius.
        :rtype: float

        Note
        ----
        The temperature is calculated using the formula
        T = 1 / (1 / T0 + 1 / beta * ln(R/R0))
        where T0 is the reference temperature in Kelvin, beta is the beta value
        of the NTC thermistor, R is the given resistance value, and R0 is the
        nominal resistance of the NTC thermistor at the reference temperature.
        The result is converted from Kelvin to Celsius before being returned.
        """
        temperature = 1 / (1 / self.t0 + 1 / self.beta * math.log(resistance / self.r0))
        return temperature - 273.15  # convert temperature from Kelvin to Celsius

    def to_string(self) -> str:
        """
        :return: A string representation of the NTCModel instance.
        :rtype: str
        """
        return f"NTCModel(r0={self.r0}, beta={self.beta}, t0={self.t0 - 273.15})"


class PTxModel(Model, metaclass=ModelMeta):
    """
    A model for a PT100 or PT1000 or similar platinum resistance temperature sensor (PTx).
    The model describes the mathematical relationship between the resistance and temperature.

    :param r0: The nominal resistance of the PTx thermistor at the reference temperature.
    :type r0: float

    :return: A new PTxModel instance.
    :rtype: PTxModel
    """

    def __init__(self, r0: float):
        self.name = "PTxModel"
        self.r0 = r0
        self.alpha = 3.85e-3

    def apply(self, resistance: float) -> float:
        """
        Apply the PTxModel to a given resistance value.

        :param resistance: The resistance value to apply the PTxModel to.
        :type resistance: float

        :return: The temperature in Celsius.
        :rtype: float

        Note
        ----
        The temperature is calculated using the formula
        T = (R - R0) / (R0 * alpha)
        where R is the given resistance value, R0 is the nominal resistance of the
        PTx thermistor at the reference temperature, and alpha is the temperature
        coefficient of the PTx thermistor.
        """
        return (resistance - self.r0) / (self.r0 * self.alpha)

    def to_string(self) -> str:
        """
        :return: A string representation of the PTxModel instance.
        :rtype: str
        """
        return f"PTxModel(r0={self.r0})"


class KTYxModel(Model, metaclass=ModelMeta):
    """
    A model for a KTY81-110 or similar silicon temperature sensor.
    The model describes the mathematical relationship between the sensor's resistance and temperature.

    :param r0: The nominal resistance of the KTYx thermistor at the reference temperature T0.
    :type r0: float
    :param alpha: The temperature coefficient of the KTYx thermistor. Defaults to 7.88e-3.
    :type alpha: float
    :param beta: The non-linear coefficient of the KTYx thermistor. Defaults to 1.937e-5.
    :type beta: float
    :param t0: The reference temperature in Celsius. Defaults to 25 degrees Celsius.

    :return: A new KTYxModel instance.
    :rtype: KTYxModel
    """

    def __init__(
        self,
        r0: float,
        alpha: float = 7.88e-3,
        beta: float = 1.937e-5,
        t0: float = 25.0,
    ):
        self.name = "KTYxModel"
        self.r0 = r0
        self.alpha = alpha
        self.beta = beta
        self.t0 = t0

    def apply(self, resistance: float) -> float:
        """
        Apply the KTYxModel to a given resistance value.

        :param resistance: The resistance value to apply the KTYxModel to.
        :type resistance: float

        :return: The temperature in Celsius.
        :rtype: float

        Note
        ----
        Calculation Info: https://docs.rs-online.com/2611/0900766b800910a6.pdf
        """

        kT = resistance / self.r0
        x = self.alpha**2 - 4 * self.beta + 4 * self.beta * kT
        temperature = self.t0 + (math.sqrt(x) - self.alpha) / (2 * self.beta)

        return temperature

    def to_string(self) -> str:
        """
        :return: A string representation of the KTYxModel instance.
        :rtype: str
        """
        return f"KTYxModel(r0={self.r0}, alpha={self.alpha}, beta={self.beta}, t0={self.t0})"


class Config(Serializable):
    """
    A class representing the configuration settings, allowing for easy access and manipulation of settings.

    :param kwargs: A dictionary of keyword arguments to set as attributes of the instance.
    :type kwargs: dict

    :return: Config instance
    :rtype: Config
    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


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


class Hardware_RaspberryPi(Hardware):
    """
    Represents a Raspberry Pi 5 hardware instance.

    :param name: The name of the hardware instance.
    :type name: str
    :param gpiochip: The gpiochip to use. Defaults to 4.

    :return: Hardware_RaspberryPi instance
    :rtype: Hardware_RaspberryPi
    """

    def __init__(self, name, gpiochip: int = 4):
        self.name = name
        self.gpiochip = gpiochip
        self.initialize()

    def initialize(self) -> None:
        """
        Initialize a Hardware_RaspberryPi instance.

        :return: None
        :rtype: None
        """
        super().__init__(name=self.name)
        handle = lgpio.gpiochip_open(self.gpiochip)  # Open gpiochip4 --> GPIOs
        self._handle = GPIOHandle(handle)  # Cast handle to GPIOHandle

    @property
    def handle(self) -> GPIOHandle:
        """
        :return: The handle of the gpiochip.
        :rtype: GPIOHandle
        """
        return self._handle

    @handle.setter
    def handle(self, handle: GPIOHandle) -> None:
        """
        :param handle: The handle of the gpiochip.
        :type handle: GPIOHandle

        :return: None
        :rtype: None
        """
        self._handle = handle

    def close(self) -> None:
        """
        Close the Hardware_RaspberryPi instance.

        :return: None
        :rtype: None
        """
        super().close()
        if self.handle is not None:
            lgpio.gpiochip_close(self.handle)
            self.handle = None


class Channel_RPI_FrequencyCounter(InputChannel):
    """
    A Raspberry Pi-based frequency counter input channel.
    The frequency is measured continuously in a thread-safe way and can be read anytime using the `read` method.

    :param handle: The handle of the gpiochip.
    :type handle: GPIOHandle
    :param name: The name of the channel.
    :type name: str
    :param pin: The pin to use for frequency counting.
    :type pin: int
    :param unit: The unit of the frequency. Defaults to "Hz".
    :type unit: str
    :param model: The model to use for frequency counting. Defaults to LinearModel(offset=0, gain=1).
    :type model: Model
    :param **config: Additional keyword arguments to store as a Config instance.

    :return: Channel_RPI_FrequencyCounter instance
    :rtype: Channel_RPI_FrequencyCounter
    """

    def __init__(
        self,
        handle: GPIOHandle,
        name: str,
        pin: int,
        unit: str = "Hz",
        model: Model = LinearModel(offset=0, gain=1),
        **config,
    ):
        self._handle = handle
        self.name = name
        self.pin = pin
        self.unit = unit
        self.model = model

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the Channel_RPI_FrequencyCounter instance.

        :return: None
        :rtype: None
        """
        super().__init__(
            name=self.name,
            type=ChannelProperties.Type.FREQUENCY,
            unit=self.unit,
            model=self.model,
        )

        self._frequency = None
        self._data = Data()

        # NOTE: check if needed and implement arguments in __init__
        self._debounce_micros = 5
        self._monitor_duration_seconds = 0.1

        self._monitoring_edges = (
            lgpio.BOTH_EDGES
        )  # TODO: check if non 50% dutycycle signals are also valid with BOTH_EDGES

        # Setup GPIO
        lgpio.gpio_claim_alert(handle=self._handle, gpio=self.pin, eFlags=self._monitoring_edges)
        lgpio.gpio_set_debounce_micros(handle=self._handle, gpio=self.pin, debounce_micros=self._debounce_micros)

        # Initialize callback
        self._cb = lgpio.callback(handle=self._handle, gpio=self.pin, edge=lgpio.BOTH_EDGES, func=None)

        # Start the background thread
        self._lock = threading.Lock()
        self._thread_stop_event = threading.Event()
        self._thread = threading.Thread(target=self._count_frequency)
        self._thread.daemon = True
        self._thread.start()

        if self._monitor_duration_seconds < 10:
            time.sleep(2 * self._monitor_duration_seconds)
        else:
            print(
                f"WARNING: monitor_duration_seconds={self._monitor_duration_seconds}, wait at least that time to get a valid measurement"
            )

    def _count_frequency(self) -> None:
        """
        Measure the frequency of the input channel.
        """
        while not self._thread_stop_event.is_set():
            t0 = time.time()
            self._cb.reset_tally()
            time.sleep(self._monitor_duration_seconds)
            edge_count = self._cb.tally()
            t1 = time.time()

            if self._monitoring_edges == lgpio.BOTH_EDGES:
                frequency = (
                    edge_count / (t1 - t0) / 2
                )  # both edges -> half period -> double count, therefore divide by 2
            else:
                frequency = edge_count / (t1 - t0)

            # thread save update of _frequency
            with self._lock:
                self._frequency = self.model.apply(frequency)  # * self.gain + self.offset
                self._data.add_value(self._frequency)

    def read(self) -> Data:
        """
        Read the frequency of the channel. Thread safe.

        :return: The frequency of the channel.
        :rtype: Data
        """
        with self._lock:
            # return self._frequency
            return self._data

    def close(self) -> None:
        """
        Close the frequency counter channel.

        This method stops the frequency counter thread, cancels the callback,
        clears the data queue, and frees the GPIO pin.

        :return: None
        :rtype: None
        """

        self._thread_stop_event.set()
        self._thread.join(timeout=1)
        self._thread = None
        self._thread_stop_event.clear()
        self._cb.cancel()
        self._frequency = None
        self._data.clear()
        lgpio.gpio_free(self._handle, self.pin)


class Channel_RPI_DigitalInput(InputChannel):
    """
    A Raspberry Pi-based digital input channel.

    :param handle: The handle of the gpiochip.
    :param name: The name of the channel.
    :param pin: The pin to use for digital input.
    :param unit: The unit of the digital input. Defaults to "High/Low".
    :param model: The model to use for digital input. Defaults to LinearModel(offset=0, gain=1).
    :param config: Additional keyword arguments to store as a Config instance.

    :return: A Channel_RPI_DigitalInput instance.
    :rtype: Channel_RPI_DigitalInput
    """

    def __init__(
        self,
        handle: GPIOHandle,
        name: str,
        pin: int,
        unit: str = "High/Low",
        model: Model = LinearModel(offset=0, gain=1),
        **config,
    ):
        self._handle = handle
        self.name = name
        self.pin = pin
        self.unit = unit
        self.model = model

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the digital input channel.

        :return: None
        :rtype: None
        """
        super().__init__(
            name=self.name,
            type=ChannelProperties.Type.DIGITAL_IN,
            unit=self.unit,
            model=self.model,
        )

        self._pin_status = None
        self._data = Data()

        # Setup GPIO
        lgpio.gpio_claim_alert(handle=self._handle, gpio=self.pin, eFlags=lgpio.BOTH_EDGES)
        lgpio.gpio_set_debounce_micros(handle=self._handle, gpio=self.pin, debounce_micros=5)

        # Read the status of the pin
        self._pin_status = lgpio.gpio_read(handle=self._handle, gpio=self.pin)

        # Initialize callback
        self._cb = lgpio.callback(
            handle=self._handle,
            gpio=self.pin,
            edge=lgpio.BOTH_EDGES,
            func=self._callback,
        )

    def _callback(self, handle, gpio, level, tick) -> None:
        """
        Callback for the digital input pin.

        This method is called whenever the digital input pin changes state. It
        updates the pin status and adds the new value to the data queue.

        :param handle: The handle of the gpiochip.
        :param gpio: The GPIO pin number.
        :param level: The level of the GPIO pin (0 or 1).
        :param tick: The tick of the GPIO pin.

        :return: None
        :rtype: None
        """
        self._pin_status = self.model.apply(float(level))  # float(level) * self.gain + self.offset
        self._data.add_value(self._pin_status)

    def read(self) -> Data:
        """
        Read the digital input channel.

        :return: The digital input channel.
        :rtype: Data
        """
        return self._data

    def readRaw(self) -> int:
        """
        Read the raw digital input channel.

        :return: The raw digital input channel.
        :rtype: int
        """
        return lgpio.gpio_read(handle=self._handle, gpio=self.pin)

    def close(self) -> None:
        """
        Close the digital input channel.

        This method stops the callback, clears the data queue, and frees the GPIO pin.

        :return: None
        :rtype: None
        """
        self._cb.cancel()
        self._pin_status = None
        self._data.clear()
        lgpio.gpio_free(self._handle, self.pin)


class Channel_RPI_BufferedDigitalInput(Channel_RPI_DigitalInput):
    """
    A buffered Raspberry Pi-based digital input channel.

    :param handle: The handle of the gpiochip.
    :param name: The name of the channel.
    :param pin: The pin to use for digital input.
    :param unit: The unit of the digital input. Defaults to "High/Low".
    :param model: The model to use for digital input. Defaults to LinearModel(offset=0, gain=1).
    :param config: Additional keyword arguments to store as a Config instance.

    :return: A Channel_RPI_BufferedDigitalInput instance.
    :rtype: Channel_RPI_BufferedDigitalInput
    """

    def __init__(
        self,
        handle: GPIOHandle,
        name: str,
        pin: int,
        unit: str = "High/Low",
        model: Model = LinearModel(offset=0, gain=1),
        **config,
    ):
        self._handle = handle
        self.name = name
        self.pin = pin
        self.unit = unit
        self.model = model

        # # Store the config as an instance of Config
        # self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize a Channel_RPI_BufferedDigitalInput instance.

        This method calls the superclass's `initialize` method and initializes
        the internal data buffer.

        :return: None
        :rtype: None
        """
        super().initialize()  # TODO: what about the config??
        self._data = Data()

    def _callback(self, handle, gpio, level, tick) -> None:
        """
        Callback for the digital input pin.

        This method is called whenever the digital input pin changes state. It
        updates the pin status and adds the new value to the data queue.

        :return: None
        :rtype: None
        """
        value = self.model.apply(float(level))
        self._data.add_value(value)

    def read(self) -> Data:
        """
        :return: The last value of the buffered digital input channel.
        :rtype: Data
        """
        return self._data

    def close(self) -> None:
        """
        Close the buffered digital input channel.

        This method clears the data queue and calls the superclass's `close` method.

        :return: None
        :rtype: None
        """
        self._data.clear()
        super().close()


class Channel_RPI_DigitalOutput(OutputChannel):
    """
    A Raspberry Pi-based digital output channel.

    :param handle: The handle of the gpiochip.
    :param name: The name of the channel.
    :param pin: The pin to use for digital output.
    :param unit: The unit of the digital output. Defaults to "High/Low".
    :param model: The model to use for digital output. Defaults to LinearModel(offset=0, gain=1).
    :param config: Additional keyword arguments to store as a Config instance.

    :return: A Channel_RPI_DigitalOutput instance.
    :rtype: Channel_RPI_DigitalOutput
    """

    def __init__(
        self,
        handle: GPIOHandle,
        name: str,
        pin: int,
        unit: str = "High/Low",
        model: Model = LinearModel(offset=0, gain=1),
        **config,
    ):
        self._handle = handle
        self.name = name
        self.pin = pin
        self.unit = unit
        self.model = model

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the digital output channel.

        :return: None
        :rtype: None
        """
        super().__init__(
            name=self.name,
            type=ChannelProperties.Type.DIGITAL_OUT,
            unit=self.unit,
            model=self.model,
        )

        # Setup GPIO
        level = 0
        lgpio.gpio_claim_output(self._handle, self.pin, level=level, lFlags=lgpio.SET_PULL_DOWN)
        self.level = level

    def write(self, value: int) -> None:
        """
        Write the given value to the digital output channel.

        :param value: The value to write to the digital output channel.
        :type value: int

        :return: None
        :rtype: None
        """
        lgpio.gpio_write(handle=self._handle, gpio=self.pin, level=value)
        self.level = value

    def close(self) -> None:
        """
        Close the digital output channel.

        :return: None
        :rtype: None
        """
        self.level = None
        lgpio.gpio_free(self._handle, self.pin)


class Channel_RPI_InternalTemperature(InputChannel):
    """
    A Raspberry Pi-based internal temperature input channel.

    :param name: The name of the channel.
    :param unit: The unit of the temperature. Defaults to "Celsius".
    :param model: The model to use for internal temperature measurement. Defaults to LinearModel(offset=0, gain=1).
    :param config: Additional keyword arguments to store as a Config instance.

    :return: A Channel_RPI_InternalTemperature instance.
    :rtype: Channel_RPI_InternalTemperature
    """

    def __init__(
        self,
        name="InternalTemperature",
        unit="Celsius",
        model: Model = LinearModel(offset=0, gain=1),
        **config,
    ):
        self.name = name
        self.unit = unit
        self.model = model

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the internal temperature channel.

        :return: None
        :rtype: None
        """
        super().__init__(
            name=self.name,
            type=ChannelProperties.Type.TEMPERATURE,
            unit=self.unit,
            model=self.model,
        )
        self._data = Data()

    def read(self) -> Data:
        """
        Read the internal temperature of the Raspberry Pi.

        This method reads the internal temperature of the Raspberry Pi by executing
        the "vcgencmd measure_temp" command and parsing the output.

        :return: The internal temperature of the Raspberry Pi.
        :rtype: Data
        """

        output = os.popen("vcgencmd measure_temp").readline()
        # Remove anything not like a digit or a decimal point
        result = re.sub("[^0-9.]", "", output)
        temperature = self.model.apply(float(result))  # float(result) * self.gain + self.offset

        self._data.add_value(temperature)

        # return self._temperature
        return self._data

    def close(self) -> None:
        """
        Close the internal temperature channel and clears the data buffer.

        :return: None
        :rtype: None
        """
        # self._temperature = None
        self._data.clear()


class Module_RPI_StepperMotor(MultiChannel, OutputModule):
    """
    A Raspberry Pi-based stepper motor control module.

    :param handle: The handle of the gpiochip.
    :param name: The name of the module.
    :param step_pin: The pin to use for step signal output.
    :param dir_pin: The pin to use for direction signal output.
    :param enable_pin: The pin to use for enable signal output.
    :param limitA_pin: The pin to use for limit A signal input.
    :param limitB_pin: The pin to use for limit B signal input.
    :param config: Additional keyword arguments to store as a Config instance.

    :return: A Module_RPI_StepperMotor instance.
    :rtype: Module_RPI_StepperMotor
    """

    def __init__(
        self,
        handle: GPIOHandle,
        name: str,
        step_pin: int,
        dir_pin: int,
        enable_pin: int,
        limitA_pin: int,
        limitB_pin: int,
        **config,
    ) -> None:
        self._handle = handle
        self.name = name

        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.enable_pin = enable_pin
        self.limitA_pin = limitA_pin
        self.limitB_pin = limitB_pin

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the Module_RPI_StepperMotor instance.

        :return: None
        :rtype: None
        """

        MultiChannel.__init__(self, name=self.name, input_channels=[], output_channels=[])
        OutputModule.__init__(self, self.name)

        self._channel_step_pin = Channel_RPI_DigitalOutput(self._handle, "StepPin", self.step_pin)
        self._channel_dir_pin = Channel_RPI_DigitalOutput(self._handle, "DirPin", self.dir_pin)
        self._channel_enable_pin = Channel_RPI_DigitalOutput(self._handle, "EnablePin", self.enable_pin)
        self._channel_limitA_pin = Channel_RPI_DigitalInput(self._handle, "LimitAPin", self.limitA_pin)
        self._channel_limitB_pin = Channel_RPI_DigitalInput(self._handle, "LimitBPin", self.limitB_pin)

        self.add_channels(self._channel_step_pin)
        self.add_channels(self._channel_dir_pin)
        self.add_channels(self._channel_enable_pin)
        self.add_channels(self._channel_limitA_pin)
        self.add_channels(self._channel_limitB_pin)

        self._thread = None
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()

        self._max_steps = None
        self._direction = None
        self._position = 0

    def enable_stepper(self) -> None:
        """
        Enable the stepper motor.

        This method will set the enable pin to HIGH to enable the stepper motor.

        :return: None
        :rtype: None
        """
        self._channel_enable_pin.write(1)

    def disable_stepper(self) -> None:
        """
        Disable the stepper motor.

        This method will set the enable pin to LOW to disable the stepper motor.

        :return: None
        :rtype: None
        """
        self._channel_enable_pin.write(0)

    def getPosition(self) -> int:
        """
        Get the current position of the stepper motor.

        :return: The current position of the stepper motor.
        :rtype: int
        """

        return self._position

    def setDirection(self, direction: int) -> None:
        """
        Set the direction of the stepper motor.

        :param direction: 1 to move towards limitA, 0 to move towards limitB.
        :type direction: int

        :return: None
        :rtype: None
        """

        self._channel_dir_pin.write(direction)
        self._direction = direction

    def write(self, direction, steps, duration) -> None:
        """
        Write a command to the stepper motor to move a given number of steps in a given direction.
        The method will block until the move is complete.

        :param direction: 1 to move towards limitA, 0 to move towards limitB.
        :type direction: int
        :param steps: The number of steps to move.
        :type steps: int
        :param duration: The maximum time to wait for the move to complete.
        :type duration: float

        :return: None
        :rtype: None
        """
        self._thread = threading.Thread(target=self._drive_motor, args=(direction, steps, duration))
        self._thread.daemon = True
        self._thread.start()
        self._thread.join(timeout=duration + 1)  # Wait for thread to finish

    def _drive_motor(self, direction, steps, duration=None) -> None:
        """
        Internal method to drive the stepper motor. (Thread function)

        :param direction: 1 to move towards limitA, 0 to move towards limitB.
        :type direction: int
        :param steps: The number of steps to move.
        :type steps: int
        :param duration: The maximum time to wait for the move to complete.
        :type duration: float

        :return: None
        :rtype: None
        """

        with self._lock:
            if self._running:
                return
            self._running = True

        # Limit Check Thread
        def check_limits():
            while not self._stop_event.is_set():
                if (
                    direction == 1
                    and self._channel_limitA_pin.read()
                    or direction == 0
                    and self._channel_limitB_pin.read()
                ):
                    self._stop_event.set()
                time.sleep(0.01)  # Check limits every 10ms

        limit_thread = threading.Thread(target=check_limits)
        limit_thread.daemon = True
        limit_thread.start()

        # Set Direction
        self.setDirection(direction)

        # Generate steps
        if duration:
            steps_frequency = steps / duration  # Steps per second
        else:
            steps_frequency = 100  # Steps per second

        lgpio.tx_pwm(
            handle=self._handle,
            gpio=self._channel_step_pin.pin,
            pwm_frequency=steps_frequency,
            pwm_duty_cycle=50,
            pulse_cycles=steps,
        )  # Generate 50% PWM for steps

        # Wait until the desired number of steps are completed or stop event is set
        self._stop_event.wait(
            timeout=duration + 1 / steps_frequency
        )  # plus wait for one addional step --> TODO: replace with step feedback loop

        with self._lock:
            self._running = False

        # Stop the limit check thread
        self._stop_event.set()
        limit_thread.join(timeout=1)
        self._stop_event.clear()

    def calibrate(self, timeout_steps=10000) -> None:
        """
        Calibrate the stepper motor.

        This method moves the stepper motor until it hits one of its limits,
        then moves it in the other direction until it hits the other limit.
        The maximum number of steps between the limits is stored in the
        _max_steps attribute.

        :param timeout_steps: The maximum number of steps to move.
        :type timeout_steps: int

        :return: None
        :rtype: None
        """

        steps_fwd = 0
        steps_bwd = 0

        # Move until limitA
        self.setDirection(1)
        self.enable_stepper()

        steps_fwd = 0
        while not self._channel_limitA_pin.read():
            self._channel_step_pin.write(1)
            time.sleep(0.001)
            self._channel_step_pin.write(0)
            time.sleep(0.001)
            steps_fwd += 1
            if steps_fwd > timeout_steps:
                break

        time.sleep(0.5)

        # Move until limitB
        self.setDirection(0)

        steps_bwd = 0
        while not self._channel_limitB_pin.read():
            self._channel_step_pin.write(1)
            time.sleep(0.001)
            self._channel_step_pin.write(0)
            time.sleep(0.001)
            steps_bwd += 1
            if steps_bwd > timeout_steps:
                break

        self.disable_stepper()

        self._max_steps = max(steps_fwd, steps_bwd)
        self._position = 0
        print(f"Calibration complete. Max steps between limits: {self._max_steps}")

    def close(self) -> None:
        """
        Close the Module_RPI_StepperMotor instance.

        :return: None
        :rtype: None
        """

        MultiChannel.close(self)


class Module_RPI_WeighScalesHX711(MultiChannel, InputModule):
    """
    A Raspberry Pi-based HX711 weight scales input module.

    :param handle: The handle of the gpiochip.
    :type handle: GPIOHandle
    :param name: The name of the module.
    :type name: str
    :param data_pin: The pin to use for data input from the HX711.
    :type data_pin: int
    :param clock_pin: The pin to use for clock input to the HX711.
    :type clock_pin: int
    :param model: The model of the HX711.
    :type model: Model

    :return: Module_RPI_WeighScalesHX711 instance
    :rtype: Module_RPI_WeighScalesHX711
    """

    class ReadType:
        """
        Enumeration-like class representing different read types.
        """

        RAW = 0
        AVG = 1
        MEDIAN = 2

    def __init__(
        self,
        handle: GPIOHandle,
        name,
        data_pin: int,
        clock_pin: int,
        model: Model = LinearModel(offset=0, gain=1),
        **config,
    ):
        self._handle = handle
        self.name = name
        self.data_pin = data_pin
        self.clock_pin = clock_pin
        self.model = model

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the Module_RPI_WeighScalesHX711 instance.

        :return: None
        :rtype: None
        """

        MultiChannel.__init__(self, self.name, input_channels=[], output_channels=[])
        InputModule.__init__(
            self,
            self.name,
            type=ChannelProperties.Type.WEIGHT,
            unit="kg",
            model=self.model,
        )

        self._channel_data_pin = Channel_RPI_DigitalInput(handle=self._handle, name="DATA", pin=self.data_pin)
        self._channel_clock_pin = Channel_RPI_DigitalOutput(handle=self._handle, name="CLOCK", pin=self.clock_pin)

        # NOTE: issue when adding channels later on in "get_channels" of multi_channel
        self.add_channels(self._channel_data_pin)
        self.add_channels(self._channel_clock_pin)

        self._data = Data()

        # default gain is 128
        self._hx711_gain = 128

        # Power down after initialization
        self.powerDown()

        # Measure tara
        self._tara = self._measure_tara()

    def read(self, type: ReadType = ReadType.RAW, count: int = 5) -> Data:
        """
        Read data from the HX711 module.

        :param type: The type of read to perform. Defaults to ReadType.RAW.
        :type type: Module_RPI_WeighScalesHX711.ReadType
        :param count: The number of values to read. Defaults to 5.
        :type count: int

        :return: Data object containing the read values.
        :rtype: Data
        """

        if type == self.ReadType.AVG:
            val = self.readAverage(count=count)
        elif type == self.ReadType.MEDIAN:
            val = self.readMedian(count=count)
        else:
            val = self.readRaw()

        self._data.add_value(self.model.apply(val))

        return self._data

    def _measure_tara(self) -> int:
        """
        Measure the tara (zero) value of the HX711 module.

        :return: The tara value.
        :rtype: int
        """
        tara = self.readMedian(count=10)
        return int(tara)

    def _is_ready(self) -> bool:
        """
        Check if the HX711 module is ready for a measurement.

        This method will read the data pin of the HX711 module and return True if the
        pin is low (0), indicating that the module is ready for a measurement.
        Otherwise it will return False.

        :return: True if the module is ready for a measurement, False otherwise.
        :rtype: bool
        """
        data = self._channel_data_pin.read()
        if data.get_count() > 0:
            val, _ = data.get_last()
            return val == 0
        return False

    def _send_clock_cycle(self, count=1) -> None:
        """
        Send a clock cycle to the HX711 module.

        :param count: The number of clock cycles to send. Defaults to 1.
        :type count: int

        :return: None
        :rtype: None
        """
        for _ in range(count):
            self._channel_clock_pin.write(1)
            self._channel_clock_pin.write(0)

    def _twos_complement_24bit_to_int(self, data) -> int:
        # Mask to get the lower 24 bits
        """
        Convert a 24-bit two's complement number to an integer.

        :param data: The 24-bit two's complement number to convert.
        :type data: int

        :return: The integer value of the 24-bit two's complement number.
        :rtype: int
        """

        mask = 0xFFFFFF
        # Apply the mask
        data &= mask
        # Check if the sign bit (24th bit) is set
        if data & 0x800000:  # 0x800000 is the 24th bit (2^23)
            # If the sign bit is set, calculate the negative value
            data -= 0x1000000  # Subtract 2^24
        return data

    def wakeup(self) -> None:
        """
        Wakeup the HX711 module with setting the clock pin low for 1 ms.

        :return: None
        :rtype: None
        """
        self._channel_clock_pin.write(0)
        time.sleep(0.001)

    def powerDown(self) -> None:
        """
        Power down the HX711 module with setting the clock pin high for 1 ms.

        :return: None
        :rtype: None
        """
        self._channel_clock_pin.write(1)
        time.sleep(0.001)

    def _wait_for_data_ready(self, t_timeout=3) -> None:
        # wait until HX711 is ready
        """
        Wait until the HX711 module is ready for a measurement.
        The method will timeout and power down the module if it is not ready.

        :param t_timeout: The timeout in seconds. Defaults to 3.
        :type t_timeout: float

        :return: None
        :rtype: None
        """
        t_start = time.time()
        while not self._is_ready():
            if time.time() - t_start > t_timeout:  # timeout after 3 seconds
                self.powerDown()
                raise TimeoutError("Timeout waiting for HX711")
            time.sleep(0.01)

    def _readBit(self) -> int:
        """
        Read a single bit from the HX711 module by sending a clock cycle.

        :return: The value of the bit.
        :rtype: int
        """
        self._send_clock_cycle()
        return self._channel_data_pin.readRaw()  # read is altert/callback based, use readRaw for direct read

    def readRaw(self, t_timeout=3) -> float:
        """
        Read a single measurement from the HX711 module. Only 24 bits are supported.

        :param t_timeout: The timeout in seconds. Defaults to 3.
        :type t_timeout: float

        :return: The raw value of the measurement.
        :rtype: float
        """
        self.wakeup()

        if t_timeout:
            self._wait_for_data_ready(t_timeout=3)

        # get 24 bits
        dataValue = 0
        for _ in range(24):
            dataValue = (dataValue << 1) | self._readBit()

        # send 25th bit: set channel A, gain=128 in next conversion
        self._send_clock_cycle(count=1)

        # TODO: implement for other channels/gain
        # when sending 26th bit: set channel B, gain=32 in next conversion
        # when sending 27th bit: set channel A, gain=64 in next conversion

        self.powerDown()

        return self._twos_complement_24bit_to_int(dataValue)

    def readAverage(self, count=5) -> int:
        """
        Read the average of 'count' raw values.

        :param count: The number of values to read. Defaults to 5.
        :type count: int

        :return: The average of the 'count' number of raw values.
        :rtype: int
        """
        values = []
        for _ in range(count):
            values.append(self.readRaw())
            avg = sum(values) // count
            # time.sleep(0.1)
        return avg  # int(sum(self.readRaw() for _ in range(count)) / count)

    def readMedian(self, count=5) -> int:
        """
        Read the median of 'count' raw values.

        :param count: The number of values to read. Defaults to 5.
        :type count: int

        :return: The median of the 'count' number of raw values.
        :rtype: int
        """
        values = []
        for _ in range(count):
            values.append(self.readRaw())
            median = sorted(values)[len(values) // 2]
            # time.sleep(0.1)
        return median  # int(sorted(self.readRaw() for _ in range(count))[int(count / 2)])

    def close(self) -> None:
        """
        Close the module.

        This method will clear the internal data queue and call the close method of the
        MultiChannel class to release any resources allocated by the module.

        :return: None
        :rtype: None
        """
        self._data.clear()
        MultiChannel.close(self)  # NOTE: self to ensure correct instance of close is called


class Module_RPI_ServoMotor(MultiChannel, OutputModule):
    """
    A Raspberry Pi-based servo motor control module.

    :param handle: The handle of the gpiochip.
    :type handle: GPIOHandle
    :param name: The name of the module.
    :type name: str
    :param servo_pin: The pin to use for servo motor control.
    :type servo_pin: int
    :param config: Additional keyword arguments to store as a Config instance.
    :type config: Config

    :return: A Module_RPI_ServoMotor instance.
    :rtype: Module_RPI_ServoMotor
    """

    def __init__(self, handle: GPIOHandle, name: str, servo_pin: int, **config) -> None:
        self._handle = handle
        self.name = name
        self.servo_pin = servo_pin

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the Module_RPI_ServoMotor instance.

        :return: None
        :rtype: None
        """
        MultiChannel.__init__(self, name=self.name, input_channels=[], output_channels=[])
        OutputModule.__init__(self, name=self.name)

        self._channel_servo_pin = Channel_RPI_DigitalOutput(handle=self._handle, name="SERVO_PIN", pin=self.servo_pin)

        self._servo_frequency = 50  # NOTE: check if needed and implement in __init__

        self.add_channels(self._channel_servo_pin)

    def write(self, percentage, pulse_cycles=0) -> None:
        """
        Set the servo motor output to a given percentage of the total range.

        :param percentage: The percentage of the total range to set the servo motor output to.
            0% corresponds to 1000us and 100% corresponds to 2000us.
        :type percentage: float
        :param pulse_cycles: The number of pulse cycles to send. Defaults to 0, which means continuous servo motor output.
        :type pulse_cycles: int

        :return: None
        :rtype: None
        """

        # 0% = 1000us
        # 100% = 2000us
        pulseWidth = int(1000 + (2000 - 1000) * percentage / 100)

        h = self._channel_servo_pin._handle
        p = self._channel_servo_pin.pin
        lgpio.tx_servo(
            handle=h,
            gpio=p,
            pulse_width=pulseWidth,
            servo_frequency=self._servo_frequency,
            pulse_offset=0,
            pulse_cycles=pulse_cycles,
        )  # pulse_cycles=0 --> continuous servo

    def close(self) -> None:
        """
        Close the Hardware_DigilentMCC118 instance.

        This method closes all channels in the Hardware_DigilentMCC118 instance.
        It also stops the servo motor output and closes the underlying gpiochip handle.

        :return: None
        :rtype: None
        """
        MultiChannel.close(self)


class Hardware_DigilentMCC118(Hardware):
    """
    A class representing the Digilent MCC 118 hardware device.

    :param name: The name of the hardware instance.
    :type name: str
    :param hat_address: The address of the Digilent MCC 118.
    :type hat_address: str

    :return: A Hardware_DigilentMCC118 instance.
    :rtype: Hardware_DigilentMCC118
    """

    def __init__(self, name, hat_address):
        self.name = name
        self.hat_address = hat_address
        self.initialize()

    def initialize(self) -> None:
        """
        Initialize a Hardware_DigilentMCC118 instance.

        :return: None
        :rtype: None
        """
        super().__init__(name=self.name)
        self.handle = mcc118(self.hat_address)

    @property
    def handle(self) -> mcc118:
        """
        :return: The handle of the MCC 118 device.
        :rtype: mcc118
        """
        return self._handle

    @handle.setter
    def handle(self, value: mcc118) -> None:
        """
        :param value: The handle of the MCC 118 device.
        :type value: mcc118
        """
        self._handle = value

    def close(self) -> None:
        """
        Close the Hardware_DigilentMCC118 instance.

        This method closes all channels in the Hardware_DigilentMCC118 instance.

        :return: None
        :rtype: None
        """
        super().close()
        # TODO: check if ressource close is needed


class Channel_MCC118_VoltageChannel(InputChannel):
    """
    A class representing a voltage input channel on the Digilent MCC 118 device.

    This class provides a software interface to a single voltage input channel on the MCC 118 device.

    :param handle: The handle of the MCC 118 device.
    :type handle: mcc118
    :param name: The name of the channel.
    :type name: str
    :param channel: The channel number on the MCC 118 (0-7).
    :type channel: int
    :param unit: The unit of the voltage measurement. Defaults to "V".
    :type unit: str
    :param model: The model to use for voltage measurement. Defaults to LinearModel(offset=0, gain=1).
    :type model: Model
    :param config: Additional keyword arguments to store as a Config instance.
    :type config: dict

    :return: A Channel_MCC118_VoltageChannel instance.
    :rtype: Channel_MCC118_VoltageChannel
    """

    def __init__(
        self,
        handle: mcc118,
        name: str,
        channel: int,
        unit: str = "V",
        model: Model = LinearModel(offset=0, gain=1),
        **config,
    ) -> None:
        self._handle = handle
        self.name = name
        self.channel = channel  # do not mix with self.hat.channels !
        self.unit = unit
        self.model = model

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the Channel_MCC118_VoltageChannel instance.

        :return: None
        :rtype: None
        """
        super().__init__(
            name=self.name,
            type=ChannelProperties.Type.VOLTAGE,
            unit=self.unit,
            model=self.model,
        )
        self._options = (
            OptionFlags.DEFAULT
        )  # TODO: check if needed and implement in __init__ & check if flags are correct
        self._data = Data()

    def read(self) -> Data:
        """
        Read a voltage measurement from the channel.

        :return: The voltage measurement.
        :rtype: Data
        """
        _voltage = self._handle.a_in_read(channel=self.channel, options=self._options)
        _voltage = self.model.apply(_voltage)

        self._data.add_value(_voltage)

        return self._data

    def close(self) -> None:
        """
        Close the voltage channel.

        This method stops the voltage channel, clears the internal data.

        :return: None
        :rtype: None
        """
        self._voltage = None
        self._data.clear()

    def to_dict(self):
        """
        :return: A dictionary representation of the voltage channel.
        :rtype: dict
        """

        # prevet RecursionError
        original_hat = self._handle
        self._handle = None
        d = super().to_dict()
        self._handle = original_hat

        return d


class Hardware_DigilentMCC134(Hardware):
    """
    A class representing the Digilent MCC 134 hardware device.

    :param name: The name of the hardware instance.
    :type name: str
    :param hat_address: The address of the Digilent MCC 134.
    :type hat_address: str

    :return: A Hardware_DigilentMCC134 instance.
    :rtype: Hardware_DigilentMCC134
    """

    def __init__(self, name, hat_address):
        self.name = name
        self.hat_address = hat_address
        self.initialize()

    def initialize(self) -> None:
        """
        Initialize a Hardware_DigilentMCC134 instance.

        :return: None
        :rtype: None
        """

        super().__init__(name=self.name)
        self.handle = mcc134(self.hat_address)

    @property
    def handle(self) -> mcc134:
        """
        :return: The handle of the MCC 134 device.
        :rtype: mcc134
        """
        return self._handle

    @handle.setter
    def handle(self, value: mcc134) -> None:
        """
        :param value: The handle of the MCC 134 device.
        :type value: mcc134
        """
        self._handle = value

    def close(self) -> None:
        """
        Close the Hardware_DigilentMCC134 instance.

        This method closes all channels in the Hardware_DigilentMCC134 instance.

        :return: None
        :rtype: None
        """
        super().close()  # TODO: check if ressource close is needed


class Channel_MCC134_ThermocoupleChannel(InputChannel):
    """
    A class representing a temerature input channel on the Digilent MCC 134 device.

    This class provides a software interface to a single temerature input channel on the MCC 134 device.

    :param handle: The handle of the MCC 134 device.
    :type handle: mcc134
    :param name: The name of the channel.
    :type name: str
    :param channel: The channel number on the MCC 134 (0-3).
    :type channel: int
    :param unit: The unit of the voltage measurement. Defaults to "degC".
    :type unit: str
    :param model: The model to use for voltage measurement. Defaults to LinearModel(offset=0, gain=1).
    :type model: Model
    :param config: Additional keyword arguments to store as a Config instance.
    :type config: dict

    :return: A Channel_MCC134_ThermocoupleChannel instance.
    :rtype: Channel_MCC134_ThermocoupleChannel
    """

    def __init__(
        self,
        handle: mcc134,
        name: str,
        channel: int,
        unit: str = "degC",
        model: Model = LinearModel(offset=0, gain=1),
        **config,
    ) -> None:
        self._handle = handle
        self.name = name
        self.channel = channel  # do not mix with self.hat.channels !
        self.unit = unit
        self.model = model

        # Store the config as an instance of Config
        self.config = Config(**config)

        self.initialize()

    def initialize(self) -> None:
        """
        Initialize the Channel_MCC134_VoltageChannel instance.

        :return: None
        :rtype: None
        """
        super().__init__(name=self.name, type=ChannelProperties.Type.VOLTAGE, unit=self.unit, model=self.model)

        self._handle.tc_type_write(self.channel, TcTypes.TYPE_K)  # NOTE: Hardcoded Type K, maybe improve
        self._handle.update_interval_write(1)  # once per second

        self._data = Data()

    def read(self) -> Data:
        """
        Read a temperature measurement from the channel.

        :return: The voltage measurement.
        :rtype: Data
        """
        temperature = self._handle.t_in_read(channel=self.channel)
        temperature = self.model.apply(temperature)

        self._data.add_value(temperature)
        return self._data

    def close(self) -> None:
        """
        Close the temperature channel.

        This method stops the temperature channel, clears the internal data.

        :return: None
        :rtype: None
        """
        self._data.clear()

    def to_dict(self):
        """
        :return: A dictionary representation of the temperature channel.
        :rtype: dict
        """

        # prevet RecursionError
        original_hat = self._handle
        self._handle = None
        d = super().to_dict()
        self._handle = original_hat

        return d


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


########################
# Example usage
if __name__ == "__main__":
    # Hardware: Raspberry Pi 5
    rpi_hardware = Hardware_RaspberryPi("RPI5")

    # Input Channels
    rpi_input_channels = [
        Channel_RPI_FrequencyCounter(
            handle=rpi_hardware.handle,
            name="RPI_GPIO_18",
            pin=18,
            unit="Hz",
            model=LinearModel(offset=0, gain=1),
            test=7,
        ),
        Channel_RPI_DigitalInput(
            handle=rpi_hardware.handle,
            name="RPI_GPIO_23",
            pin=23,
            unit="High/Low",
            model=LinearModel(offset=0, gain=1),
        ),
        Channel_RPI_InternalTemperature(
            name="InternalTemperature",
            unit="Celsius",
            model=LinearModel(offset=0, gain=1),
            sample_rate=1,
        ),
        # Add more channels here if needed
    ]
    rpi_hardware.add_channels(rpi_input_channels)

    # Multi Channels
    rpi_multi_channels = [
        Module_RPI_StepperMotor(
            handle=rpi_hardware.handle,
            name="Stepper",
            step_pin=24,
            dir_pin=25,
            enable_pin=16,
            limitA_pin=20,
            limitB_pin=21,
        ),
        Module_RPI_WeighScalesHX711(
            handle=rpi_hardware.handle,
            name="HX711",
            data_pin=5,
            clock_pin=6,
            model=LinearModel(offset=0, gain=1 / 22000),
        ),
        Module_RPI_ServoMotor(handle=rpi_hardware.handle, name="Servo_Module", servo_pin=22),
        # Add more multi channels here if needed
    ]
    rpi_hardware.add_channels(rpi_multi_channels)

    # # Test Stepper Motor
    # stepper = rpi_hardware.get_channels_by_name("Stepper")
    # assert isinstance(stepper, Module_RPI_StepperMotor)  # Check if it's an instance of StepperMotorChannels
    # stepper.write(direction=1, steps=5, duration=2)
    # stepper.write(direction=1, steps=5, duration=1)

    # # Test HX711
    # hx711 = rpi_hardware.get_channels_by_name("HX711")
    # assert isinstance(hx711, Module_RPI_WeighScalesHX711)  # Check if it's an instance of WeighScalesHX711

    # for i in range(10):
    # value = hx711.read(type=Module_RPI_WeighScalesHX711.ReadType.MEDIAN, count=5)
    #     print("HX711:",  value)

    # # Test Servo
    # servo = rpi_hardware.get_channels_by_name("Servo")
    # assert isinstance(servo, Module_RPI_ServoMotor)  # Check if it's an instance of ServoMotor

    # servo.write(percentage=0)
    # time.sleep(1)
    # servo.write(percentage=50)
    # time.sleep(1)
    # servo.write(percentage=100)
    # time.sleep(1)

    # Hardware: Digilent MCC118
    mcc118_hardware = Hardware_DigilentMCC118(name="MCC118", hat_address=0)
    mcc118_hardware.initialize()

    mcc118_input_channels = [
        Channel_MCC118_VoltageChannel(
            handle=mcc118_hardware._handle,
            name="MCC118_0",
            channel=0,
            unit="V",
            model=LinearModel(offset=0, gain=1),
        ),
        Channel_MCC118_VoltageChannel(
            handle=mcc118_hardware._handle,
            name="MCC118_1",
            channel=1,
            unit="V",
            model=KTYxModel(r0=0.01, alpha=0.0001, t0=25.0),
        ),
        # Add more channels here if needed
    ]

    mcc118_hardware.add_channels(mcc118_input_channels)

    # Hardware: Multihardware
    multi_hardware = MultiHardware(name="MeasurementSystem")
    multi_hardware.add_hardware(rpi_hardware)
    multi_hardware.add_hardware(mcc118_hardware)

    # # Example 1: Standard Loop to read all channels
    # for channel in multi_hardware.get_channels():
    #     if not isinstance(channel, InputChannel):
    #         continue

    #     for i in range(3) :
    #         val = channel.read()
    #         print("Channel", channel.name, "Value: ", val, channel.unit)
    #     print("--")

    # multi_hardware.close()
    # sys.exit(0)

    print("-----")

    # Example 2: Threaded Loop to read all channels

    t_start = time.time_ns()

    class _ChannelReaderThread(threading.Thread):
        def __init__(self, channel: Union[InputChannel, InputModule], sample_rate):
            super().__init__()
            self.name = "Reader-" + channel.name
            self.channel = channel
            self.sample_rate = sample_rate
            self._running = True

        def run(self):
            while self._running:
                data = self.channel.read()

                if data.get_count() > 0:
                    value, t_value = data.get_last()
                else:
                    continue

                t_rel = (t_value - t_start) * 10**-9  # convert to seconds

                print(
                    f"Time: {t_rel:10.7f} - Channel: {self.channel.name:<20}  Value: {value:12.3f} {self.channel.unit}"
                )
                time.sleep(self.sample_rate)

        def stop(self):
            self._running = False

    sample_rates = {
        "RPI_GPIO_18": 1,
        "RPI_GPIO_23": 0.5,
        "InternalTemperature": 2,
        "MCC118_0": 1,
        "MCC118_1": 1,
        "HX711": 0.5,
    }

    readers = []
    for channel in multi_hardware.get_channels():
        if not isinstance(channel, (InputChannel, InputModule)):
            continue

        reader = _ChannelReaderThread(channel=channel, sample_rate=sample_rates[channel.name])
        reader.start()
        readers.append(reader)

    # Wait some time
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass

    # close the readers
    for reader in readers:
        assert isinstance(reader, _ChannelReaderThread)  # for code completion
        reader.stop()
    for reader in readers:
        assert isinstance(reader, _ChannelReaderThread)  # for code completion
        reader.join(timeout=1)

    multi_hardware.close()

    print("done")
