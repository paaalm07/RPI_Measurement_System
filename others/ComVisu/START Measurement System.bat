@echo off
rem for /f "tokens=2 delims=[]" %%f in ('ping -4 -n 1 %COMPUTERNAME%') do set caller_ip=%%f

@echo off
setlocal enabledelayedexpansion
set my_ip=

for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /C:"IPv4 Address"') do (
    set ip_address=%%A
    set ip_address=!ip_address:~1!
    
    rem Once an IP address is found, store it and exit the loop
    if defined ip_address (
        set my_ip=!ip_address!
        goto :found
    )
)

:found
if defined my_ip (
    echo MyIP: %my_ip%
    ssh -t heinz@raspberrypi.local "bash -ic 'cd ~/Documents/RPI_Measurement_System && hatch env prune && hatch env create && hatch run measurement-system %my_ip%:8008'"
) else (
    echo No active IPv4 address found.
)

pause