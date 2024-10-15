from __future__ import annotations

import math
import os
import re
import sys
from typing import List

from MeasurementSystem.core.common.Utils import Serializable


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
