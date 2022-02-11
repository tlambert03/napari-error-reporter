from platform import platform
from unittest.mock import MagicMock, patch

import pytest

import napari_error_reporter
from napari_error_reporter import ask_opt_in, get_sample_event, install_error_reporter


@pytest.fixture(autouse=True)
def mock_settings(tmp_path, monkeypatch):
    assert str(napari_error_reporter.settings_path()).endswith(".json")
    monkeypatch.setattr(
        napari_error_reporter, "settings_path", lambda: tmp_path / "test.json"
    )


def test_widget(qtbot):
    wdg = napari_error_reporter.OptInWidget()
    qtbot.addWidget(wdg)
    wdg._set_no()
    assert wdg._no


def test_example_event():
    event = get_sample_event()
    assert isinstance(event, dict)
    assert event["environment"] == platform()


def test_opt_in():
    """The opt in should only show if there are no settings, or if enabled is None."""
    assert not napari_error_reporter.settings_path().exists()

    mock = MagicMock(return_value=None)
    setattr(napari_error_reporter.OptInWidget, "exec", mock)

    assert mock.call_count == 0
    assert ask_opt_in()["enabled"] is None
    assert mock.call_count == 1

    assert napari_error_reporter.settings_path().exists()

    napari_error_reporter._save_settings({"enabled": True, "with_locals": True})
    assert ask_opt_in()["enabled"] is True
    assert mock.call_count == 1

    napari_error_reporter._save_settings({"enabled": None, "with_locals": False})
    s = ask_opt_in()
    assert s["enabled"] is None
    assert s["with_locals"] is False
    assert mock.call_count == 2

    napari_error_reporter._save_settings({"enabled": False, "with_locals": True})
    assert ask_opt_in()["enabled"] is False
    assert mock.call_count == 2


def test_install():
    with patch("sentry_sdk.init") as mock:
        napari_error_reporter._save_settings({"enabled": False, "with_locals": True})
        install_error_reporter()
        mock.assert_not_called()

        assert not napari_error_reporter.INSTALLED
        napari_error_reporter._save_settings({"enabled": True, "with_locals": True})
        install_error_reporter()
        mock.assert_called_once()

        # only gets called once
        assert napari_error_reporter.INSTALLED
        install_error_reporter()
        mock.assert_called_once()
