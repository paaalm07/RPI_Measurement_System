from __future__ import annotations

import time

import lgpio

# Constants
GPIO_CHIP = 4  # The correct GPIO chip number for GPIO pins
GPIO_PIN = 18  # Replace with your GPIO pin number
MONITOR_DURATION = 0.1  # Duration to monitor the pin in seconds
DEBOUNCE_MICROS = 5  # Debounce time in microseconds


def main():
    # Initialize GPIO
    rpi_handle = lgpio.gpiochip_open(GPIO_CHIP)

    # Claim the GPIO pin
    _ = lgpio.gpio_claim_alert(handle=rpi_handle, gpio=GPIO_PIN, eFlags=lgpio.BOTH_EDGES)

    # Setup callback for rising edges
    _ = lgpio.gpio_set_debounce_micros(handle=rpi_handle, gpio=GPIO_PIN, debounce_micros=DEBOUNCE_MICROS)
    cb1 = lgpio.callback(handle=rpi_handle, gpio=GPIO_PIN, edge=lgpio.BOTH_EDGES, func=None)

    try:
        while True:
            # Record the start time
            t0 = time.time()

            # Reset tally to start fresh counting
            cb1.reset_tally()

            # Monitor for the specified duration
            time.sleep(MONITOR_DURATION)

            # Get the number of edges counted
            edge_count = cb1.tally()

            # Record the end time
            t1 = time.time()

            # Calculate the time interval
            delta_t = t1 - t0

            # Calculate the frequency in Hz
            frequency = edge_count / delta_t  # divide by 2 to account for both edges

            print(f"Edge count: {edge_count:8d}, Frequency: {frequency:10.2f} Hz")

    except KeyboardInterrupt:
        print("Exiting...")

    finally:
        # Clean up
        lgpio.gpiochip_close(rpi_handle)


if __name__ == "__main__":
    main()
