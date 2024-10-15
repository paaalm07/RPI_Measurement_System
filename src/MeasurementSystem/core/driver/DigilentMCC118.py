from __future__ import annotations

import os
import sys

from daqhats import OptionFlags, mcc118

from MeasurementSystem.core.driver.BaseClasses import ChannelProperties, Hardware, InputChannel
from MeasurementSystem.core.driver.Config import Config
from MeasurementSystem.core.driver.Data import Data
from MeasurementSystem.core.driver.Models import LinearModel, Model


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
