"""
todo_gui.py - giao diện bấm-chạy cho Export/Import Microsoft To Do.

Cài (1 lần):
    pip install msal requests PySide6
Hoặc không cần cài, chạy thẳng bằng uv:
    uv run --with msal --with requests --with pyside6 todo_gui.py

Đóng gói thành .exe (bấm đúp là chạy, không hiện cửa sổ đen):
    pyinstaller --noconsole --onefile --name TodoBackup todo_gui.py
"""

import json
import sys
import time
import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from todo_core import Cancelled, TodoSession

STYLE = """
QWidget { background:#1e2327; color:#e6e6e6; font-family:"Segoe UI"; font-size:10pt; }
QLabel { background:transparent; }
QLabel#title { font-size:16pt; font-weight:700; }
QLabel#sub, QLabel#hint { color:#9aa5ad; }
QPushButton { background:#2d353b; border:1px solid #3a444b; border-radius:8px;
              padding:12px 18px; font-weight:600; }
QPushButton:hover { background:#374046; }
QPushButton:disabled { color:#6b757c; background:#252b30; }
QPushButton#primary { background:#2f6fed; border-color:#2f6fed; color:white; }
QPushButton#primary:hover { background:#4a82f0; }
QPushButton#primary:disabled { background:#2a3f6b; border-color:#2a3f6b; color:#8a97b3; }
QPushButton#small { padding:6px 12px; }
QPlainTextEdit { background:#161a1d; border:1px solid #2d353b; border-radius:8px;
                 padding:8px; font-family:Consolas, monospace; font-size:9pt; }
QProgressBar { background:#2d353b; border:none; border-radius:4px; }
QProgressBar::chunk { background:#2f6fed; border-radius:4px; }
QFrame#loginCard { background:#262d32; border:1px solid #2f6fed; border-radius:10px; }
QLabel#code { font-family:Consolas, monospace; font-size:24pt; font-weight:700;
              color:#7fb0ff; }
"""


