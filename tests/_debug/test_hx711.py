from __future__ import annotations

import time
from typing import NewType

import lgpio
import plotext as plt

GPIOHandle = NewType("GPIOHandle", int)


# Define GPIO pins
data_pin = 5
clock_pin = 6


def init() -> GPIOHandle:
    h = lgpio.gpiochip_open(4)

    lgpio.gpio_claim_input(handle=h, gpio=data_pin)
    lgpio.gpio_claim_output(handle=h, gpio=clock_pin, level=1)

    return h


# helper functions
def clock_cycle(h: GPIOHandle) -> None:
    lgpio.gpio_write(h, clock_pin, 1)
    lgpio.gpio_write(h, clock_pin, 0)
    # Note: do not implement a delay!


def read_bit(h: GPIOHandle):
    return lgpio.gpio_read(h, data_pin)


def twos_complement_24bit_to_int(data: int) -> int:
    # Mask to get the lower 24 bits
    mask = 0xFFFFFF
    # Apply the mask
    data &= mask
    # Check if the sign bit (24th bit) is set
    if data & 0x800000:  # 0x800000 is the 24th bit (2^23)
        # If the sign bit is set, calculate the negative value
        data -= 0x1000000  # Subtract 2^24
    return data


def percentage_representation_24bit(data: int) -> float:
    percentage = (data / (2**23)) * 100
    return percentage


def read_data(h: GPIOHandle) -> int:
    wait_for_data_ready(h)

    data = 0
    for i in range(24):
        clock_cycle(h)
        data = (data << 1) | read_bit(h)

    # addition cycles for settings of next conversion
    clock_cycle(h)  # 1x channel A gain 128
    # clock_cycle(h)  # 2x channel B gain 32
    # clock_cycle(h)  # 3x channel A gain 64

    return twos_complement_24bit_to_int(data)


# wakeup HX711
def wakeup(h: GPIOHandle):
    lgpio.gpio_write(h, clock_pin, 0)


# go to power down mode
def power_down(h: GPIOHandle):
    lgpio.gpio_write(h, clock_pin, 1)
    time.sleep(0.1)  # wait for 60us to go to power down mode, 0.1 to be sure


# wait for HX711 to be ready
def wait_for_data_ready(h: GPIOHandle):
    while lgpio.gpio_read(h, data_pin) != 0:
        time.sleep(1e-6)


# tara - 10 samples average
def tara(h: GPIOHandle) -> int:
    data = []
    for _ in range(10):
        data.append(read_data(h))
    tara = sum(data) / len(data)

    return int(tara)


#####################
# Test HX711

x = []
y = []

plt.clf()
plt.title("Dynamic Line Chart")
plt.xlabel("X Axis")
plt.ylabel("Y Axis")

try:
    h = init()
    wakeup(h)

    tara = tara(h)

    while True:
        value = read_data(h)

        value = value - tara
        percentage = percentage_representation_24bit(value)
        print(f"0b{value:024b} = {percentage:7.1f}% = {value}")

        x.append(len(x) + 1)
        y.append(value)

        display_samples = 150

        x_plot = x[-display_samples:]
        y_plot = y[-display_samples:]

        plt.scatter(x_plot, y_plot)
        if len(x_plot) > 1:
            x_min = min(x_plot)
            x_max = max(x_plot)

            y_adder = (max(y_plot) - min(y_plot)) * 0.2  # add 20% to the y-axis range
            y_min = min(y_plot) - y_adder
            y_max = max(y_plot) + y_adder

            plt.xlim(x_min, x_max)
            plt.ylim(y_min, y_max)
        plt.show()
        plt.grid(True, True)

except KeyboardInterrupt:
    pass

finally:
    power_down(h)

# cleanup
lgpio.gpiochip_close(h)
