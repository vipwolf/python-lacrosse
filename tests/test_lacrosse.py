#!/usr/bin/env python

import time
from unittest.mock import MagicMock, patch

import pytest
import serial

from pylacrosse import LaCrosse, LaCrosseSensor
from pylacrosse.cli_tool import main


class TestCli:
    def test_requires_subcommand_before_opening_device(self):
        with patch("pylacrosse.cli_tool.pylacrosse.LaCrosse") as device:
            with pytest.raises(SystemExit):
                main(["-v", "-d", "/dev/ttyTEST", "-r", "9.579"])

        device.assert_not_called()

    @pytest.mark.parametrize("state", ["on", "off"])
    def test_configure_with_led_subcommand(self, state):
        with patch("pylacrosse.cli_tool.pylacrosse.LaCrosse") as device:
            main(["-r", "9.579", "led", state])

        device.return_value.set_datarate.assert_called_once_with("9.579", 1)
        device.return_value.led_mode_state.assert_called_once_with(state == "on")
        device.return_value.close.assert_called_once_with()


class TestLacrosse(object):
    @pytest.mark.parametrize("booting", [False, True])
    def test_open_waits_until_commands_can_be_accepted(self, booting):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        banner = b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 r:17241)]\r\n"
        ready = not booting
        startup = iter([b"", b"\n", banner])
        pending = []
        accepted = []

        def write(command):
            if ready:
                accepted.append(command)
                if command == b"v":
                    pending.append(banner)

        def readline():
            nonlocal ready
            if not ready:
                line = next(startup)
                if line == banner:
                    ready = True
                return line
            return pending.pop(0)

        serial_port.write.side_effect = write
        serial_port.readline.side_effect = readline
        serial_port.reset_input_buffer.side_effect = pending.clear

        with patch("pylacrosse.lacrosse.time.sleep"):
            lacrosse.open()
            lacrosse.set_toggle_mask(7)
            lacrosse.set_toggle_interval(30)

        assert accepted[-2:] == [b"7m", b"30t"]

    @pytest.mark.parametrize(
        "response",
        [
            b"",
            b"[unrecognized firmware]\r\n",
            b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30)]\r\n",
        ],
    )
    def test_open_warns_and_continues_if_readiness_is_unknown(self, caplog, response):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        serial_port.readline.return_value = response

        with patch("pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 6]):
            lacrosse.open()
            lacrosse.set_toggle_mask(7)

        serial_port.close.assert_not_called()
        serial_port.write.assert_called_with(b"7m")
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "initialization could not be confirmed" in caplog.text
        assert "may or may not" in caplog.text
        assert "10.1s or newer" in caplog.text
        assert "https://github.com/vipwolf/python-lacrosse/issues" in caplog.text

    def test_open_skips_malformed_report_until_ready(self, caplog):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        serial_port.readline.side_effect = [
            b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30)]\r\n",
            b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30~7)]\r\n",
        ]

        with patch("pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 1]):
            lacrosse.open()

        assert serial_port.readline.call_count == 2
        serial_port.close.assert_not_called()
        assert not caplog.records

    def test_open_closes_port_on_serial_error(self):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        serial_port.readline.side_effect = serial.SerialException("Disconnected")

        with pytest.raises(serial.SerialException, match="Disconnected"):
            lacrosse.open()

        serial_port.close.assert_called_once_with()

    def test_refresh(self):
        mock_readline = MagicMock()

        def side_effect_fct():
            if not hasattr(side_effect_fct, "counter"):
                side_effect_fct.counter = 0
            values = [
                b"OK 9 1 1 4 150 106",
                b"OK 9 2 1 4 150 106",
                b"OK 9 2 1 4 150 106",
            ]

            if side_effect_fct.counter >= len(values):
                value = b""
            else:
                value = values[side_effect_fct.counter]
            side_effect_fct.counter += 1
            return value

        mock_readline.side_effect = side_effect_fct

        mock_cb_1 = MagicMock(return_value=None)
        mock_cb_2 = MagicMock(return_value=None)

        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        lacrosse._serial.readline = mock_readline
        lacrosse.register_callback(1, mock_cb_1)
        lacrosse.register_callback(2, mock_cb_2)

        lacrosse._start_worker()
        time.sleep(0.01)
        lacrosse._stop_worker()

        assert mock_cb_1.call_count == 1
        assert mock_cb_2.call_count == 2

    def test_get_info(self):
        info = LaCrosse._parse_info("[LaCrosseITPlusReader.10.1s (RFM12B f:0 r:17241)]")
        assert info["name"] == "LaCrosseITPlusReader"
        assert info["version"] == "10.1s"

        info = LaCrosse._parse_info("[LaCrosseITPlusReader.10.1s (RFM12B f:0 r:17241)]")
        assert info["rfm1name"] == "RFM12B"
        assert info["rfm1frequency"] == "0"
        assert info["rfm1datarate"] == "17241"

        info = LaCrosse._parse_info("[LaCrosseITPlusReader.10.1s (RFM12B f:0 t:10~3)]")
        assert info["rfm1name"] == "RFM12B"
        assert info["rfm1frequency"] == "0"
        assert info["rfm1datarate"] is None
        assert info["rfm1toggleinterval"] == "10"
        assert info["rfm1togglemask"] == "3"

    @pytest.mark.parametrize("mode", ["t:30", "t", "t:30~", "t:~7", "r", "r:"])
    def test_get_info_handles_malformed_report(self, mode):
        info = LaCrosse._parse_info(
            f"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 {mode})]"
        )
        assert all(value is None for value in info.values())

    @pytest.mark.parametrize("valid_first", [False, True])
    def test_get_info_skips_malformed_toggle_and_continues(self, valid_first):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        malformed = b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30)]\r\n"
        valid = b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30~7)]\r\n"
        responses = [valid, malformed] if valid_first else [malformed, valid]
        pending = []
        serial_port.reset_input_buffer.side_effect = pending.clear
        serial_port.write.side_effect = lambda command: pending.extend(responses)
        serial_port.readline.side_effect = lambda: pending.pop(0) if pending else b""

        with patch("pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 1, 2, 5]):
            info = lacrosse.get_info()

        assert info["rfm1toggleinterval"] == "30"
        assert info["rfm1togglemask"] == "7"
        assert serial_port.readline.call_count == 3
        serial_port.write.assert_called_once_with(b"v")

    def test_get_info_discards_startup_banner_before_query(self):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        startup = b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 r:17241)]\r\n"
        current = b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30~7)]\r\n"
        pending = [startup]
        serial_port.reset_input_buffer.side_effect = pending.clear
        serial_port.write.side_effect = lambda command: pending.append(current)
        serial_port.readline.side_effect = lambda: pending.pop(0) if pending else b""

        with patch("pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 1, 5]):
            info = lacrosse.get_info()

        assert info["rfm1datarate"] is None
        assert info["rfm1toggleinterval"] == "30"
        assert info["rfm1togglemask"] == "7"
        serial_port.write.assert_called_once_with(b"v")

    @pytest.mark.parametrize("open_times_out", [False, True])
    def test_get_info_consumes_banner_arriving_after_reset(self, open_times_out):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        serial_port.readline.return_value = b""

        if open_times_out:
            with patch("pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 6]):
                lacrosse.open()
            serial_port.write.reset_mock()

        startup = b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 r:17241)]\r\n"
        current = b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30~7)]\r\n"
        pending = []
        serial_port.reset_input_buffer.side_effect = pending.clear
        serial_port.write.side_effect = lambda command: pending.extend(
            [startup, b"OK 9 1 1 4 150 106\r\n", current]
        )
        serial_port.readline.side_effect = lambda: pending.pop(0) if pending else b""

        with patch(
            "pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 1, 2, 3, 5]
        ):
            info = lacrosse.get_info()

        assert info["rfm1datarate"] is None
        assert info["rfm1toggleinterval"] == "30"
        assert info["rfm1togglemask"] == "7"
        assert pending == []
        serial_port.write.assert_called_once_with(b"v")

    def test_get_info_continues_through_timeouts_between_reports(self):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200, timeout=1)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        serial_port.readline.side_effect = [
            b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 r:17241)]\r\n",
            b"",
            b"",
            b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30~7)]\r\n",
            b"",
        ]

        with patch(
            "pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 1, 2, 3, 4, 5]
        ):
            info = lacrosse.get_info()

        assert info["rfm1datarate"] is None
        assert info["rfm1toggleinterval"] == "30"
        assert info["rfm1togglemask"] == "7"
        assert serial_port.readline.call_count == 5

    def test_get_info_returns_latest_report_at_deadline(self):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        serial_port = MagicMock()
        lacrosse._serial = serial_port
        serial_port.readline.side_effect = [
            b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 r:17241)]\r\n",
            b"[LaCrosseITPlusReader.10.1s (RFM69CW f:868300 t:30~7)]\r\n",
        ]

        with patch("pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 1, 6]):
            info = lacrosse.get_info()

        assert info["rfm1toggleinterval"] == "30"
        assert info["rfm1togglemask"] == "7"
        assert serial_port.readline.call_count == 2

    @pytest.mark.parametrize("response", [b"", b"[unrecognized firmware]\r\n"])
    def test_get_info_raises_if_no_recognizable_report(self, response):
        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        lacrosse._serial = MagicMock()
        lacrosse._serial.readline.return_value = response

        with patch("pylacrosse.lacrosse.time.monotonic", side_effect=[0, 0, 6]):
            with pytest.raises(TimeoutError, match="firmware information"):
                lacrosse.get_info()

    def test_led_mode_state(self):
        mock = MagicMock()

        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        lacrosse._serial.write = mock

        lacrosse.led_mode_state(True)
        lacrosse._serial.write.assert_called_with(b"1a")

        lacrosse.led_mode_state(False)
        lacrosse._serial.write.assert_called_with(b"0a")

    def test_set_frequency(self):
        mock = MagicMock()

        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        lacrosse._serial.write = mock

        lacrosse.set_frequency(100)
        lacrosse._serial.write.assert_called_with(b"100f")

        lacrosse.set_frequency("200")
        lacrosse._serial.write.assert_called_with(b"200f")

        lacrosse.set_frequency(300, rfm=1)
        lacrosse._serial.write.assert_called_with(b"300f")

        lacrosse.set_frequency(400, rfm=2)
        lacrosse._serial.write.assert_called_with(b"400F")

    def test_set_frequency_invalid_rfm(self):
        mock = MagicMock()

        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        lacrosse._serial.write = mock

        with pytest.raises(KeyError):
            lacrosse.set_frequency(500, rfm=3)
            lacrosse._serial.write.assert_called_with(b"400f")

    def test_set_datarate(self):
        mock = MagicMock()

        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        lacrosse._serial.write = mock

        lacrosse.set_datarate(0)
        lacrosse._serial.write.assert_called_with(b"0r")
        lacrosse.set_datarate("1")
        lacrosse._serial.write.assert_called_with(b"1r")

        lacrosse.set_datarate(0, rfm=1)
        lacrosse._serial.write.assert_called_with(b"0r")
        lacrosse.set_datarate(0, rfm=2)
        lacrosse._serial.write.assert_called_with(b"0R")

    def test_set_toggle_interval(self):
        mock = MagicMock()

        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        lacrosse._serial.write = mock

        lacrosse.set_toggle_interval(10)
        lacrosse._serial.write.assert_called_with(b"10t")
        lacrosse.set_toggle_interval("10")
        lacrosse._serial.write.assert_called_with(b"10t")

        lacrosse.set_toggle_interval(10, rfm=1)
        lacrosse._serial.write.assert_called_with(b"10t")
        lacrosse.set_toggle_interval(10, rfm=2)
        lacrosse._serial.write.assert_called_with(b"10T")

    def test_set_toggle_mask(self):
        mock = MagicMock()

        lacrosse = LaCrosse("/dev/ttyTEST", 115200)
        lacrosse._serial.write = mock

        lacrosse.set_toggle_mask(1)
        lacrosse._serial.write.assert_called_with(b"1m")
        lacrosse.set_toggle_mask("1")
        lacrosse._serial.write.assert_called_with(b"1m")

        lacrosse.set_toggle_mask(2, rfm=1)
        lacrosse._serial.write.assert_called_with(b"2m")
        lacrosse.set_toggle_mask(3, rfm=2)
        lacrosse._serial.write.assert_called_with(b"3M")


class TestLaCrosseSensor(object):
    def test_init(self):
        s = LaCrosseSensor("OK 9 1 1 4 150 66")
        assert s.sensorid == 1
        assert s.sensortype == 1
        assert s.temperature == 17.4
        assert s.humidity == 66
        assert not s.new_battery
        assert not s.low_battery