class Worker(QThread):
    log = Signal(str)
    progress = Signal(int, int)
    device_code = Signal(str, str)
    logged_in = Signal()
    done = Signal(bool, str)

    def __init__(self, session, mode, path):
        super().__init__()
        self.session = session
        self.mode = mode
        self.path = path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        s = self.session
        s.log = self.log.emit
        s.on_progress = self.progress.emit
        s.on_device_code = lambda code, uri, msg: self.device_code.emit(code, uri)
        s.on_logged_in = self.logged_in.emit
        s.is_cancelled = lambda: self._cancel
        try:
            if self.mode == "export":
                backup = s.export_all()
                Path(self.path).write_text(
                    json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                n_tasks = sum(len(l["tasks"]) for l in backup["lists"])
                self.done.emit(
                    True,
                    f"Xong: {len(backup['lists'])} list, {n_tasks} task.\n{self.path}",
                )
            else:
                backup = json.loads(Path(self.path).read_text(encoding="utf-8"))
                n_lists, n_tasks = s.import_backup(backup)
                self.done.emit(True, f"Xong: import {n_tasks} task vào {n_lists} list.")
        except Cancelled:
            self.done.emit(False, "Đã huỷ.")
        except Exception as e:  # noqa: BLE001 - hiện lỗi cho người dùng
            self.done.emit(False, f"Lỗi: {e}")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("To Do Backup")
        self.resize(560, 640)

        self.session = TodoSession()  # giữ đăng nhập trong RAM suốt phiên
        self.worker = None
        self.last_export = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("Microsoft To Do Backup")
        title.setObjectName("title")
        sub = QLabel("Sao lưu và khôi phục list, task, ghi chú, hạn, nhắc nhở, checklist.")
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.btn_export = QPushButton("Export (sao lưu)")
        self.btn_export.setObjectName("primary")
        self.btn_import = QPushButton("Import (khôi phục)")
        self.btn_export.clicked.connect(self.start_export)
        self.btn_import.clicked.connect(self.start_import)
        row.addWidget(self.btn_export)
        row.addWidget(self.btn_import)
        root.addLayout(row)

        # Thẻ đăng nhập, chỉ hiện khi cần nhập device code
        self.login_card = QFrame()
        self.login_card.setObjectName("loginCard")
        lc = QVBoxLayout(self.login_card)
        lc.setContentsMargins(16, 14, 16, 14)
        lc.addWidget(QLabel("Đăng nhập Microsoft: nhập mã này vào trình duyệt"))
        self.code_label = QLabel("")
        self.code_label.setObjectName("code")
        lc.addWidget(self.code_label)
        hint = QLabel("Mã đã được copy sẵn và trình duyệt đã tự mở. Dán mã rồi đăng nhập.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lc.addWidget(hint)
        btn_row = QHBoxLayout()
        self.btn_open = QPushButton("Mở lại trang đăng nhập")
        self.btn_open.setObjectName("small")
        self.btn_copy = QPushButton("Copy mã")
        self.btn_copy.setObjectName("small")
        self.btn_open.clicked.connect(lambda: webbrowser.open(self._login_uri))
        self.btn_copy.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(self.code_label.text())
        )
        btn_row.addWidget(self.btn_open)
        btn_row.addWidget(self.btn_copy)
        btn_row.addStretch()
        lc.addLayout(btn_row)
        self.login_card.hide()
        self._login_uri = "https://microsoft.com/devicelogin"
        root.addWidget(self.login_card)

        self.status = QLabel("Sẵn sàng.")
        root.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        root.addWidget(self.bar)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

        bottom = QHBoxLayout()
        self.btn_folder = QPushButton("Mở thư mục chứa file")
        self.btn_folder.setObjectName("small")
        self.btn_folder.clicked.connect(self.open_folder)
        self.btn_folder.hide()
        self.btn_cancel = QPushButton("Huỷ")
        self.btn_cancel.setObjectName("small")
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_cancel.hide()
        bottom.addWidget(self.btn_folder)
        bottom.addStretch()
        bottom.addWidget(self.btn_cancel)
        root.addLayout(bottom)

    # ---------- bắt đầu ----------
    def start_export(self):
        default = str(Path.home() / f"todo_backup_{time.strftime('%Y%m%d_%H%M%S')}.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu file backup", default, "JSON (*.json)"
        )
        if path:
            self._start("export", path)

    def start_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file backup", str(Path.home()), "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            lists = data["lists"]
            n_tasks = sum(len(l.get("tasks", [])) for l in lists)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "File không hợp lệ", f"Không đọc được file backup:\n{e}")
            return

        answer = QMessageBox.question(
            self,
            "Xác nhận import",
            f"File có {len(lists)} list, {n_tasks} task.\n\n"
            "Task sẽ được THÊM vào list cùng tên (script không tự bỏ task trùng). "
            "Import nhiều lần cùng một file sẽ bị trùng task.\n\nTiếp tục?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._start("import", path)

    def _start(self, mode, path):
        self.log_view.clear()
        self.btn_folder.hide()
        self.login_card.hide()
        self.last_export = path if mode == "export" else None
        self._set_running(True)
        self.status.setText("Đang kết nối...")
        self.bar.setRange(0, 0)  # chạy vô định cho đến khi có tiến độ

        self.worker = Worker(self.session, mode, path)
        self.worker.log.connect(self.log_view.appendPlainText)
        self.worker.progress.connect(self.on_progress)
        self.worker.device_code.connect(self.on_device_code)
        self.worker.logged_in.connect(self.on_logged_in)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    # ---------- phản hồi từ worker ----------
    def on_device_code(self, code, uri):
        self._login_uri = uri
        self.code_label.setText(code)
        QGuiApplication.clipboard().setText(code)
        self.login_card.show()
        self.status.setText("Đang chờ bạn đăng nhập trên trình duyệt...")
        webbrowser.open(uri)

    def on_logged_in(self):
        self.login_card.hide()
        self.status.setText("Đăng nhập OK, đang xử lý...")

    def on_progress(self, done, total):
        self.bar.setRange(0, max(total, 1))
        self.bar.setValue(done)
        self.status.setText(f"Đang xử lý {done}/{total}")

    def on_done(self, ok, message):
        self._set_running(False)
        self.login_card.hide()
        self.bar.setRange(0, 1)
        self.bar.setValue(1 if ok else 0)
        self.status.setText(message.splitlines()[0])
        self.log_view.appendPlainText("\n" + message)
        if ok and self.last_export:
            self.btn_folder.show()
        box = QMessageBox.information if ok else QMessageBox.warning
        box(self, "Hoàn tất" if ok else "Chưa xong", message)

    # ---------- khác ----------
    def cancel(self):
        if self.worker:
            self.worker.cancel()
            self.status.setText("Đang huỷ... (có thể mất vài giây)")
            self.btn_cancel.setEnabled(False)

    def open_folder(self):
        if self.last_export:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.last_export).parent)))

    def _set_running(self, running):
        self.btn_export.setEnabled(not running)
        self.btn_import.setEnabled(not running)
        self.btn_cancel.setVisible(running)
        self.btn_cancel.setEnabled(True)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(6000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
