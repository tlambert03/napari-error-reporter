try:
    from ._version import version as __version__
except ImportError:  # pragma: no cover
    __version__ = "unknown"


import json
from pathlib import Path
from typing import Optional, TypedDict

import sentry_sdk

from ._util import SENTRY_DSN, SENTRY_SETTINGS, _get_tags, get_sample_event

INSTALLED = False


__all__ = [
    "capture_exception",
    "SENTRY_DSN",
    "SENTRY_SETTINGS",
    "install_error_monitor",
    "capture_exception",
    "get_sample_event",
]

capture_exception = sentry_sdk.capture_exception


def _settings_path() -> Path:  # pragma: no cover
    from napari.utils._appdirs import user_data_dir

    return Path(user_data_dir()) / "error_reporting.json"


class SettingsDict(TypedDict):
    enabled: Optional[bool]
    with_locals: bool


def _load_settings() -> SettingsDict:
    data: SettingsDict = {"enabled": None, "with_locals": True}
    settings = _settings_path()
    if settings.exists():
        try:
            with open(settings) as fh:
                data.update(json.load(fh))
        except Exception:  # pragma: no cover
            settings.unlink()
    return data


def _save_settings(settings: SettingsDict):
    dest = _settings_path()
    dest.parent.mkdir(exist_ok=True, parents=True)
    with open(dest, "w") as fh:
        json.dump(settings, fh)


def _ask_opt_in() -> SettingsDict:
    settings = _load_settings()
    if settings.get("enabled") is not None:
        return settings

    from ._opt_in_widget import OptInWidget

    dlg = OptInWidget()
    send: Optional[bool] = None
    if bool(dlg.exec()):
        send = True  # pragma: no cover
    elif dlg._no:
        send = False  # pragma: no cover

    settings.update({"enabled": send, "with_locals": dlg.send_locals.isChecked()})
    _save_settings(settings)
    return settings


def install_error_monitor():
    global INSTALLED
    if INSTALLED:
        return  # pragma: no cover
    settings = _ask_opt_in()
    if not settings.get("enabled"):
        return

    _settings = SENTRY_SETTINGS.copy()
    _settings["with_locals"] = settings.get("with_locals", False)
    sentry_sdk.init(**_settings)
    for k, v in _get_tags().items():
        sentry_sdk.set_tag(k, v)
    INSTALLED = True
