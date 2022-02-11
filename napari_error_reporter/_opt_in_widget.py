import re
from pprint import pformat

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ._util import _DEFAULT_SETTINGS, SettingsDict, get_sample_event


class OptInWidget(QDialog):
    def __init__(
        self,
        settings: SettingsDict = _DEFAULT_SETTINGS,
        admins_have_changed: bool = False,
        parent=None,
    ) -> None:
        if parent is None:
            app = QApplication.instance()
            for i in app.topLevelWidgets():
                if isinstance(i, QMainWindow):  # pragma: no cover
                    parent = i
                    break
        super().__init__(parent=parent)
        self._mock_initialized = False
        self._no = False

        self._setup_ui(settings, admins_have_changed)
        self.send_locals.setChecked(settings.get("with_locals", False))
        self._update_example()

    def _setup_ui(self, settings: SettingsDict, admins_have_changed: bool):
        btn_box = QDialogButtonBox()
        btn_box.addButton(
            "Yes, send my bug reports to napari", QDialogButtonBox.AcceptRole
        )
        no = btn_box.addButton(
            "No, I'd prefer not to send bug reports", QDialogButtonBox.RejectRole
        )
        no.clicked.connect(self._set_no)

        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        ads = []
        for i in settings["admins"]:
            match = re.search(r"(.+) \(@(.+)\)", i)
            if match:
                name, username = match.groups()
                ads.append(
                    f'<a style="color: #6495ED;" '
                    f'href="https://github.com/{username}">{name}</a>'
                )
        _ads = ", ".join(ads)
        _ads = f"These admins have access: {_ads}"
        if admins_have_changed:
            _ads = f'<strong style="color:red;">CHANGE</strong> {_ads}'

        _info = """<h2>You have installed <em>napari-error-reporter</em></h2>
        <br><br>
        Would you like to help us improve napari by automatically sending
        bug reports (via <a style="color: #6495ED;" href="https://sentry.io/">
        Sentry.io</a>) when an error is detected in napari?
        <br><br>{}<br><br>
        Here is an example error log that would be sent from your system:
        """.format(
            _ads
        )

        info = QLabel(_info)
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        info.setOpenExternalLinks(True)

        self.txt = QTextEdit()
        self.txt.setReadOnly(True)

        self.send_locals = QCheckBox("Include local variables")
        self.send_locals.stateChanged.connect(self._update_example)
        self.send_locals.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        _lbl = QLabel(
            "<small><em><b>greatly</b> improves interpretability of errors, but may "
            "leak personal identifiable information like file paths</em></small>"
        )
        _lbl.setWordWrap(True)
        _lbl.setStyleSheet("color: #999;")

        _lbl2 = QLabel(
            "You may opt out at any time with <em>Bug reporting opt in/out...</em>"
            " in the Help menu."
        )
        _lbl2.setStyleSheet("color: #999;")
        _lbl2.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(info)
        self.layout().addWidget(self.txt)

        w = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(self.send_locals)
        layout.addWidget(_lbl)
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        self.layout().addWidget(w)
        self.layout().addWidget(btn_box)
        self.layout().addWidget(_lbl2)
        self.resize(660, 600)

    def _set_no(self):
        self._no = True

    def _update_example(self):
        event = get_sample_event(with_locals=self.send_locals.isChecked())

        try:
            import yaml

            estring = yaml.safe_dump(event, indent=4, width=120)
        except Exception:
            estring = pformat(event, indent=2, width=120)

        self.txt.setText(estring)
