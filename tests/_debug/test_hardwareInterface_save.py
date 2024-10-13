from __future__ import annotations

import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from measurement_server import HardwareInterface

hwi = HardwareInterface(name="HardwareInterface")
hwi.initialize()

# # plausi check
# results = hwi.getMeasurements()
# print(results)

hwi.to_json()
hwi.close()


# restore test
hwi_restored = HardwareInterface.from_json(
    hardware_file="hardware.json",
    channels_file="channels.json",
    modules_file="modules.json",
)

# # plausi check
# results = hwi_restored.getMeasurements()
# print(results)

hwi_restored.close()
