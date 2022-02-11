try:
    from ._version import version as __version__
except ImportError:  # pragma: no cover
    __version__ = "unknown"


import json
from pathlib import Path
from typing import Optional, TypedDict

import appdirs
import sentry_sdk

from ._opt_in_widget import OptInWidget
from ._util import SENTRY_SETTINGS, _get_tags, get_sample_event

INSTALLED = False


__all__ = [
    "ask_opt_in",
    "capture_exception",
    "capture_message",
    "add_breadcrumb",
    "get_sample_event",
    "install_error_reporter",
    "OptInWidget",
    "settings_path",
]


capture_exception = sentry_sdk.capture_exception
capture_message = sentry_sdk.capture_message
add_breadcrumb = sentry_sdk.add_breadcrumb


def settings_path() -> Path:
    """Return the path used for napari-error-reporter settings."""
    data = appdirs.user_data_dir("napari", False)
    return Path(data) / "error_reporting.json"


class SettingsDict(TypedDict):
    enabled: Optional[bool]
    with_locals: bool


def _load_settings() -> SettingsDict:
    data: SettingsDict = {"enabled": None, "with_locals": False}
    settings = settings_path()
    if settings.exists():
        try:
            with open(settings) as fh:
                data.update(json.load(fh))
        except Exception:  # pragma: no cover
            settings.unlink()
    return data


def _save_settings(settings: SettingsDict):
    dest = settings_path()
    dest.parent.mkdir(exist_ok=True, parents=True)
    with open(dest, "w") as fh:
        json.dump(settings, fh)


def ask_opt_in(force=False) -> SettingsDict:
    """Show the dialog asking the user to opt in.

    Parameters
    ----------
    force : bool, optional
        If True, will show opt_in even if user has already opted in/out,
        by default False.

    Returns
    -------
    SettingsDict
        [description]
    """
    settings = _load_settings()
    if not force and settings.get("enabled") is not None:
        return settings

    dlg = OptInWidget(with_locals=settings["with_locals"])
    send: Optional[bool] = None
    if bool(dlg.exec()):
        send = True  # pragma: no cover
    elif dlg._no:
        send = False  # pragma: no cover

    settings.update({"enabled": send, "with_locals": dlg.send_locals.isChecked()})
    _save_settings(settings)
    return settings


def install_error_reporter():
    """Initialize the error reporter with sentry.io"""
    global INSTALLED
    if INSTALLED:
        return  # pragma: no cover

    settings = ask_opt_in()
    if not settings.get("enabled"):
        return

    _settings = SENTRY_SETTINGS.copy()
    _settings["with_locals"] = settings.get("with_locals", False)
    sentry_sdk.init(**_settings)
    for k, v in _get_tags().items():
        sentry_sdk.set_tag(k, v)
    INSTALLED = True
