# ============================================================
#   SECURECHAT — PyQt6 GUI CLIENT
#   Drop-in replacement for the CLI client.py
#   Requirements: pip install PyQt6 bcrypt
# ============================================================

import sys
import socket
import ssl
import threading
import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QStackedWidget, QFrame, QFileDialog,
    QMessageBox, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor, QIcon


# ─────────────────────────────────────
# CONFIGURATION  (match your server.py)
# ─────────────────────────────────────

HEADER    = 64
PORT      = 8080
FORMAT    = 'utf-8'
BUFFER    = 1024
SERVER    = "192.168.1.6"   # ← change to your server IP
ADDR      = (SERVER, PORT)
CERT_FILE = "cert.pem"

DISCONNECT_MESSAGE = "!DISCONNECT"
FILE_MESSAGE       = "!FILE"
USERS_MESSAGE      = "!USERS"
DM_MESSAGE         = "!DM"
REGISTER_MESSAGE   = "!REGISTER"
LOGIN_MESSAGE      = "!LOGIN"


# ─────────────────────────────────────
# COLOUR PALETTE
# ─────────────────────────────────────

DARK_BG      = "#0d1117"
PANEL_BG     = "#161b22"
CARD_BG      = "#1c2128"
ACCENT       = "#00d4aa"
ACCENT_DARK  = "#00a88a"
TEXT_PRIMARY = "#e6edf3"
TEXT_MUTED   = "#7d8590"
BORDER       = "#30363d"
MSG_SELF     = "#1a3a4a"
MSG_OTHER    = "#1c2128"
MSG_SERVER   = "#2a1f0a"
MSG_PRIVATE  = "#1a1a3a"
ERROR_COLOR  = "#f85149"
SUCCESS      = "#3fb950"


# ─────────────────────────────────────
# NETWORK THREAD
# ─────────────────────────────────────

class NetworkThread(QThread):
    """Runs in background — receives all messages from server."""
    message_received = pyqtSignal(str)
    file_received    = pyqtSignal(str)
    disconnected     = pyqtSignal()

    def __init__(self, client_socket):
        super().__init__()
        self.client = client_socket
        self.running = True

    def run(self):
        while self.running:
            try:
                msg_length = self.client.recv(HEADER).decode(FORMAT)
                if not msg_length:
                    break
                msg = self.client.recv(int(msg_length)).decode(FORMAT)

                if msg == FILE_MESSAGE:
                    filename = self._receive_file()
                    self.file_received.emit(filename)
                else:
                    self.message_received.emit(msg)
            except:
                if self.running:
                    self.disconnected.emit()
                break

    def _receive_file(self):
        """Receive incoming file and save to received_files/"""
        os.makedirs("received_files", exist_ok=True)
        ml = self.client.recv(HEADER).decode(FORMAT)
        filename = self.client.recv(int(ml)).decode(FORMAT)
        ml = self.client.recv(HEADER).decode(FORMAT)
        filesize = int(self.client.recv(int(ml)).decode(FORMAT))
        data = b''
        while len(data) < filesize:
            chunk = self.client.recv(BUFFER)
            if not chunk:
                break
            data += chunk
        path = f"received_files/received_{filename}"
        with open(path, 'wb') as f:
            f.write(data)
        return filename

    def stop(self):
        self.running = False


# ─────────────────────────────────────
# STYLED WIDGETS
# ─────────────────────────────────────

def styled_input(placeholder="", password=False):
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    if password:
        w.setEchoMode(QLineEdit.EchoMode.Password)
    w.setStyleSheet(f"""
        QLineEdit {{
            background: {CARD_BG};
            color: {TEXT_PRIMARY};
            border: 1.5px solid {BORDER};
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 14px;
            font-family: 'Consolas', monospace;
        }}
        QLineEdit:focus {{
            border: 1.5px solid {ACCENT};
        }}
        QLineEdit::placeholder {{
            color: {TEXT_MUTED};
        }}
    """)
    return w


