from __future__ import annotations

import time

import lgpio

# Documentation
# https://abyz.me.uk/lg/py_lgpio.html


def main():
    rpi_handle = lgpio.gpiochip_open(4)  # Open gpiochip4 --> GPIOs
    pin = 17  # Use BCM pin numbering
    lgpio.gpio_claim_alert(handle=rpi_handle, gpio=pin, eFlags=lgpio.RISING_EDGE)

    def cbf(chip, gpio, level, tick):
        print(f"chip={chip} gpio={gpio} level={level} time={tick / 1e9:.09f}")

    _ = lgpio.gpio_set_debounce_micros(
        handle=rpi_handle, gpio=pin, debounce_micros=1000
    )  # Optional: debounce time in microseconds
    cb1 = lgpio.callback(handle=rpi_handle, gpio=pin, edge=lgpio.BOTH_EDGES, func=cbf)

    try:
        while True:
            print("tally", cb1.tally())
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        # cb1.cancel()
        lgpio.gpiochip_close(rpi_handle)


if __name__ == "__main__":
    main()
