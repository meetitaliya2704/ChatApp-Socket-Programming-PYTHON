# ============================================================
#   SECURECHAT — KivyMD ANDROID APP
#   Direct SSL connection to server_modified.py
#   Testable on desktop: python android_app.py
#   Build APK: buildozer android debug (Linux/WSL)
#
#   Requirements: pip install kivy kivymd
# ============================================================

import socket
import ssl
import threading
import os
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty, BooleanProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.lang import Builder
from kivy.utils import get_color_from_hex
from kivy.animation import Animation

from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.list import MDList, OneLineIconListItem, IconLeftWidget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.navigationdrawer import MDNavigationDrawer, MDNavigationLayout, MDNavigationDrawerMenu
from kivymd.uix.dialog import MDDialog
from kivymd.uix.snackbar import Snackbar

# ─────────────────────────────────────
# CONFIGURATION  (must match server_modified.py)
# ─────────────────────────────────────

HEADER    = 64
PORT      = 8080
FORMAT    = 'utf-8'
BUFFER    = 1024
DEFAULT_SERVER = "192.168.222.1"
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

C_BG          = "#0a0e17"
C_BG_SEC      = "#111827"
C_CARD        = "#1a2035"
C_CARD_ALT    = "#1e2642"
C_ACCENT      = "#00d4aa"
C_ACCENT_DARK = "#00a88a"
C_TEXT        = "#e6edf3"
C_TEXT_MUTED  = "#6b7b8d"
C_BORDER      = "#1e2a3a"
C_ERROR       = "#f85149"
C_SUCCESS     = "#3fb950"
C_WARNING     = "#e3b341"
C_INFO        = "#79c0ff"
C_MSG_SELF    = "#0d2f3f"
C_MSG_OTHER   = "#151d2e"
C_MSG_SERVER  = "#2a1f0a"
C_MSG_PRIVATE = "#1a1a3a"

# For desktop testing, set a phone-like window size
Window.size = (400, 750)

# ─────────────────────────────────────
# KV LANGUAGE (UI Definition)
# ─────────────────────────────────────

