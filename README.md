# Pure Python Jeelink LaCrosse Library

[![PyPI version](https://badge.fury.io/py/pylacrosse.svg)](https://badge.fury.io/py/pylacrosse)
[![Python versions](https://img.shields.io/pypi/pyversions/pylacrosse.svg)](https://badge.fury.io/py/pylacrosse)

## Requirements

This library works with the [Jeelink](https://www.digitalsmarties.net/products/jeelink)
USB RF adapter and the Arduino
[sketch](https://svn.fhem.de/trac/browser/trunk/fhem/contrib/arduino/36_LaCrosse-LaCrosseITPlusReader.zip)
hosted on the [FHEM](https://wiki.fhem.de/wiki/JeeLink) website.

## Tested Devices

* Technoline TX 29IT
* Technoline TX 29DTH-IT

## Command Line Tool

```shell
# pylacrosse -h
usage: LaCrosse sensor CLI tool. [-h] [-v] [-d DEVICE] [-f FREQUENCY_RFM1]
                                 [-F FREQUENCY_RFM2] [-t TOGGLE_INTERVAL_RFM1]
                                 [-T TOGGLE_INTERVAL_RFM2]
                                 [-m TOGGLE_MASK_RFM1] [-M TOGGLE_MASK_RFM2]
                                 [-r DATARATE_RFM1] [-R DATARATE_RFM2]
                                 {scan,info,led} ...

optional arguments:
  -h, --help            show this help message and exit
  -v                    be more verbose
  -d DEVICE, --device DEVICE
                        set local device e.g. '/dev/ttyUSB0' or
                        set remote device e.g. 'rfc2217://[IP]:[PORT]'
                        default: '/dev/ttyUSB0'
  -f FREQUENCY_RFM1     set the frequency for RFM1
  -F FREQUENCY_RFM2     set the frequency for RFM2
  -t TOGGLE_INTERVAL_RFM1
                        set the toggle interval for RFM1
  -T TOGGLE_INTERVAL_RFM2
                        set the toggle interval for RFM2
  -m TOGGLE_MASK_RFM1   set the toggle mask for RFM1
  -M TOGGLE_MASK_RFM2   set the toggle mask for RFM2
  -r DATARATE_RFM1      set the datarate for RFM1
  -R DATARATE_RFM2      set the datarate for RFM2

Commands:
  {scan,info,led}
    scan                Show all received sensors
    info                Get configuration info
    led                 Set traffic LED state
```

Choose one command. Configuration options are applied before the command runs.
For example, set the datarate and then show the device configuration:

```shell
pylacrosse -v -d /dev/ttyUSB0 -r 2 info
```

Opening the connection can reset the adapter. The library opens the serial port
and flushes its input and output buffers, but does not wait for a firmware report
before sending configuration commands.

The LaCrosse sensor generates the ID every time the battery is changed.

Use the cli tool `pylacrosse` to find your device:

```shell
# pylacrosse -d /dev/ttyUSB0 scan
id=40 t=16.000000 h=69 nbat=0 name=unknown
id=16 t=18.700000 h=60 nbat=0 name=unknown
id=0 t=17.400000 h=65 nbat=0 name=unknown
```

You can generate a file with know devices at `~/.lacrosse/known_sensors.ini`

```ini
[0]
name = Kitchen
[16]
name = Livingroom
[40]
name = Bedroom
```

then the tool will print the defined names

```shell
# pylacrosse -d /dev/ttyUSB0 scan
id=40 t=16.000000 h=69 nbat=0 name=Bedroom
id=16 t=18.700000 h=60 nbat=0 name=Livingroom
id=0 t=17.400000 h=65 nbat=0 name=Kitchen
```

## Using remote serial port with ser2net

You can also use `ser2net` to connect to a remote JeeLink Adapter. This can be useful,
if you use a Docker container or if you can not attach a JeeLink adapter to your host
running `pylacrosse`. On your remote device install `ser2net` and add the following
line to your `ser2net.conf` file:

```text
20001:telnet:0:/dev/ttyUSB0:57600 remctl banner
```

Restart the `ser2net` daemon and connect to your remote host using `pylacrosse`
command line tool:

```shell
# pylacrosse -d rfc2217://[REMOTE_IP]]:20001 scan
id=40 t=16.000000 h=69 nbat=0 name=Bedroom
id=16 t=18.700000 h=60 nbat=0 name=Livingroom
id=0 t=17.400000 h=65 nbat=0 name=Kitchen
```

## Contributing

Developer, publishing, and maintenance instructions are in the
[contributing guide](https://github.com/vipwolf/python-lacrosse/blob/develop/contributing.md).