def styled_button(text, primary=True):
    w = QPushButton(text)
    bg   = ACCENT      if primary else CARD_BG
    bg_h = ACCENT_DARK if primary else BORDER
    fg   = DARK_BG     if primary else TEXT_PRIMARY
    w.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: 1.5px solid {bg};
            border-radius: 8px;
            padding: 10px 22px;
            font-size: 14px;
            font-weight: 600;
            font-family: 'Segoe UI', sans-serif;
        }}
        QPushButton:hover {{
            background: {bg_h};
            border-color: {bg_h};
        }}
        QPushButton:pressed {{
            background: {ACCENT_DARK};
        }}
    """)
    return w


# ─────────────────────────────────────
# AUTH SCREEN
# ─────────────────────────────────────

class AuthScreen(QWidget):
    auth_success = pyqtSignal(str, object)   # username, socket

    def __init__(self):
        super().__init__()
        self.client = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {DARK_BG};")
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedWidth(400)
        card.setStyleSheet(f"""
            QFrame {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 212, 170, 60))
        shadow.setOffset(0, 8)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(16)

        # logo / title
        title = QLabel("🔐 SecureChat")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 26px;
            font-weight: 700;
            color: {ACCENT};
            font-family: 'Consolas', monospace;
            letter-spacing: 1px;
        """)

        subtitle = QLabel("End-to-end encrypted messaging")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")

        # server info
        server_row = QHBoxLayout()
        self.server_input = styled_input(f"Server IP ({SERVER})")
        self.server_input.setText(SERVER)
        server_row.addWidget(QLabel("🌐"))
        server_row.addWidget(self.server_input)

        # fields
        self.username_input = styled_input("Username")
        self.password_input = styled_input("Password", password=True)

        # status
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"font-size: 12px; color: {ERROR_COLOR};")

        # buttons
        btn_row = QHBoxLayout()
        self.login_btn    = styled_button("Login",    primary=True)
        self.register_btn = styled_button("Register", primary=False)
        btn_row.addWidget(self.login_btn)
        btn_row.addWidget(self.register_btn)

        self.login_btn.clicked.connect(lambda: self._attempt_auth("login"))
        self.register_btn.clicked.connect(lambda: self._attempt_auth("register"))

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addLayout(server_row)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.status_label)
        layout.addLayout(btn_row)

        outer.addWidget(card)

    def _set_status(self, msg, color=ERROR_COLOR):
        self.status_label.setStyleSheet(f"font-size: 12px; color: {color};")
        self.status_label.setText(msg)

    def _attempt_auth(self, mode):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        server_ip = self.server_input.text().strip() or SERVER

        if not username or not password:
            self._set_status("Please fill in both fields.")
            return

        self._set_status("Connecting...", TEXT_MUTED)
        QApplication.processEvents()

        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_verify_locations(CERT_FILE)
            ctx.check_hostname = False

            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client = ctx.wrap_socket(raw, server_hostname=server_ip)
            self.client.connect((server_ip, PORT))
        except Exception as e:
            self._set_status(f"Connection failed: {e}")
            return

        try:
            cmd = REGISTER_MESSAGE if mode == "register" else LOGIN_MESSAGE
            self._send(cmd)
            self._send(username)
            self._send(password)

            ml  = self.client.recv(HEADER).decode(FORMAT)
            res = self.client.recv(int(ml)).decode(FORMAT)

            if "successful" in res.lower():
                self._set_status("✓ " + res, SUCCESS)
                QTimer.singleShot(400, lambda: self.auth_success.emit(username, self.client))
            else:
                self._set_status(res)
        except Exception as e:
            self._set_status(f"Auth error: {e}")

    def _send(self, msg):
        encoded = msg.encode(FORMAT)
        header  = str(len(encoded)).encode(FORMAT).ljust(HEADER)
        self.client.send(header)
        self.client.send(encoded)


# ─────────────────────────────────────
# CHAT SCREEN
# ─────────────────────────────────────

class ChatScreen(QWidget):
    def __init__(self, username, client_socket):
        super().__init__()
        self.username = username
        self.client   = client_socket
        self._build_ui()
        self._start_network()

    # ── UI BUILD ──────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"background: {DARK_BG};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._sidebar())
        root.addWidget(self._main_area(), stretch=1)

    def _sidebar(self):
        panel = QFrame()
        panel.setFixedWidth(220)
        panel.setStyleSheet(f"""
            QFrame {{
                background: {PANEL_BG};
                border-right: 1px solid {BORDER};
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # header
        header = QFrame()
        header.setStyleSheet(f"background: {CARD_BG}; border-bottom: 1px solid {BORDER};")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(16, 16, 16, 16)

        logo = QLabel("🔐 SecureChat")
        logo.setStyleSheet(f"color: {ACCENT}; font-size: 15px; font-weight: 700; font-family: 'Consolas', monospace;")

        user_label = QLabel(f"@{self.username}")
        user_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")

        h_layout.addWidget(logo)
        h_layout.addWidget(user_label)

        # online users
        online_label = QLabel("  ONLINE USERS")
        online_label.setStyleSheet(f"""
            color: {TEXT_MUTED};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 12px 16px 4px;
            background: {PANEL_BG};
        """)

        self.users_list = QListWidget()
        self.users_list.setStyleSheet(f"""
            QListWidget {{
                background: {PANEL_BG};
                border: none;
                color: {TEXT_PRIMARY};
                font-size: 13px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-radius: 6px;
                margin: 1px 4px;
            }}
            QListWidget::item:hover {{
                background: {CARD_BG};
                cursor: pointer;
            }}
            QListWidget::item:selected {{
                background: {CARD_BG};
            }}
        """)
        self.users_list.itemDoubleClicked.connect(self._dm_from_sidebar)

        # bottom buttons
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background: {PANEL_BG}; border-top: 1px solid {BORDER};")
        btn_layout = QVBoxLayout(btn_frame)
        btn_layout.setContentsMargins(12, 12, 12, 12)
        btn_layout.setSpacing(6)

        refresh_btn = styled_button("↻ Refresh Users", primary=False)
        refresh_btn.clicked.connect(self._refresh_users)
        refresh_btn.setFixedHeight(34)

        leave_btn = styled_button("⏻ Leave Chat", primary=False)
        leave_btn.clicked.connect(self._disconnect)
        leave_btn.setFixedHeight(34)
        leave_btn.setStyleSheet(leave_btn.styleSheet() + f"QPushButton {{ color: {ERROR_COLOR}; }}")

        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(leave_btn)

        layout.addWidget(header)
        layout.addWidget(online_label)
        layout.addWidget(self.users_list, stretch=1)
        layout.addWidget(btn_frame)

        return panel

    def _main_area(self):
        frame = QFrame()
        frame.setStyleSheet(f"background: {DARK_BG};")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # top bar
        topbar = QFrame()
        topbar.setFixedHeight(56)
        topbar.setStyleSheet(f"background: {PANEL_BG}; border-bottom: 1px solid {BORDER};")
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(20, 0, 20, 0)

        channel = QLabel("# general")
        channel.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: 600;")

        hint = QLabel("!DM user msg  •  !SENDFILE path  •  !USERS")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

        tb_layout.addWidget(channel)
        tb_layout.addStretch()
        tb_layout.addWidget(hint)

        # messages area
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet(f"""
            QTextEdit {{
                background: {DARK_BG};
                color: {TEXT_PRIMARY};
                border: none;
                padding: 16px 20px;
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
                line-height: 1.6;
            }}
            QScrollBar:vertical {{
                background: {PANEL_BG};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER};
                border-radius: 3px;
            }}
        """)

        # input row
        input_frame = QFrame()
        input_frame.setStyleSheet(f"background: {PANEL_BG}; border-top: 1px solid {BORDER};")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(8)

        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText(f"Message as @{self.username}  •  !DM user msg  •  !SENDFILE path")
        self.msg_input.setStyleSheet(f"""
            QLineEdit {{
                background: {CARD_BG};
                color: {TEXT_PRIMARY};
                border: 1.5px solid {BORDER};
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self.msg_input.returnPressed.connect(self._send_message)

        file_btn = QPushButton("📎")
        file_btn.setFixedSize(40, 40)
        file_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CARD_BG};
                color: {TEXT_PRIMARY};
                border: 1.5px solid {BORDER};
                border-radius: 8px;
                font-size: 16px;
            }}
            QPushButton:hover {{ border-color: {ACCENT}; }}
        """)
        file_btn.clicked.connect(self._send_file_dialog)

        send_btn = QPushButton("Send  ↑")
        send_btn.setFixedHeight(40)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: {DARK_BG};
                border: none;
                border-radius: 8px;
                padding: 0 20px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: {ACCENT_DARK}; }}
        """)
        send_btn.clicked.connect(self._send_message)

        input_layout.addWidget(self.msg_input, stretch=1)
        input_layout.addWidget(file_btn)
        input_layout.addWidget(send_btn)

        layout.addWidget(topbar)
        layout.addWidget(self.chat_area, stretch=1)
        layout.addWidget(input_frame)

        return frame

    # ── NETWORK ───────────────────────

    def _start_network(self):
        self.net = NetworkThread(self.client)
        self.net.message_received.connect(self._on_message)
        self.net.file_received.connect(self._on_file)
        self.net.disconnected.connect(self._on_disconnected)
        self.net.start()

    def _send_raw(self, msg):
        try:
            encoded = msg.encode(FORMAT)
            header  = str(len(encoded)).encode(FORMAT).ljust(HEADER)
            self.client.send(header)
            self.client.send(encoded)
        except:
            self._append_system("⚠ Failed to send message.")

    # ── ACTIONS ───────────────────────

    def _send_message(self):
        msg = self.msg_input.text().strip()
        if not msg:
            return
        self.msg_input.clear()

        if msg == DISCONNECT_MESSAGE:
            self._disconnect()
            return

        if msg.startswith("!SENDFILE "):
            path = msg[10:].strip()
            self._send_file(path)
            return

        self._send_raw(msg)

        # show own message immediately
        if msg.startswith("!DM "):
            parts = msg.split(" ", 2)
            if len(parts) == 3:
                self._append_message(f"[YOU → {parts[1]}] {parts[2]}", "private")
        elif not msg.startswith("!"):
            self._append_message(f"[YOU] {msg}", "self")

    def _refresh_users(self):
        self._send_raw(USERS_MESSAGE)

    def _send_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Send")
        if path:
            self._send_file(path)

    def _send_file(self, filepath):
        if not os.path.exists(filepath):
            self._append_system(f"⚠ File not found: {filepath}")
            return
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            data = f.read()
        self._send_raw(FILE_MESSAGE)
        self._send_raw(filename)
        self._send_raw(str(filesize))
        self.client.send(data)
        self._append_system(f"📤 Sent file: {filename} ({filesize:,} bytes)")

    def _dm_from_sidebar(self, item):
        user = item.text().replace("● ", "").strip()
        if user != self.username:
            self.msg_input.setText(f"!DM {user} ")
            self.msg_input.setFocus()

    def _disconnect(self):
        self._send_raw(DISCONNECT_MESSAGE)
        self.net.stop()
        self.client.close()
        QApplication.quit()

    # ── MESSAGE DISPLAY ───────────────

    def _on_message(self, msg):
        # update users list if it's a users response
        if "[ONLINE USERS]" in msg:
            self._parse_users(msg)
        self._append_message(msg, self._classify(msg))

    def _on_file(self, filename):
        self._append_system(f"📥 Received file saved as: received_{filename}")

    def _on_disconnected(self):
        self._append_system("🔴 Disconnected from server.")

    def _classify(self, msg):
        if "[SERVER]" in msg:
            return "server"
        if "[PRIVATE" in msg:
            return "private"
        if "[YOU]" in msg or "[YOU →" in msg:
            return "self"
        return "other"

    def _append_message(self, msg, kind="other"):
        colors = {
            "self":    (MSG_SELF,    ACCENT,       "You"),
            "other":   (MSG_OTHER,   TEXT_PRIMARY, ""),
            "server":  (MSG_SERVER,  "#e3b341",    ""),
            "private": (MSG_PRIVATE, "#79c0ff",    ""),
        }
        bg, color, _ = colors.get(kind, colors["other"])

        ts = datetime.now().strftime("%I:%M %p")

        self.chat_area.append(
            f'<div style="background:{bg}; border-radius:8px; padding:8px 12px; '
            f'margin:3px 0; color:{color}; font-size:13px;">'
            f'<span style="color:{TEXT_MUTED}; font-size:11px;">{ts}</span>  {msg}'
            f'</div>'
        )
        self.chat_area.moveCursor(QTextCursor.MoveOperation.End)

    def _append_system(self, msg):
        self._append_message(msg, "server")

    def _parse_users(self, msg):
        self.users_list.clear()
        for line in msg.splitlines():
            line = line.strip()
            if line and line[0].isdigit() and ". " in line:
                name = line.split(". ", 1)[1].strip()
                item = QListWidgetItem(f"● {name}")
                item.setForeground(QColor(ACCENT if name == self.username else TEXT_PRIMARY))
                self.users_list.addItem(item)


# ─────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecureChat 🔐")
        self.setMinimumSize(960, 640)
        self.resize(1100, 700)
        self._apply_dark_title_bar()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.auth_screen = AuthScreen()
        self.auth_screen.auth_success.connect(self._on_auth_success)
        self.stack.addWidget(self.auth_screen)

    def _on_auth_success(self, username, client_socket):
        chat = ChatScreen(username, client_socket)
        self.stack.addWidget(chat)
        self.stack.setCurrentWidget(chat)
        self.setWindowTitle(f"SecureChat 🔐  —  @{username}")

    def _apply_dark_title_bar(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {DARK_BG};
            }}
        """)


# ─────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(DARK_BG))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base,            QColor(PANEL_BG))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(CARD_BG))
    palette.setColor(QPalette.ColorRole.Text,            QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button,          QColor(CARD_BG))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(DARK_BG))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())