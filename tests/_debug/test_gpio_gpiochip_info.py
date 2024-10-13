from __future__ import annotations

import lgpio as sbc

# like plain console command: gpioinfo

for i in range(10):
    try:
        h = sbc.gpiochip_open(i)
    except:
        continue

    ci = sbc.gpio_get_chip_info(h)

    print(f"lines={ci[1]} name={ci[2]} label={ci[3]}")

    for j in range(ci[1]):
        li = sbc.gpio_get_line_info(h, j)
        print(f"offset={li[1]} flags={li[2]} name={li[3]} user={li[4]}")

    print("----")
    sbc.gpiochip_close(h)
