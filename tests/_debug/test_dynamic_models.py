from __future__ import annotations

import math
import re
from typing import List


# Base Model class
class Model:
    @staticmethod
    def parse_model_list(model_list_str: str, model_registry: dict) -> List[Model]:
        """Parse and instantiate models from a string representation of a list."""
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
        raise NotImplementedError("Subclasses must implement this method")


# Metaclass to handle automatic registration
class ModelMeta(type):
    model_registry = {}

    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if name != "Model":
            ModelMeta.model_registry[name] = cls


class StackedModel(Model, metaclass=ModelMeta):
    def __init__(self, models: List[Model]):
        self.models = models  # models are stored like a stack: 1st defined, 1st applied --> be aware of order!

    def apply(self, value: float) -> float:
        for model in self.models:
            value = model.apply(value)
        return value


# Model implementations
class LinearModel(Model, metaclass=ModelMeta):
    def __init__(self, offset: float, gain: float):
        self.name = "LinearModel"
        self.offset = offset
        self.gain = gain

    def apply(self, value: float) -> float:
        return value * self.gain + self.offset


class NTCModel(Model, metaclass=ModelMeta):
    def __init__(self, r0: float, beta: float, t0: float = 25):
        self.name = "NTCModel"
        self.r0 = r0
        self.beta = beta
        self.t0 = t0 + 273.15  # convert T0 from Celsius to Kelvin

    def apply(self, resistance: float) -> float:
        temperature = 1 / (1 / self.t0 + 1 / self.beta * math.log(resistance / self.r0))
        return temperature - 273.15  # convert temperature from Kelvin to Celsius


class PTxModel(Model, metaclass=ModelMeta):
    def __init__(self, r0: float):
        self.name = "PTxModel"
        self.r0 = r0
        self.alpha = 3.85e-3

    def apply(self, resistance: float) -> float:
        return (resistance - self.r0) / (self.r0 * self.alpha)


class Channel:
    def __init__(self, name: str, value: float, model: Model):
        self.name = name
        self.value = value
        self.model = model

    def read(self):
        return self.model.apply(self.value)

    def set_model_from_str(self, model_str: str):
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


if __name__ == "__main__":
    # Usage example
    channel = Channel("test", value=300, model=LinearModel(0, 1))
    print("Initial read:", channel.read())

    # Change the model using a string with a StackedModel containing a single model
    new_model_str = "StackedModel([LinearModel(100, gain=1), LinearModel(offset=0, gain=10)])"
    channel.set_model_from_str(new_model_str)
    print(f"set {new_model_str}:", channel.read())

    # Change the model using a string with mixed arguments
    new_model_str = "LinearModel(10, gain=5)"
    channel.set_model_from_str(new_model_str)
    print(f"set {new_model_str}:", channel.read())

    # Change the model using a string with key-value pairs
    new_model_str = "NTCModel(r0=10000, beta=3456, t0=25)"
    channel.set_model_from_str(new_model_str)
    print(f"set {new_model_str}:", channel.read())

    # Change the model using a string with positional arguments
    new_model_str = "PTxModel(100)"
    channel.set_model_from_str(new_model_str)
    print(f"set {new_model_str}:", channel.read())

    # Change the model using a string with positional arguments
    new_model_str = "PTxModel(1000)"
    channel.set_model_from_str(new_model_str)
    print(f"set {new_model_str}:", channel.read())
