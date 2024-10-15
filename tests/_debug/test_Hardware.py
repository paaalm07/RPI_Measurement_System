from __future__ import annotations

import os
import re
import threading
import time
from collections.abc import Generator
from typing import List, NewType, Union

from MeasurementSystem.core.driver.BaseClasses import (
    Channel,
    ChannelManager,
    ChannelProperties,
    Hardware,
    InputChannel,
    InputModule,
    Module,
    MultiChannel,
    MultiHardware,
    OutputChannel,
    OutputModule,
)
from MeasurementSystem.core.driver.Data import Data
from MeasurementSystem.core.driver.DigilentMCC118 import Channel_MCC118_VoltageChannel, Hardware_DigilentMCC118
from MeasurementSystem.core.driver.DigilentMCC134 import Channel_MCC134_ThermocoupleChannel, Hardware_DigilentMCC134
from MeasurementSystem.core.driver.Models import (
    KTYxModel,
    LinearModel,
    Model,
    ModelMeta,
    NTCModel,
    PTxModel,
    StackedModel,
)
from MeasurementSystem.core.driver.RaspberryPi import (
    Channel_RPI_BufferedDigitalInput,
    Channel_RPI_DigitalInput,
    Channel_RPI_DigitalOutput,
    Channel_RPI_FrequencyCounter,
    Channel_RPI_InternalTemperature,
    Hardware_RaspberryPi,
    Module_RPI_ServoMotor,
    Module_RPI_StepperMotor,
    Module_RPI_WeighScalesHX711,
)
from MeasurementSystem.core.Utils import Serializable

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

    # Hardware: Digilent MCC134
    mcc134_hardware = Hardware_DigilentMCC134(name="MCC134", hat_address=1)
    mcc134_hardware.initialize()

    mcc134_input_channels = [
        Channel_MCC134_ThermocoupleChannel(
            handle=mcc134_hardware._handle, name="MCC134_0", channel=0, unit="degC", model=LinearModel(offset=0, gain=1)
        ),
        Channel_MCC134_ThermocoupleChannel(
            handle=mcc134_hardware._handle, name="MCC134_3", channel=3, unit="degC", model=LinearModel(offset=0, gain=1)
        ),
        # Add more channels here if needed
    ]

    mcc134_hardware.add_channels(mcc134_input_channels)

    # Hardware: Multihardware
    multi_hardware = MultiHardware(name="MeasurementSystem")
    multi_hardware.add_hardware(rpi_hardware)
    multi_hardware.add_hardware(mcc118_hardware)
    multi_hardware.add_hardware(mcc134_hardware)

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
        "MCC134_0": 1,
        "MCC134_3": 1,
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
