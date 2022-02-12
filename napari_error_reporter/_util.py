import functools
import os
import platform
from contextlib import suppress
from datetime import datetime
from importlib import metadata
from site import getsitepackages, getusersitepackages
from subprocess import run
from typing import Dict, Optional, Set, TypedDict
from urllib.error import URLError
from urllib.request import urlopen

import sentry_sdk

try:
    from rich import print as pprint
except ImportError:  # pragma: no cover
    from pprint import pprint


SENTRY_DSN = (
    "https://f9d6b27849a34934bd7fe799295af690@o1142361.ingest.sentry.io/6201321"
)

SHOW_HOSTNAME = os.getenv("NAPARI_TELEMETRY_SHOW_HOSTNAME", "0") in ("1", "True")
SHOW_LOCALS = os.getenv("NAPARI_TELEMETRY_SHOW_LOCALS", "1") in ("1", "True")
DEBUG = bool(os.getenv("NAPARI_TELEMETRY_DEBUG"))


class SettingsDict(TypedDict):
    enabled: Optional[bool]
    with_locals: bool
    admins: Set[str]
    date: datetime


_DEFAULT_SETTINGS: SettingsDict = {
    "enabled": None,
    "with_locals": False,
    "admins": set(),
    "date": datetime.now(),
}


def strip_sensitive_data(event: dict, hint: dict):
    """Pre-send hook to strip sensitive data from `event` dict.

    https://docs.sentry.io/platforms/python/configuration/filtering/#filtering-error-events
    """
    # modify event here

    # strip `abs_paths` from stack_trace to hide local paths
    with suppress(KeyError, IndexError):
        for exc in event["exception"]["values"]:
            for frame in exc["stacktrace"]["frames"]:
                frame.pop("abs_path", None)
        # only include the name of the executable in sys.argv (remove pathsƒ)
        if args := event["extra"]["sys.argv"]:
            args[0] = args[0].split(os.sep)[-1]
    if DEBUG:  # pragma: no cover
        pprint(event)
    return event


def is_editable_install(dist_name: str) -> bool:
    """Return True if `dist_name` is installed as editable.

    i.e: if the package isn't in site-packages or user site-packages.
    """

    dist = metadata.distribution(dist_name)
    installed_paths = getsitepackages() + [getusersitepackages()]
    root = str(dist.locate_file(""))
    return all(loc not in root for loc in installed_paths)


def try_get_git_sha(dist_name: str = "napari") -> str:
    """Try to return a git sha, for `dist_name` and detect if dirty.

    Return empty string on failure.
    """
    try:
        ff = metadata.distribution(dist_name).locate_file("")
        out = run(["git", "-C", ff, "rev-parse", "HEAD"], capture_output=True)
        if out.returncode:  # pragma: no cover
            return ""
        sha = out.stdout.decode().strip()
        # exit with 1 if there are differences and 0 means no differences
        # disallow external diff drivers
        out = run(["git", "-C", ff, "diff", "--no-ext-diff", "--quiet", "--exit-code"])
        if out.returncode:  # pragma: no cover
            sha += "-dirty"
        return sha
    except Exception:  # pragma: no cover
        return ""


@functools.lru_cache
def get_release(package="napari") -> str:
    """Get the current release string for `package`.

    If the package is an editable install, it will return the current git sha.
    Otherwise return version string from package metadata.
    """
    with suppress(ModuleNotFoundError):
        if is_editable_install(package):
            if sha := try_get_git_sha(package):
                return sha
        return metadata.version(package)
    return "UNDETECTED"


