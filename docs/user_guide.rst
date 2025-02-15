User Guide
##########


Preparation
***********

RaspberryPi
===========


Hardware
--------

1. Install Digilent HATs
2. Install DIO HAT
3. Insert USB Stick (or SD-Card reader)

Connections
^^^^^^^^^^^

...to be defined


Software
--------

- Clone the git repository into ``~/Documents/RPI_Measurement_System``. This path is mandatory, otherwise the ``START Measurement System.bat`` won't work (or has to be adapted).

- Hatch has to be installed, see pre-requisites in ``README.md``

- Shared library and tools for MCC DAQ Hat has to be installed, see pre-requisites in ``README.md``


Windows
===============

- Clone the git repository anywhere on the PC


Execute (Windows)
*****************

1. Start ``ComVisu.exe``
2. Press ``Verbinden``
3. Move to ``Startseite`` sheet
4. Start ``START Measurement System.bat``
5. Make sure a USB drive is plugged in
6. Press ``Mess-System: START`` and perform the measurement
7. Press ``Mess-System: STOP`` to stop and save the data to the USB drive


Troubleshooting
===============

- On any issue, always check command line logs either in ComViso GUI or in the Terminal where the batch file was started.
  It gives mostly useful hints for debugging later on.

- The measurement system uses a lockfile to prevent double execution.
  When a 2nd start is recognized, the active process will be killed and the lockfile will be removed.
  The system is then ready for a new attempt. This also happens on reboot.
