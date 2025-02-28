Prerequisites
#############

Hardware
********

- RaspberryPi 5
- Digilent MCC HATs
    - currently supported HATs: *MCC118*, *MCC134*
- *HX711* weight scales input module
- DIGPIO Screw Terminal Breakut Board HAT
- USB Stick (or SD-Card + reader)

Connections
===========

to be defined


Software
********


Repository
==========

Clone the git repository into ``~/Documents/RPI_Measurement_System`` on the RaspberryPi.
**This path is mandatory**, otherwise the ``START Measurement System.bat`` won't work (or has to be adapted).

    .. code-block:: bash

        cd ~/Documents
        git clone https://github.com/paaalm07/RPI_Measurement_System.git


Clone this repository as well on the Windows machine. Where is not important, just to have the files, for example here:

    .. code-block:: bash

        cd %USERPROFILE%\Desktop
        git clone https://github.com/paaalm07/RPI_Measurement_System.git


Daqhats Shared Library
======================

Install the shared library and tools for MCC DAQ Hat on the RaspberryPi.

    .. code-block:: bash

        cd ~
        git clone https://github.com/mccdaq/daqhats.git
        cd ~/daqhats
        sudo ./install.sh

For more details, checkout https://mccdaq.github.io/daqhats/install.html


Hatch
=====

- Install `Hatch <https://hatch.pypa.io/>`_ as python manager on the RaspberryPi:
    - Python/Pip already there: ``pip install hatch --break-system-packages``
    - Set global hatch config: ``hatch config set dirs.env.virtual .hatch``

    Notes:

    - On Windows system, the `lgpio <https://abyz.me.uk/lg/py_lgpio.html>`_ library is not installed. Building docs and other features not available.

- Hatch will manage the virtual environment and dependencies for the project based on the ``pyproject.toml`` file.

Use Hatch to:

- ...create a new virtual environment: ``hatch env create``
- ...run pre-commit hooks: ``hatch run fix``
- ...create docs: ``hatch run docs``
- ...run MeasurementSystem: ``hatch run measurement-system``

Check the `[tool.hatch.envs.default.scripts]` section in the `pyproject.toml` file for more scripts
