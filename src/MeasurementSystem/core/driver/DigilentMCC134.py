from __future__ import annotations

import os
import sys

from daqhats import OptionFlags, TcTypes, mcc134

from MeasurementSystem.core.driver.BaseClasses import ChannelProperties, Hardware, InputChannel
from MeasurementSystem.core.driver.Config import Config
from MeasurementSystem.core.driver.Data import Data
from MeasurementSystem.core.driver.Models import LinearModel, Model


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