KV = '''
#:import get_color_from_hex kivy.utils.get_color_from_hex
#:import dp kivy.metrics.dp
#:import Window kivy.core.window.Window

<RoundedInput@MDTextField>:
    mode: "rectangle"
    line_color_focus: get_color_from_hex("00d4aa")
    line_color_normal: get_color_from_hex("1e2a3a")
    text_color_normal: get_color_from_hex("e6edf3")
    text_color_focus: get_color_from_hex("e6edf3")
    hint_text_color_normal: get_color_from_hex("6b7b8d")
    hint_text_color_focus: get_color_from_hex("00d4aa")
    fill_color_normal: get_color_from_hex("0a0e17")
    fill_color_focus: get_color_from_hex("0a0e17")
    font_size: "14sp"
    radius: [dp(8)]

<MessageBubble@MDCard>:
    orientation: "vertical"
    padding: dp(12), dp(8)
    spacing: dp(4)
    radius: [dp(12)]
    elevation: 0
    size_hint_y: None
    size_hint_x: 0.82
    height: self.minimum_height
    md_bg_color: get_color_from_hex("151d2e")

<AuthScreen>:
    name: "auth"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: get_color_from_hex("0a0e17")
        padding: 0

        # Spacer top
        Widget:
            size_hint_y: 0.15

        # Auth card
        MDBoxLayout:
            orientation: "vertical"
            size_hint_x: 0.88
            size_hint_y: None
            height: self.minimum_height
            pos_hint: {"center_x": 0.5}
            spacing: dp(6)

            # Logo section
            MDLabel:
                text: "🔐"
                font_style: "H3"
                halign: "center"
                size_hint_y: None
                height: dp(56)
                theme_text_color: "Custom"
                text_color: get_color_from_hex("00d4aa")

            MDLabel:
                text: "SecureChat"
                font_style: "H5"
                halign: "center"
                bold: True
                size_hint_y: None
                height: dp(36)
                theme_text_color: "Custom"
                text_color: get_color_from_hex("00d4aa")

            MDLabel:
                text: "End-to-end encrypted messaging"
                font_style: "Caption"
                halign: "center"
                size_hint_y: None
                height: dp(24)
                theme_text_color: "Custom"
                text_color: get_color_from_hex("6b7b8d")

            Widget:
                size_hint_y: None
                height: dp(16)

            # Server IP
            RoundedInput:
                id: server_input
                hint_text: "Server IP Address"
                text: app.server_ip
                icon_left: "server-network"

            # Username
            RoundedInput:
                id: username_input
                hint_text: "Username"
                icon_left: "account"

            # Password
            RoundedInput:
                id: password_input
                hint_text: "Password"
                password: True
                icon_left: "lock"

            Widget:
                size_hint_y: None
                height: dp(8)

            # Buttons
            MDBoxLayout:
                orientation: "horizontal"
                size_hint_y: None
                height: dp(48)
                spacing: dp(10)

                MDRaisedButton:
                    id: login_btn
                    text: "LOGIN"
                    md_bg_color: get_color_from_hex("00d4aa")
                    text_color: get_color_from_hex("0a0e17")
                    font_size: "14sp"
                    size_hint_x: 1
                    elevation: 0
                    on_release: root.do_auth("login")

                MDRaisedButton:
                    id: register_btn
                    text: "REGISTER"
                    md_bg_color: get_color_from_hex("1a2035")
                    text_color: get_color_from_hex("e6edf3")
                    font_size: "14sp"
                    size_hint_x: 1
                    elevation: 0
                    on_release: root.do_auth("register")

            # Status
            MDLabel:
                id: status_label
                text: ""
                font_style: "Caption"
                halign: "center"
                size_hint_y: None
                height: dp(30)
                theme_text_color: "Custom"
                text_color: get_color_from_hex("f85149")

        Widget:
            size_hint_y: 0.3

<ChatScreen>:
    name: "chat"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: get_color_from_hex("0a0e17")

        # Top app bar
        MDTopAppBar:
            title: "# general"
            md_bg_color: get_color_from_hex("111827")
            specific_text_color: get_color_from_hex("e6edf3")
            left_action_items: [["menu", lambda x: root.toggle_drawer()]]
            right_action_items: [["account-group", lambda x: root.request_users()]]
            elevation: 0

        # Messages area
        ScrollView:
            id: scroll_view
            do_scroll_x: False
            bar_width: dp(3)
            bar_color: get_color_from_hex("1e2a3a")

            MDBoxLayout:
                id: messages_box
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(12), dp(12)
                spacing: dp(6)

                # Welcome message
                MDLabel:
                    id: welcome_label
                    text: "💬 Welcome to SecureChat!\\nMessages will appear here."
                    halign: "center"
                    font_style: "Body2"
                    size_hint_y: None
                    height: dp(80)
                    theme_text_color: "Custom"
                    text_color: get_color_from_hex("6b7b8d")

        # Input bar
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(60)
            padding: dp(10), dp(8)
            spacing: dp(8)
            md_bg_color: get_color_from_hex("111827")

            MDTextField:
                id: msg_input
                hint_text: "Type a message..."
                mode: "rectangle"
                size_hint_x: 1
                line_color_focus: get_color_from_hex("00d4aa")
                line_color_normal: get_color_from_hex("1e2a3a")
                text_color_normal: get_color_from_hex("e6edf3")
                text_color_focus: get_color_from_hex("e6edf3")
                hint_text_color_normal: get_color_from_hex("3d4f63")
                fill_color_normal: get_color_from_hex("1a2035")
                fill_color_focus: get_color_from_hex("1a2035")
                font_size: "13sp"
                radius: [dp(8)]
                on_text_validate: root.send_message()

            MDIconButton:
                icon: "send"
                md_bg_color: get_color_from_hex("00d4aa")
                theme_icon_color: "Custom"
                icon_color: get_color_from_hex("0a0e17")
                on_release: root.send_message()

ScreenManager:
    id: screen_manager
    AuthScreen:
        id: auth_screen
    ChatScreen:
        id: chat_screen
'''


# ─────────────────────────────────────
# AUTH SCREEN
# ─────────────────────────────────────

