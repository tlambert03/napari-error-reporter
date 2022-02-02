import os
import platform
from contextlib import suppress

import sentry_sdk

try:
    from rich import print as pprint
except ImportError:  # pragma: no cover
    from pprint import pprint

try:
    from napari import __version__ as napari_version
except ImportError:  # pragma: no cover
    napari_version = "None"

SENTRY_DSN = "https://a265f1a2a6254d6e8c32c3da6f75fe95@o100671.ingest.sentry.io/5894957"
SHOW_HOSTNAME = os.getenv("NAPARI_TELEMETRY_SHOW_HOSTNAME", "0") in ("1", "True")
SHOW_LOCALS = os.getenv("NAPARI_TELEMETRY_SHOW_LOCALS", "1") in ("1", "True")
DEBUG = bool(os.getenv("NAPARI_TELEMETRY_DEBUG"))


def strip_sensitive_data(event: dict, hint: dict):
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


SENTRY_SETTINGS = dict(
    dsn=SENTRY_DSN,
    release=napari_version,
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
    environment=platform.platform(),
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


def _get_tags() -> dict:
    tags = {"platform.system": platform.system()}

    with suppress(ImportError):
        from napari.utils.info import _sys_name

        tags["platform.name"] = _sys_name()

    with suppress(ImportError):
        import qtpy

        tags["qtpy.API_NAME"] = qtpy.API_NAME
        tags["qtpy.QT_VERSION"] = qtpy.QT_VERSION

    return tags


def get_sample_event(**kwargs):

    EVENT: dict = {}

    def _trans(event: dict):
        nonlocal EVENT
        EVENT = event

    settings = SENTRY_SETTINGS.copy()
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
                    for k, v in _get_tags().items():
                        scope.set_tag(k, v)
                    del v, k, scope
                    hub.capture_exception()
    try:
        # remove the mock hub from the event
        frames = EVENT["exception"]["values"][0]["stacktrace"]["frames"]  # type: ignore
        del frames[-1]["vars"]["hub"]
    except (KeyError, IndexError):
        pass

    return EVENT
