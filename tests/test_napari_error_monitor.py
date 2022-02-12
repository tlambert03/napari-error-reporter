import sys
from platform import system
from unittest.mock import MagicMock, patch

import pytest

import napari_error_reporter
from napari_error_reporter import (
    _save_settings,
    _util,
    ask_opt_in,
    get_release,
    get_sample_event,
    install_error_reporter,
)
from napari_error_reporter._opt_in_widget import OptInWidget


@pytest.fixture(autouse=True)
def mocked_settings_and_urlopen(tmp_path, monkeypatch):
    assert str(napari_error_reporter.settings_path()).endswith(".json")
    monkeypatch.setattr(
        napari_error_reporter, "settings_path", lambda: tmp_path / "test.json"
    )

    with patch.object(_util, "urlopen") as mock_urlopen:
        cm = MagicMock()
        cm.getcode.return_value = 200
        cm.read.return_value = b"Me (@me)\nYou (@you)"
        cm.__enter__.return_value = cm
        mock_urlopen.return_value = cm
        yield


def create_settings(**kwargs) -> _util.SettingsDict:
    return {**_util._DEFAULT_SETTINGS, **kwargs}  # type: ignore


def test_widget(qtbot, monkeypatch):
    wdg = OptInWidget(create_settings())
    qtbot.addWidget(wdg)
    wdg._set_no()
    assert wdg._no

    # make sure we can print a message in the absence of yaml
    monkeypatch.setitem(sys.modules, "yaml", None)
    wdg = OptInWidget(create_settings())
    qtbot.addWidget(wdg)


def test_get_admins():
    # this is mocked in mocked_settings_and_urlopen
    assert _util._try_get_admins() == {"Me (@me)", "You (@you)"}


def test_widget_admins_changed(qtbot):
    wdg = OptInWidget(admins_have_changed=True)
    qtbot.addWidget(wdg)
    wdg._set_no()
    assert wdg._no


def test_example_event():
    event = get_sample_event()
    assert isinstance(event, dict)
    assert event["environment"] == system()


@pytest.mark.parametrize("force", [True, False])
@pytest.mark.parametrize(
    "settings, count",
    [
        # if we have no settings, or enabled is None, we show
        (dict(), 1),
        (dict(enabled=None), 1),
        # if enabled is True, we don't ask unless admins have changed
        (dict(enabled=True), 0),
        (dict(enabled=True, admins={"Someone (@someone)"}), 1),
        # if enabled is False, we never ask
        (dict(enabled=False), 0),
        (dict(enabled=False, admins={"Someone (@someone)"}), 0),
    ],
)
def test_opt_in(force, settings, count):
    """The opt in should only show if there are no settings, or if enabled is None."""
    assert not napari_error_reporter.settings_path().exists()

    mock = MagicMock(return_value=None)
    setattr(OptInWidget, "exec", mock)  # mock the widget
    assert mock.call_count == 0

    _save_settings(create_settings(**settings))
    ask_opt_in(force=force)
    assert mock.call_count == (1 if force else count)


def test_install():
    assert not napari_error_reporter.INSTALLED
    with patch("sentry_sdk.init") as mock:
        _save_settings(create_settings(enabled=False))
        install_error_reporter()
        mock.assert_not_called()

        assert not napari_error_reporter.INSTALLED
        D = create_settings(enabled=True, admins={"Me (@me)", "You (@you)"})
        _save_settings(D)
        install_error_reporter()
        mock.assert_called_once()

        # only gets called once
        assert napari_error_reporter.INSTALLED
        install_error_reporter()
        mock.assert_called_once()


def test_get_release_fail():
    assert get_release("aasldkhjfas") == "UNDETECTED"
