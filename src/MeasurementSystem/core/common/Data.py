from __future__ import annotations

import os
import re
import sys
import time
from typing import Any, Dict, Generator, List, NewType, Tuple

Time_ns = NewType("Time_ns", int)


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
