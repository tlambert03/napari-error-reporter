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

from ._util import get_sample_event


class OptInWidget(QDialog):
    def __init__(self, parent=None) -> None:
        if parent is None:
            app = QApplication.instance()
            for i in app.topLevelWidgets():
                if isinstance(i, QMainWindow):  # pragma: no cover
                    parent = i
                    break
        super().__init__(parent=parent)
        self._mock_initialized = False
        self._no = False

        self._setup_ui()
        self._update_example()

    def _setup_ui(self):
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

        info = QLabel(
            """<h3>napari error reporting</h3>
            <br><br>
            You have installed <em>napari-error-monitoring</em>.<br><br>
            Would you like to help us improve napari by automatically sending
            bug reports when an error is detected in napari?
            <br><br>
            Reports are collected via <a href="https://sentry.io/">Sentry.io</a>
            <br><br>
            Here is an example error log that would be sent from your system:
            """
        )
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        info.setOpenExternalLinks(True)

        self.txt = QTextEdit()
        self.txt.setReadOnly(True)

        self.send_locals = QCheckBox("Include local variables")
        self.send_locals.setChecked(False)
        self.send_locals.stateChanged.connect(self._update_example)
        self.send_locals.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        _lbl = QLabel(
            "<small><em><b>greatly</b> improves interpretability of errors, but may "
            "leak personal identifiable information like file paths</em></small>"
        )
        _lbl.setWordWrap(True)
        _lbl.setStyleSheet("color: #999;")

        _lbl2 = QLabel(
            "<small><em>you may change your settings at any time in the "
            "napari preferences window.</em></small>"
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
        self.resize(720, 740)

    def _set_no(self):
        self._no = True

    def _update_example(self):
        event = get_sample_event(with_locals=self.send_locals.isChecked())
        self.txt.setText(pformat(event, indent=2, width=120))
