import json

import pytest

from opengarage import cli
from opengarage.errors import ResponseError
from opengarage.state import NormalizedState


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.close_connection_called = False

    async def get_state(self):
        return NormalizedState("open", 1, light_on=True, raw={"door": 1, "light": 1})

    async def get_capabilities(self):
        return {"light_control": True}

    async def push_open_button(self):
        return "success"

    async def set_light(self, on):
        self.set_light_called_with = on
        return "success"

    async def set_lock(self, engaged):
        self.set_lock_called_with = engaged
        return "success"

    async def reboot(self):
        return "success"

    async def ap_mode(self):
        return "success"

    async def close_connection(self):
        self.close_connection_called = True


def test_build_parser_rejects_unknown_action():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["http://device", "not-a-real-action"])


def test_main_state_text_output(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    exit_code = cli.main(["http://device", "state"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "door_state: open" in out
    assert "capabilities:" in out
    assert "raw:" in out
    assert "  door: 1" in out


def test_main_state_json_output(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    exit_code = cli.main(["http://device", "state", "--json"])
    out = capsys.readouterr().out
    assert exit_code == 0
    payload = json.loads(out)
    assert payload["door_state"] == "open"


def test_main_action_open(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    exit_code = cli.main(["http://device", "open"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "open: success" in out


def test_main_set_light_requires_state(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    exit_code = cli.main(["http://device", "set-light"])
    err = capsys.readouterr().err
    assert exit_code == 2
    assert "--state" in err


def test_main_rejects_state_for_unrelated_action(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    exit_code = cli.main(["http://device", "toggle-light", "--state", "on"])
    err = capsys.readouterr().err
    assert exit_code == 2
    assert "--state" in err


def test_main_apmode_aborts_on_eof(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)

    def _raise_eof(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)
    exit_code = cli.main(["http://device", "apmode"])
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "aborted" in err


def test_main_set_light_on(monkeypatch, capsys):
    client_holder = {}

    class TrackingClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            client_holder["client"] = self

    monkeypatch.setattr(cli, "OpenGarage", TrackingClient)
    exit_code = cli.main(["http://device", "set-light", "--state", "on"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "set-light: success" in out
    assert client_holder["client"].set_light_called_with is True


def test_main_set_lock_off(monkeypatch, capsys):
    client_holder = {}

    class TrackingClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            client_holder["client"] = self

    monkeypatch.setattr(cli, "OpenGarage", TrackingClient)
    exit_code = cli.main(["http://device", "set-lock", "--state", "off"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "set-lock: success" in out
    assert client_holder["client"].set_lock_called_with is False


def test_main_capabilities_text_output(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    exit_code = cli.main(["http://device", "capabilities"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "capabilities:" in out
    assert "light_control: yes" in out


def test_main_state_json_output_is_indented(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    exit_code = cli.main(["http://device", "state", "--json"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "\n" in out.strip()


def test_main_closes_connection_on_error(monkeypatch):
    closed = {}

    class FailingClient(FakeClient):
        async def get_state(self):
            raise ResponseError(500, "http://device/jc")

        async def close_connection(self):
            closed["called"] = True

    monkeypatch.setattr(cli, "OpenGarage", FailingClient)
    exit_code = cli.main(["http://device", "state"])
    assert exit_code == 1
    assert closed["called"] is True


def test_main_prints_error_to_stderr(monkeypatch, capsys):
    class FailingClient(FakeClient):
        async def get_state(self):
            raise ResponseError(500, "http://device/jc")

    monkeypatch.setattr(cli, "OpenGarage", FailingClient)
    exit_code = cli.main(["http://device", "state"])
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "error:" in err


def test_main_apmode_requires_confirmation(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    exit_code = cli.main(["http://device", "apmode"])
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "aborted" in err


def test_main_apmode_confirmed_via_prompt(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    exit_code = cli.main(["http://device", "apmode"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "apmode: success" in out


def test_main_apmode_skips_confirmation_with_yes_flag(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)

    def _unexpected_input(prompt):
        raise AssertionError("input() should not be called when --yes is passed")

    monkeypatch.setattr("builtins.input", _unexpected_input)
    exit_code = cli.main(["http://device", "apmode", "--yes"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "apmode: success" in out


def test_main_reboot_requires_confirmation(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    exit_code = cli.main(["http://device", "reboot"])
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "aborted" in err


def test_main_state_does_not_prompt(monkeypatch):
    monkeypatch.setattr(cli, "OpenGarage", FakeClient)

    def _unexpected_input(prompt):
        raise AssertionError("input() should not be called for non-disruptive actions")

    monkeypatch.setattr("builtins.input", _unexpected_input)
    exit_code = cli.main(["http://device", "state"])
    assert exit_code == 0
