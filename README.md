# Measurement-System

[![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10-blue)](https://www.python.org/)
[![Issues](https://img.shields.io/badge/Issues-orange)](https://github.com/paaalm07/RPI_Measurement_System/issues)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)
[![Sphinx](https://img.shields.io/badge/docs-blue?label=sphinx&logo=sphinx&logoColor=white)](https://github.com/sphinx-doc/sphinx)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/paaalm07/RPI_Measurement_System/blob/master/LICENSE)

This is a template Python project with Sphinx documentation.
Measurement-System based on RaspberryPi 5 hardware.
- Measurements: DAQ-Hats (Digilent MCC Series) and RPi IOs
- Visualization: [ComVisu](http://comvisu.de/)

## Pre-Requisites
- Hardware
    - RaspberryPi 5
    - Digilent MCC HATs
        - currently supported HATs: MCC118, MCC134
    - HX711 weight scales input module
- Software
    - Installed the shared library and tools for MCC DAQ Hat
        - Summary
            ```bash
            cd ~
            git clone https://github.com/mccdaq/daqhats.git
            cd ~/daqhats
            sudo ./install.sh
            ```  
        - For more details, checkout https://mccdaq.github.io/daqhats/install.html
- Toolchain
    - Install [Hatch](https://hatch.pypa.io/) as python manager:
        - Python/Pip already there: ```pip install hatch --break-system-packages```
        - Set global hatch config: ```hatch config set dirs.env.virtual .hatch```
    - Notes
        - On Windows system, the [lgpio](https://abyz.me.uk/lg/py_lgpio.html) library is not installed. Building docs and other features not available.

## Getting Started

Use [Hatch](https://hatch.pypa.io/) to...

- ...install environment: ``` hatch env create```
- ...run pre-commit: ```hatch run fix```
- ...create docs: ```hatch run docs```
- ...build: ```hatch run dev```

Check [pyproject.toml](pyproject.toml) for more scripts in section [tool.hatch.envs.default.scripts]

Use any hatch command to sync dependencies.
