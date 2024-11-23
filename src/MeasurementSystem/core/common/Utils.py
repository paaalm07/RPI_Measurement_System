from __future__ import annotations

import importlib
import os
import platform
import queue
import sys
from typing import Any, Dict, Tuple

import psutil


class OrderedPriorityQueue(queue.PriorityQueue):
    """
    A priority queue that preserves the order of elements with the same priority.

    :class:`OrderedPriorityQueue` extends the standard :class:`PriorityQueue` to ensure that elements with the same priority are
    retrieved in the order they were inserted. This is achieved by using a tuple as the priority,
    where the first element is the actual priority and the second element is a unique counter.


    :param name: The name of the queue.
    :type name: str

    :return: OrderedPriorityQueue object
    :rtype: OrderedPriorityQueue
    """

    def __init__(self, name):
        super().__init__()
        self.name = name
        self._sequence_number = 0

    def put(
        self,
        queue_element: Any,
        priority: float = 5,
        block: bool = True,
        timeout: float = None,
    ) -> None:
        """
        Put an element into the queue.

        This method puts an element into the queue with a given priority.
        The element is a tuple containing the priority, a sequence number and the queue element.
        The sequence number is used to ensure that elements with the same priority are processed
        in the order they were added to the queue.

        :param queue_element: The element to be added to the queue.
        :type queue_element: Any
        :param priority: The priority of the element. Elements with higher priority are processed first. Defaults to 5.
        :type priority: float
        :param block: If True, block until a free slot is available, otherwise raise the QueueFull exception. Defaults to True.
        :type block: bool
        :param timeout: The maximum time to wait for a free slot in the queue. If None, wait forever. Defaults to None.
        :type timeout: float
        :return: None
        :rtype: None
        """

        super().put(
            (priority, self._sequence_number, queue_element),
            block=block,
            timeout=timeout,
        )
        self._sequence_number += 1

    def get(self, block: bool = True, timeout: float = None) -> Tuple[Any, float]:
        """
        Get an element from the queue.

        This method gets an element from the queue.
        The element is a tuple containing the queue element and the priority.

        :param block: If True, block until an element is available, otherwise raise the QueueEmpty exception. Defaults to True.
        :type block: bool
        :param timeout: The maximum time to wait for an element. If None, wait forever. Defaults to None.
        :type timeout: float
        :return: Queue element and its priority.
        :rtype: Tuple[Any, float]
        """

        priority, sequence_number, queue_element = super().get(block=block, timeout=timeout)
        return queue_element, priority


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


class USBUtils:
    @staticmethod
    def find_all_usb_drives(common_mount_points=None, common_filesystems=None) -> list:
        """
        Finds all USB drives attached to the system, excluding system drives.

        Automatically adapts to the current operating system. On Linux, it checks
        for USB drives mounted under paths like `/media/` or `/mnt/`. If the
        filesystem doesn't match the expected types, an error will be raised.

        :param common_mount_points: A list of base paths or prefixes for mount points. Defaults to platform-specific values.
        :type common_mount_points: Optional[List[str]]
        :param common_filesystems: A set of filesystem types to look for. Defaults to platform-specific values.
        :type common_filesystems: Optional[Set[str]]

        :return: A list of paths where USB drives are mounted.
        :rtype: List[str]

        :raises ValueError: If the filesystem of a USB drive doesn't match the expected ones.
        """

        # Set default values based on the platform
        if common_mount_points is None:
            if platform.system() == "Windows":
                # Windows: All drive letters are potential mount points, excluding C:\
                # common_mount_points = [f"{chr(d)}:\\" for d in range(65, 91) if chr(d) != 'C']  # Exclude C:\
                raise NotImplementedError("Windows is not supported yet")
            # Linux/Unix
            common_mount_points = ["/media/", "/mnt/"]

        if common_filesystems is None:
            if platform.system() == "Windows":
                # Common USB filesystems on Windows
                # common_filesystems = {'FAT32', 'NTFS', 'exFAT'}
                raise NotImplementedError("Windows is not supported yet")
            # Common USB filesystems on Linux
            common_filesystems = {"vfat", "ntfs", "ntfs3"}

        usb_drives = []
        for partition in psutil.disk_partitions():
            # Check if the mount point matches any common path and exclude system drives
            if any(partition.mountpoint.startswith(path) for path in common_mount_points):
                # On Linux, exclude root partition and internal drives
                if partition.device == "/":
                    continue
                # Include only specified filesystems
                if partition.fstype:
                    if partition.fstype not in common_filesystems:
                        raise ValueError(f"Unsupported filesystem type: {partition.fstype} for {partition.device}")
                    usb_drives.append(partition.mountpoint)

        return usb_drives


# TEST
if __name__ == "__main__":
    q = OrderedPriorityQueue("test")

    # fill the queue
    for i in range(10):
        q.put(i)

    # read the queue
    while True:
        try:
            priority, queue_element = q.get(timeout=1)
            print(f"Priority: {priority}, QueueElement: {queue_element}")
        except queue.Empty:
            break

    print("done")

    print("----")

    usb_drives = USBUtils.find_all_usb_drives()
    print(usb_drives)