# https://docs.sentry.io/platforms/python/configuration/
SENTRY_SETTINGS = dict(
    dsn=SENTRY_DSN,
    # When enabled, local variables are sent along with stackframes.
    # This can have a performance and PII impact.
    # Enabled by default on platforms where this is available.
    with_locals=SHOW_LOCALS,
    # A number between 0 and 1, controlling the percentage chance
    # a given transaction will be sent to Sentry.
    # (0 represents 0% while 1 represents 100%.)
    # Applies equally to all transactions created in the app.
    # Either this or traces_sampler must be defined to enable tracing.
    traces_sample_rate=1.0,
    # When provided, the name of the server is sent along and persisted
    # in the event. For many integrations the server name actually
    # corresponds to the device hostname, even in situations where the
    # machine is not actually a server. Most SDKs will attempt to
    # auto-discover this value. (computer name: potentially PII)
    server_name=None if SHOW_HOSTNAME else "",
    # If this flag is enabled, certain personally identifiable information (PII)
    # is added by active integrations. By default, no such data is sent.
    send_default_pii=False,
    # This function is called with an SDK-specific event object, and can return a
    # modified event object or nothing to skip reporting the event.
    # This can be used, for instance, for manual PII stripping before sending.
    before_send=strip_sensitive_data,
    debug=DEBUG,
    # -------------------------
    environment=platform.system(),
    # max_breadcrumbs=DEFAULT_MAX_BREADCRUMBS,
    # shutdown_timeout=2,
    # integrations=[],
    # in_app_include=[],
    # in_app_exclude=[],
    # default_integrations=True,
    # dist=None,
    # transport=None,
    # transport_queue_size=DEFAULT_QUEUE_SIZE,
    # sample_rate=1.0,
    # http_proxy=None,
    # https_proxy=None,
    # ignore_errors=[],
    # request_bodies="medium",
    # before_breadcrumb=None,
    # attach_stacktrace=False,
    # ca_certs=None,
    # propagate_traces=True,
    # traces_sampler=None,
    # auto_enabling_integrations=True,
    # auto_session_tracking=True,
    # _experiments={},
)


@functools.lru_cache
def get_tags() -> Dict[str, str]:
    """Get platform and other tags to associate with this session."""
    tags = {"platform.platform": platform.platform()}

    with suppress(ImportError):
        from napari.utils.info import _sys_name

        if sys := _sys_name():
            tags["system_name"] = sys

    with suppress(ImportError):
        import qtpy

        tags["qtpy.API_NAME"] = qtpy.API_NAME
        tags["qtpy.QT_VERSION"] = qtpy.QT_VERSION

    with suppress(ModuleNotFoundError):
        tags["editable_install"] = str(is_editable_install("napari"))

    return tags


def get_sample_event(**kwargs) -> dict:
    """Return an example event as would be generated by an exception."""
    EVENT: dict = {}

    def _trans(event: dict):
        nonlocal EVENT
        EVENT = event

    settings = SENTRY_SETTINGS.copy()
    settings["release"] = get_release()
    settings["dsn"] = ""
    settings["transport"] = _trans
    settings.update(kwargs)

    with sentry_sdk.Client(**settings) as client:
        with sentry_sdk.Hub(client) as hub:
            # remove locals that wouldn't really be there
            del settings, _trans, kwargs, client, EVENT
            try:
                some_variable = 1  # noqa
                another_variable = "my_string"  # noqa
                1 / 0
            except Exception:
                with sentry_sdk.push_scope() as scope:
                    for k, v in get_tags().items():
                        scope.set_tag(k, v)
                    del v, k, scope
                    hub.capture_exception()

    with suppress(KeyError, IndexError):
        # remove the mock hub from the event
        frames = EVENT["exception"]["values"][0]["stacktrace"]["frames"]  # type: ignore
        del frames[-1]["vars"]["hub"]

    return EVENT


def _try_get_admins() -> Optional[Set[str]]:
    """Retrieve list of current admins stored in the github repo.

    Return None on error.
    """
    U = "https://raw.githubusercontent.com/tlambert03/napari-error-reporter/main/ADMINS"
    try:
        with urlopen(U) as response:
            content: str = response.read().decode()
            return {line for line in content.splitlines() if not line.startswith("#")}
    except URLError:  # pragma: no cover
        return None
