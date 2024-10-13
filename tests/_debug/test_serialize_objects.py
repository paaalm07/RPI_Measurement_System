from __future__ import annotations

import importlib
import json


class Serializable:
    def to_dict(self):
        if hasattr(self, "__dict__"):
            return {
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
    def from_dict(cls, data):
        module_name = data["module"]
        class_name = data["class"]
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)

        instance = cls.__new__(cls)
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
                setattr(instance, key, value)

        if hasattr(instance, "initialize"):
            instance.initialize()

        return instance


class X(Serializable):
    def __init__(self, x=None):
        self.x = x
        self.initialize()

    def initialize(self):
        self._test = "TEST"

    @property
    def test(self):
        return self._test


class A(Serializable):
    def __init__(self):
        self.name = "A"
        self.a = 1


class B:
    def __init__(self):
        self.name = "B"
        self.b = 2


class C(A, B):
    def __init__(self):
        A.__init__(self)
        B.__init__(self)  # overwrite name from class A
        self.name = "C"  # overwrite name from class B
        self.initialize()

    def initialize(self):
        self.x_list = [X(5), X(10)]


c = C()
_dict = c.to_dict()
print("to_dict:  ", _dict)


# Define custom serializer
def custom_serializer(obj):
    if isinstance(obj, Serializable):
        return obj.to_dict()
    return TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


# Save to JSON
with open("test.json", "w") as f:
    json.dump(_dict, f, indent=4, default=custom_serializer)


# Define custom deserializer
def custom_deserializer(data):
    if isinstance(data, dict) and "class" in data and "module" in data:
        return Serializable.from_dict(data)
    if isinstance(data, dict):
        return {key: custom_deserializer(value) for key, value in data.items()}
    if isinstance(data, list):
        return [custom_deserializer(item) for item in data]
    return data


# Load from JSON
def load_from_json(file_path):
    with open(file_path) as f:
        data = json.load(f)
    return custom_deserializer(data)


c_restored = load_from_json("test.json")
assert isinstance(c_restored, C)
print(
    "from_json:",
    c_restored.a,
    c_restored.b,
    c_restored.x_list[0].x,
    c_restored.x_list[1].x,
    c_restored.x_list[1].test,
)
