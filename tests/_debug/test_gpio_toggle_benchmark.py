from __future__ import annotations

import time

import lgpio

OUT = 17
LOOPS = 100000

h = lgpio.gpiochip_open(4)

lgpio.gpio_claim_output(h, OUT)

t0 = time.time()

for i in range(LOOPS):
    lgpio.gpio_write(h, OUT, 0)
    lgpio.gpio_write(h, OUT, 1)

t1 = time.time()

lgpio.gpiochip_close(h)

print(f"{LOOPS / (t1 - t0):.0f} toggles per second")
