@echo off
for /f "tokens=2 delims=[]" %%f in ('ping -4 -n 1 %COMPUTERNAME%') do set caller_ip=%%f
echo Caller IP: %caller_ip%
ssh heinz@raspberrypi.local "/home/heinz/Documents/PROJECT/python/.venv/bin/python -u /home/heinz/Documents/PROJECT/python/measurement_server.py %caller_ip%:8008"
pause