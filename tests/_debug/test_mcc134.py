# MCC 118 example program
# Read and display analog input values
#
from __future__ import annotations

import sys
import time

from daqhats import HatIDs, TcTypes, hat_list, mcc134

# get hat list of MCC daqhat boards
board_list = hat_list(filter_by_id=HatIDs.ANY)
if not board_list:
    print("No boards found")
    sys.exit()

print(board_list)


t1 = time.time_ns()

for i in range(100):
    # Read and display every channel
    for entry in board_list:
        if entry.id == HatIDs.MCC_134:
            print(f"Board {entry.address}: MCC 134")
            board = mcc134(entry.address)
            for channel in range(board.info().NUM_AI_CHANNELS):
                board.tc_type_write(channel, TcTypes.TYPE_K)
                value = board.t_in_read(channel)
                print(f"Ch {channel}: {value:.3f}")

t2 = time.time_ns()

print((t2 - t1) / 10e9)
