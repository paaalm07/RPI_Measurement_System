from __future__ import annotations

import time

import lgpio

pin_pwm = 24
pin_feedback = 25

handle = lgpio.gpiochip_open(4)  # Open gpiochip4 --> GPIOs

lgpio.gpio_claim_output(handle=handle, gpio=pin_pwm, level=0, lFlags=lgpio.SET_PULL_DOWN)

# same pin also as feedback is not possible --> use another pint with alert & callback
lgpio.gpio_claim_alert(handle=handle, gpio=pin_feedback, eFlags=lgpio.BOTH_EDGES)
cb = lgpio.callback(handle=handle, gpio=pin_feedback, edge=lgpio.RISING_EDGE, func=None)


# Generate PWM
lgpio.tx_pwm(
    handle=handle,
    gpio=pin_pwm,
    pwm_frequency=1,
    pwm_duty_cycle=50,
    pulse_offset=0,
    pulse_cycles=5,
)

# Check Feedback
out = 0
prev_count = cb.tally()
for i in range(100):
    t = time.time()
    count = cb.tally()

    # if count changes the value, the out variable should be toggled
    if count != prev_count:
        out = 1 - out
        prev_count = count
    print(t, out, sep=",")
    time.sleep(0.1)


# Release resources
cb.cancel()

lgpio.gpio_free(handle, pin_pwm)
lgpio.gpio_free(handle, pin_feedback)

lgpio.gpiochip_close(handle)

print("done")
