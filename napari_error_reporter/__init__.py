try:
    from ._version import version as __version__
except ImportError:  # pragma: no cover
    __version__ = "unknown"

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, cast

import appdirs
import sentry_sdk

from ._util import (
    _DEFAULT_SETTINGS,
    SENTRY_SETTINGS,
    SettingsDict,
    _try_get_admins,
    get_release,
    get_sample_event,
    get_tags,
)

INSTALLED = False


__all__ = [
    "ask_opt_in",
    "capture_exception",
    "capture_message",
    "add_breadcrumb",
    "get_sample_event",
    "get_release",
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


def _load_settings() -> SettingsDict:
    """load saved settings."""
    data: SettingsDict = _DEFAULT_SETTINGS
    settings = settings_path()
    if settings.exists():
        try:
            with open(settings) as fh:
                _data = json.load(fh)
                if "date" in _data:
                    try:
                        _data["date"] = datetime.fromisoformat(_data["date"])
                    except Exception:  # pragma: no cover
                        _data["date"] = datetime.now()
                else:  # pragma: no cover
                    _data["date"] = datetime.now()
                data.update(_data)
        except Exception:  # pragma: no cover
            settings.unlink()
    data["admins"] = set(data["admins"])
    return data


def _save_settings(settings: SettingsDict):
    """Save settings dict to user space."""
    dest = settings_path()
    dest.parent.mkdir(exist_ok=True, parents=True)
    _settings = cast(dict, settings.copy())
    _settings["admins"] = list(settings["admins"])  # cast to list for serialization
    _settings["date"] = settings["date"].isoformat()  # cast to string

    with open(dest, "w") as fh:
        json.dump(_settings, fh)


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
        A dict of settings (see SettingsDict class.)
    """
    settings = _load_settings()
    current_admins = _try_get_admins()
    admins_have_changed = bool(
        current_admins and settings["admins"] and current_admins != settings["admins"]
    )

    if not force:
        if settings.get("enabled") is False:
            # if they've previously responded "No", bail here.
            return settings
        elif settings.get("enabled") and not admins_have_changed:
            # if they've previously responded "Yes"
            # and `force` is not True (to force showing the prompt again)
            # and the admins haven't changed since the last acceptance
            # then don't ask again.
            return settings

    # otherwise, update admins in the settings and show the widget
    if current_admins is not None:
        settings["admins"] = current_admins

    from ._opt_in_widget import OptInWidget

    dlg = OptInWidget(settings=settings, admins_have_changed=admins_have_changed)
    enabled: Optional[bool] = None
    if bool(dlg.exec()):
        enabled = True  # pragma: no cover
    elif dlg._no:
        enabled = False  # pragma: no cover

    lcls = dlg.send_locals.isChecked()
    settings.update({"enabled": enabled, "with_locals": lcls, "date": datetime.now()})
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
    _settings["release"] = get_release()
    _settings["with_locals"] = settings.get("with_locals", False)
    sentry_sdk.init(**_settings)
    for k, v in get_tags().items():
        sentry_sdk.set_tag(k, v)
    sentry_sdk.set_user({"id": uuid.getnode()})
    INSTALLED = True
