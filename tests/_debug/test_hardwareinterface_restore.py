from __future__ import annotations

import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from measurement_server import HardwareInterface

hwi_restored = HardwareInterface.from_json(
    hardware_file="hardware.json",
    channels_file="channels.json",
    modules_file="modules.json",
)

# # plausi check
# results = hwi_restored.getMeasurements()
# print(results)

hwi_restored.close()

# expected like: ([0.0, 4.720000000000001, 25.0, 1.0091948818761076, 2.0229160804534763, 3.028913161912432, 4.057460751286486], 1722080727.499529)
