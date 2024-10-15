from __future__ import annotations

import os
import sys

from MeasurementSystem.core.common.Utils import Serializable


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
