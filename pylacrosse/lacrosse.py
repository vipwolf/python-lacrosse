# Copyright (c) 2017 Heiko Thiery
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
# USA

import logging
import re
import threading
from collections.abc import Callable
from typing import Any

import serial
from serial.rfc2217 import Serial as RFC2217Serial

_LOGGER = logging.getLogger(__name__)

"""
    Jeelink lacrosse firmware commands
    <n>a     set to 0 if the blue LED bothers
    <n>f     initial frequency in kHz (5 kHz steps, 860480 ... 879515)  (for RFM
    #1)
    <n>F     initial frequency in kHz (5 kHz steps, 860480 ... 879515)  (for RFM
    #2)
    <n>h     altituide above sea level
    <n>m     bits 1: 17.241 kbps, 2 : 9.579 kbps, 4 : 8.842 kbps (for RFM #1)
    <n>M     bits 1: 17.241 kbps, 2 : 9.579 kbps, 4 : 8.842 kbps (for RFM #2)
    <n>r     use one of the possible data rates (for RFM #1)
    <n>R     use one of the possible data rates (for RFM #2)
    <n>t     0=no toggle, else interval in seconds (for RFM #1)
    <n>T     0=no toggle, else interval in seconds (for RFM #2)
       v     show version
       <n>y     if 1 all received packets will be retransmitted  (Relay mode)
"""


