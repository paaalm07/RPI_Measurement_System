from __future__ import annotations

import os
import re
import sys
import threading
import time
from typing import NewType

import lgpio

from MeasurementSystem.core.common.BaseClasses import (
    Channel,
    ChannelManager,
    ChannelProperties,
    Hardware,
    InputChannel,
    InputModule,
    Module,
    MultiChannel,
    OutputChannel,
    OutputModule,
)
from MeasurementSystem.core.common.Config import Config
from MeasurementSystem.core.common.Data import Data
from MeasurementSystem.core.common.Models import (
    KTYxModel,
    LinearModel,
    Model,
    ModelMeta,
    NTCModel,
    PTxModel,
    StackedModel,
)

GPIOHandle = NewType("GPIOHandle", int)


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
