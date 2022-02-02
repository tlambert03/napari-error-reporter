from platform import platform
from unittest.mock import MagicMock, patch

import pytest

import napari_error_monitor
from napari_error_monitor import _ask_opt_in, get_sample_event, install_error_monitor
from napari_error_monitor._opt_in_widget import OptInWidget


@pytest.fixture(autouse=True)
def mock_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        napari_error_monitor,
        "_settings_path",
        lambda: tmp_path / "error_reporting.json",
    )


def test_widget(qtbot):
    wdg = OptInWidget()
    qtbot.addWidget(wdg)
    wdg._set_no()
    assert wdg._no


def test_example_event():
    event = get_sample_event()
    assert isinstance(event, dict)
    assert event["environment"] == platform()


def test_opt_in():
    """The opt in should only show if there are no settings, or if enabled is None."""
    assert not napari_error_monitor._settings_path().exists()

    mock = MagicMock(return_value=None)
    setattr(OptInWidget, "exec", mock)

    assert mock.call_count == 0
    assert _ask_opt_in()["enabled"] is None
    assert mock.call_count == 1

    assert napari_error_monitor._settings_path().exists()

    napari_error_monitor._save_settings({"enabled": True, "with_locals": True})
    assert _ask_opt_in()["enabled"] is True
    assert mock.call_count == 1

    napari_error_monitor._save_settings({"enabled": None, "with_locals": False})
    s = _ask_opt_in()
    assert s["enabled"] is None
    assert s["with_locals"] is False
    assert mock.call_count == 2

    napari_error_monitor._save_settings({"enabled": False, "with_locals": True})
    assert _ask_opt_in()["enabled"] is False
    assert mock.call_count == 2


def test_install():
    with patch("sentry_sdk.init") as mock:
        napari_error_monitor._save_settings({"enabled": False, "with_locals": True})
        install_error_monitor()
        mock.assert_not_called()

        assert not napari_error_monitor.INSTALLED
        napari_error_monitor._save_settings({"enabled": True, "with_locals": True})
        install_error_monitor()
        mock.assert_called_once()

        assert napari_error_monitor.INSTALLED