class AuthScreen(Screen):

    def do_auth(self, mode):
        server_ip = self.ids.server_input.text.strip() or DEFAULT_SERVER
        username  = self.ids.username_input.text.strip()
        password  = self.ids.password_input.text.strip()
        status    = self.ids.status_label

        if not username or not password:
            status.text = "Please fill in both fields."
            status.text_color = get_color_from_hex(C_ERROR)
            return

        status.text = "Connecting..."
        status.text_color = get_color_from_hex(C_TEXT_MUTED)

        # Disable buttons
        self.ids.login_btn.disabled = True
        self.ids.register_btn.disabled = True

        # Run auth in background thread
        app = MDApp.get_running_app()
        app.server_ip = server_ip
        threading.Thread(
            target=self._auth_thread,
            args=(mode, server_ip, username, password),
            daemon=True
        ).start()

    def _auth_thread(self, mode, server_ip, username, password):
        app = MDApp.get_running_app()

        try:
            # Create SSL connection
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

            # Try to load cert from app directory or current directory
            cert_path = CERT_FILE
            if hasattr(app, 'user_data_dir') and os.path.exists(os.path.join(app.user_data_dir, CERT_FILE)):
                cert_path = os.path.join(app.user_data_dir, CERT_FILE)

            ctx.load_verify_locations(cert_path)
            ctx.check_hostname = False

            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock = ctx.wrap_socket(raw, server_hostname=server_ip)
            sock.settimeout(10)
            sock.connect((server_ip, PORT))
            sock.settimeout(None)

        except Exception as e:
            Clock.schedule_once(lambda dt: self._auth_result(False, f"Connection failed: {e}"), 0)
            return

        try:
            cmd = REGISTER_MESSAGE if mode == "register" else LOGIN_MESSAGE
            self._send(sock, cmd)
            self._send(sock, username)
            self._send(sock, password)

            response = self._recv(sock)

            if response and "successful" in response.lower():
                app.client_socket = sock
                app.username = username
                Clock.schedule_once(lambda dt: self._auth_result(True, response), 0)
            else:
                sock.close()
                Clock.schedule_once(lambda dt: self._auth_result(False, response or "Auth failed."), 0)

        except Exception as e:
            sock.close()
            Clock.schedule_once(lambda dt: self._auth_result(False, f"Auth error: {e}"), 0)

    def _auth_result(self, success, message):
        status = self.ids.status_label
        self.ids.login_btn.disabled = False
        self.ids.register_btn.disabled = False

        if success:
            status.text = "✓ " + message
            status.text_color = get_color_from_hex(C_SUCCESS)
            # Switch to chat screen after brief delay
            Clock.schedule_once(lambda dt: self._go_to_chat(), 0.5)
        else:
            status.text = message
            status.text_color = get_color_from_hex(C_ERROR)

    def _go_to_chat(self):
        app = MDApp.get_running_app()
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "chat"
        # Start receiver
        chat_screen = self.manager.get_screen("chat")
        chat_screen.start_receiving()

    def _send(self, sock, msg):
        encoded = msg.encode(FORMAT)
        header  = str(len(encoded)).encode(FORMAT).ljust(HEADER)
        sock.send(header)
        sock.send(encoded)

    def _recv(self, sock):
        raw = sock.recv(HEADER)
        if not raw:
            return None
        length = raw.decode(FORMAT).strip()
        if not length:
            return None
        return sock.recv(int(length)).decode(FORMAT)


# ─────────────────────────────────────
# CHAT SCREEN
# ─────────────────────────────────────

class ChatScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.receiver_running = False
        self.users_dialog = None

    def start_receiving(self):
        """Start the background listener thread."""
        self.receiver_running = True
        app = MDApp.get_running_app()

        # Remove welcome label
        try:
            self.ids.welcome_label.text = f"💬 Welcome, {app.username}!\nMessages will appear here."
        except:
            pass

        # Auto-request users
        Clock.schedule_once(lambda dt: self._send_raw(USERS_MESSAGE), 1.5)

        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _receive_loop(self):
        """Continuously receive messages from server."""
        app = MDApp.get_running_app()
        sock = app.client_socket

        while self.receiver_running:
            try:
                raw = sock.recv(HEADER)
                if not raw:
                    break
                length = raw.decode(FORMAT).strip()
                if not length:
                    continue
                msg = sock.recv(int(length)).decode(FORMAT)

                if msg == FILE_MESSAGE:
                    self._skip_file(sock)
                    Clock.schedule_once(
                        lambda dt: self.add_message("📎 A file was shared (not supported on mobile)", "server"), 0
                    )
                    continue

                # Classify
                msg_type = "other"
                if "[SERVER]" in msg:
                    msg_type = "server"
                elif "[PRIVATE" in msg:
                    msg_type = "private"
                elif "[ERROR]" in msg:
                    msg_type = "error"
                elif "[ONLINE USERS]" in msg:
                    msg_type = "users"
                elif "CHAT HISTORY" in msg or "LIVE CHAT" in msg:
                    msg_type = "divider"

                Clock.schedule_once(lambda dt, m=msg, t=msg_type: self.add_message(m, t), 0)

            except Exception as e:
                if self.receiver_running:
                    Clock.schedule_once(
                        lambda dt: self.add_message("🔴 Disconnected from server.", "error"), 0
                    )
                break

    def _skip_file(self, sock):
        """Skip incoming file data to keep protocol in sync."""
        try:
            raw = sock.recv(HEADER)
            filename = sock.recv(int(raw.decode(FORMAT).strip())).decode(FORMAT)
            raw = sock.recv(HEADER)
            filesize = int(sock.recv(int(raw.decode(FORMAT).strip())).decode(FORMAT))
            received = 0
            while received < filesize:
                chunk = sock.recv(min(4096, filesize - received))
                if not chunk:
                    break
                received += len(chunk)
        except:
            pass

    def _send_raw(self, msg):
        """Send a message to the socket server."""
        app = MDApp.get_running_app()
        try:
            encoded = msg.encode(FORMAT)
            header  = str(len(encoded)).encode(FORMAT).ljust(HEADER)
            app.client_socket.send(header)
            app.client_socket.send(encoded)
        except Exception as e:
            self.add_message(f"⚠ Failed to send: {e}", "error")

    def send_message(self):
        """Handle send button / enter key press."""
        msg_input = self.ids.msg_input
        msg = msg_input.text.strip()
        if not msg:
            return
        msg_input.text = ""

        app = MDApp.get_running_app()

        # Handle disconnect
        if msg == DISCONNECT_MESSAGE:
            self.leave_chat()
            return

        # Handle !USERS
        if msg == USERS_MESSAGE:
            self.request_users()
            return

        # Send to server
        self._send_raw(msg)

        # Show own message locally
        if msg.startswith("!DM "):
            parts = msg.split(" ", 2)
            if len(parts) == 3:
                self.add_message(f"[PRIVATE → {parts[1]}] {parts[2]}", "self")
        elif not msg.startswith("!"):
            self.add_message(f"[YOU] {msg}", "self")

    def add_message(self, msg, msg_type="other"):
        """Add a styled message bubble to the chat."""
        box = self.ids.messages_box

        # Remove welcome label on first real message
        if hasattr(self.ids, 'welcome_label') and self.ids.welcome_label.parent:
            try:
                box.remove_widget(self.ids.welcome_label)
            except:
                pass

        # Parse users list
        if msg_type == "users":
            self._parse_users(msg)

        # Choose color
        color_map = {
            "self":    C_MSG_SELF,
            "other":   C_MSG_OTHER,
            "server":  C_MSG_SERVER,
            "private": C_MSG_PRIVATE,
            "error":   "#3a1a1a",
            "users":   C_MSG_OTHER,
            "divider": C_BG,
        }

        text_color_map = {
            "self":    C_ACCENT,
            "other":   C_TEXT,
            "server":  C_WARNING,
            "private": C_INFO,
            "error":   C_ERROR,
            "users":   C_TEXT,
            "divider": C_TEXT_MUTED,
        }

        bg = color_map.get(msg_type, C_MSG_OTHER)
        fg = text_color_map.get(msg_type, C_TEXT)

        # Build bubble card
        card = MDCard(
            orientation="vertical",
            padding=(dp(12), dp(8)),
            spacing=dp(2),
            radius=[dp(12)],
            elevation=0,
            size_hint_y=None,
            size_hint_x=0.85 if msg_type != "divider" else 0.6,
            md_bg_color=get_color_from_hex(bg),
        )

        # Alignment
        if msg_type == "self":
            card.pos_hint = {"right": 0.98}
        elif msg_type in ("server", "divider", "error"):
            card.pos_hint = {"center_x": 0.5}
        else:
            card.pos_hint = {"x": 0.02}

        # Message text
        msg_label = MDLabel(
            text=msg,
            font_style="Body2",
            size_hint_y=None,
            theme_text_color="Custom",
            text_color=get_color_from_hex(fg),
        )
        msg_label.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1]))
        card.add_widget(msg_label)

        # Timestamp
        if msg_type not in ("divider",):
            time_str = datetime.now().strftime("%I:%M %p")
            time_label = MDLabel(
                text=time_str,
                font_style="Overline",
                size_hint_y=None,
                height=dp(14),
                halign="right" if msg_type == "self" else "left",
                theme_text_color="Custom",
                text_color=get_color_from_hex(C_TEXT_MUTED),
            )
            card.add_widget(time_label)

        card.bind(minimum_height=card.setter("height"))
        box.add_widget(card)

        # Auto-scroll to bottom
        Clock.schedule_once(lambda dt: self._scroll_bottom(), 0.1)

    def _scroll_bottom(self):
        self.ids.scroll_view.scroll_y = 0

    def _parse_users(self, msg):
        """Parse and store online users from server response."""
        app = MDApp.get_running_app()
        users = []
        for line in msg.split("\n"):
            line = line.strip()
            if line and line[0].isdigit() and ". " in line:
                name = line.split(". ", 1)[1].strip()
                users.append(name)
        app.online_users = users

    def request_users(self):
        """Request online users list from server."""
        self._send_raw(USERS_MESSAGE)

    def toggle_drawer(self):
        """Show online users in a dialog (drawer alternative)."""
        app = MDApp.get_running_app()
        user_list = app.online_users if app.online_users else ["Tap refresh to load"]

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(4),
            padding=(dp(8), dp(8)),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        for user in user_list:
            is_you = (user == app.username)
            item = OneLineIconListItem(
                text=f"{user} (you)" if is_you else user,
                theme_text_color="Custom",
                text_color=get_color_from_hex(C_ACCENT if is_you else C_TEXT),
                on_release=lambda x, u=user: self._dm_from_list(u),
            )
            icon = IconLeftWidget(
                icon="circle",
                theme_icon_color="Custom",
                icon_color=get_color_from_hex(C_ACCENT),
            )
            item.add_widget(icon)
            content.add_widget(item)

        if self.users_dialog:
            self.users_dialog.dismiss()

        self.users_dialog = MDDialog(
            title="Online Users",
            type="custom",
            content_cls=content,
            md_bg_color=get_color_from_hex(C_BG_SEC),
            buttons=[
                MDFlatButton(
                    text="REFRESH",
                    theme_text_color="Custom",
                    text_color=get_color_from_hex(C_ACCENT),
                    on_release=lambda x: self._refresh_dialog(),
                ),
                MDFlatButton(
                    text="LEAVE CHAT",
                    theme_text_color="Custom",
                    text_color=get_color_from_hex(C_ERROR),
                    on_release=lambda x: self.leave_chat(),
                ),
                MDFlatButton(
                    text="CLOSE",
                    theme_text_color="Custom",
                    text_color=get_color_from_hex(C_TEXT_MUTED),
                    on_release=lambda x: self.users_dialog.dismiss(),
                ),
            ],
        )
        self.users_dialog.open()

    def _refresh_dialog(self):
        self.request_users()
        if self.users_dialog:
            self.users_dialog.dismiss()
        Snackbar(text="Users list refreshing...", duration=1).open()

    def _dm_from_list(self, username):
        app = MDApp.get_running_app()
        if username != app.username:
            self.ids.msg_input.text = f"!DM {username} "
            self.ids.msg_input.focus = True
        if self.users_dialog:
            self.users_dialog.dismiss()

    def leave_chat(self):
        """Gracefully disconnect."""
        self.receiver_running = False
        app = MDApp.get_running_app()
        try:
            self._send_raw(DISCONNECT_MESSAGE)
            app.client_socket.close()
        except:
            pass

        if self.users_dialog:
            self.users_dialog.dismiss()

        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "auth"

        # Reset auth screen
        auth = self.manager.get_screen("auth")
        auth.ids.status_label.text = "You left the chat."
        auth.ids.status_label.text_color = get_color_from_hex(C_WARNING)

        # Clear messages
        self.ids.messages_box.clear_widgets()


# ─────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────

class SecureChatApp(MDApp):
    server_ip     = StringProperty(DEFAULT_SERVER)
    username      = StringProperty("")
    client_socket = None
    online_users  = ListProperty([])

    def build(self):
        self.title = "SecureChat"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.primary_hue = "A400"
        self.theme_cls.material_style = "M3"

        return Builder.load_string(KV)

    def on_stop(self):
        """Cleanup on app close."""
        if self.client_socket:
            try:
                encoded = DISCONNECT_MESSAGE.encode(FORMAT)
                header  = str(len(encoded)).encode(FORMAT).ljust(HEADER)
                self.client_socket.send(header)
                self.client_socket.send(encoded)
                self.client_socket.close()
            except:
                pass


# ─────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────

if __name__ == "__main__":
    SecureChatApp().run()