class LaCrosse(object):
    sensors: dict[int, "LaCrosseSensor"] = {}
    _registry: dict[int, list[tuple[Callable[["LaCrosseSensor", Any], None], Any]]] = {}

    def __init__(self, port: str, baud: int, timeout: float = 2) -> None:
        """Initialize the Lacrosse device."""
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._serial: serial.Serial | RFC2217Serial = (
            SerialPortFactory().create_serial_port(port)
        )
        self._callback: Callable[["LaCrosseSensor", Any], None] | None = None
        self._callback_data: Any = None
        self._stopevent: threading.Event | None = None
        self._thread: threading.Thread | None = None

    def open(self) -> None:
        """Open the device."""
        self._serial.port = self._port
        self._serial.baudrate = self._baud
        self._serial.timeout = self._timeout
        self._serial.open()
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def close(self) -> None:
        """Close the device."""
        self._stop_worker()
        self._serial.close()

    def start_scan(self) -> None:
        """Start scan task in background."""
        self._start_worker()

    def _write_cmd(self, cmd: str) -> None:
        """Write a cmd."""
        self._serial.write(cmd.encode())

    @staticmethod
    def _parse_info(line: str) -> dict[str, str | None]:
        """
        The output can be:
        - [LaCrosseITPlusReader.10.1s (RFM12B f:0 r:17241)]
        - [LaCrosseITPlusReader.10.1s (RFM12B f:0 t:10~3)]
        """
        re_info = re.compile(
            r"\[(?P<name>\w+).(?P<ver>.*) "
            + r"\((?P<rfm1name>\w+) (\w+):(?P<rfm1freq>\d+) "
            + r"(?P<rfm1mode>.*)\)\]"
        )

        info = dict[str, str | None](
            [
                ("name", None),
                ("version", None),
                ("rfm1name", None),
                ("rfm1frequency", None),
                ("rfm1datarate", None),
                ("rfm1toggleinterval", None),
                ("rfm1togglemask", None),
            ]
        )
        match = re_info.match(line)
        if match:
            info["name"] = match.group("name")
            info["version"] = match.group("ver")
            info["rfm1name"] = match.group("rfm1name")
            info["rfm1frequency"] = match.group("rfm1freq")
            values = match.group("rfm1mode").split(":")
            if values[0] == "r":
                info["rfm1datarate"] = values[1]
            elif values[0] == "t":
                toggle = values[1].split("~")
                info["rfm1toggleinterval"] = toggle[0]
                info["rfm1togglemask"] = toggle[1]

        return info

    def get_info(self) -> dict[str, str | None]:
        """Get current configuration info from 'v' command."""
        re_info = re.compile(r"\[.*\]")

        self._write_cmd("v")
        while True:
            line = self._serial.readline()
            line = line.decode("utf-8")

            match = re_info.match(line)
            if match:
                return self._parse_info(line)

    def led_mode_state(self, state: bool) -> None:
        """Set the LED mode.

        The LED state can be True or False.
        """
        self._write_cmd("{}a".format(int(state)))

    def set_frequency(self, frequency: int | str, rfm: int = 1) -> None:
        """Set frequency in kHz.

        The frequency can be set in 5kHz steps.
        """
        cmds = {1: "f", 2: "F"}
        self._write_cmd("{}{}".format(frequency, cmds[rfm]))

    def set_datarate(self, rate: int | str, rfm: int = 1) -> None:
        """Set datarate (baudrate)."""
        cmds = {1: "r", 2: "R"}
        self._write_cmd("{}{}".format(rate, cmds[rfm]))

    def set_toggle_interval(self, interval: int | str, rfm: int = 1) -> None:
        """Set the toggle interval."""
        cmds = {1: "t", 2: "T"}
        self._write_cmd("{}{}".format(interval, cmds[rfm]))

    def set_toggle_mask(self, mode_mask: int | str, rfm: int = 1) -> None:
        """Set toggle baudrate mask.

        The baudrate mask values are:
          1: 17.241 kbps
          2 : 9.579 kbps
          4 : 8.842 kbps
        These values can be or'ed.
        """
        cmds = {1: "m", 2: "M"}
        self._write_cmd("{}{}".format(mode_mask, cmds[rfm]))

    def _start_worker(self) -> None:
        if self._thread is not None:
            return
        self._stopevent = threading.Event()
        self._thread = threading.Thread(target=self._refresh, args=())
        self._thread.daemon = True
        self._thread.start()

    def _stop_worker(self) -> None:
        if self._stopevent is not None:
            self._stopevent.set()
        if self._thread is not None:
            self._thread.join()

    def _refresh(self) -> None:
        """Background refreshing thread."""

        stop_event = self._stopevent
        if stop_event is None:
            return

        while not stop_event.is_set():
            line = self._serial.readline().decode("utf-8")

            if LaCrosseSensor.re_reading.match(line):
                sensor = LaCrosseSensor(line)
                self.sensors[sensor.sensorid] = sensor

                if self._callback:
                    self._callback(sensor, self._callback_data)

                if sensor.sensorid in self._registry:
                    for cbs in self._registry[sensor.sensorid]:
                        cbs[0](sensor, cbs[1])

    def register_callback(
        self,
        sensorid: int,
        callback: Callable[["LaCrosseSensor", Any], None],
        user_data: Any = None,
    ) -> None:
        """Register a callback for the specified sensor id."""
        if sensorid not in self._registry:
            self._registry[sensorid] = list()
        self._registry[sensorid].append((callback, user_data))

    def register_all(
        self,
        callback: Callable[["LaCrosseSensor", Any], None],
        user_data: Any = None,
    ) -> None:
        """Register a callback for all sensors."""
        self._callback = callback
        self._callback_data = user_data


class LaCrosseSensor(object):
    """The LaCrosse Sensor class."""

    # OK 9 248 1 4 150 106
    re_reading: re.Pattern[str] = re.compile(r"OK (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)")

    def __init__(self, line: str | None = None) -> None:
        if line:
            self._parse(line)

    def _parse(self, line: str) -> None:
        match = self.re_reading.match(line)
        if match:
            data = [int(c) for c in match.group().split()[1:]]
            self.sensorid: int = data[1]
            self.sensortype: int = data[2] & 0x7F
            self.new_battery: bool = True if data[2] & 0x80 else False
            self.temperature: float = float(data[3] * 256 + data[4] - 1000) / 10
            self.humidity: int = data[5] & 0x7F
            self.low_battery: bool = True if data[5] & 0x80 else False

    def __repr__(self) -> str:
        return "id=%d t=%f h=%d nbat=%d" % (
            self.sensorid,
            self.temperature,
            self.humidity,
            self.new_battery,
        )


class SerialPortFactory(object):
    def create_serial_port(self, port: str) -> serial.Serial | RFC2217Serial:
        if port.startswith("rfc2217://"):
            return RFC2217Serial()
        else:
            return serial.Serial()
