from __future__ import annotations

import os
import sys

from MeasurementSystem.core.common.Ceda import Ceda

TMP_DIR = "/tmp/MeasurementSystem"


"""
1) load all csv files from TMP_DIR using ceda.load
2) comibe them in one single ceda data and save as csv in save_path
"""

save_path = os.path.join(TMP_DIR, "combined_data.csv")

new_ceda = Ceda()

for file in os.listdir(TMP_DIR):
    if file.endswith(".csv"):
        ceda_tmp = Ceda()
        ceda_tmp.load(os.path.join(TMP_DIR, file))

        new_ceda.merge(ceda_tmp)

new_ceda.save(filePath=save_path, overwrite=True, print_index=True, fill_nan_values=False, nan_replacement="=NA()")

print("done")
