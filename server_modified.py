# ============================================================
#   CHAT SERVER — DEPLOYMENT LEVEL
#   Features: Multi-client, File Transfer, Private Messaging,
#             Online Users, Message History, Timestamps,
#             SQLite Database, Authentication, SSL Encryption,
#             Proper Logging
# ============================================================

import socket
import threading
import os
import ssl
import sqlite3
import bcrypt
import logging
from datetime import datetime


# ─────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────

logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s - %(levelname)s - %(message)s",
    handlers = [
        logging.FileHandler("server.log"),   # save to file permanently
        logging.StreamHandler()              # also show in terminal
    ]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────

HEADER           = 64
PORT             = 8080
SERVER           = "0.0.0.0"
ADDR             = (SERVER, PORT)
FORMAT           = 'utf-8'
BUFFER           = 1024
HISTORY_LIMIT    = 10
DATABASE_FILE    = "chat.db"
CERT_FILE        = "cert.pem"
KEY_FILE         = "key.pem"

# special command keywords
DISCONNECT_MESSAGE = "!DISCONNECT"
FILE_MESSAGE       = "!FILE"
USERS_MESSAGE      = "!USERS"
DM_MESSAGE         = "!DM"
REGISTER_MESSAGE   = "!REGISTER"
LOGIN_MESSAGE      = "!LOGIN"


# ─────────────────────────────────────
# SETUP — FOLDERS
# ─────────────────────────────────────

os.makedirs("server_files", exist_ok=True)


# ─────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────

def init_database():
    """Create database tables if they don't exist."""
    conn   = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sender     TEXT NOT NULL,
            message    TEXT NOT NULL,
            timestamp  TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized")


def register_user(username, password):
    """Register a new user. Returns (success, message)."""
    try:
        conn   = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # check if username already exists
        existing = cursor.execute(
            "SELECT username FROM users WHERE username=?", (username,)
        ).fetchone()

        if existing:
            conn.close()
            return False, "Username already taken!"

        # hash the password
        hashed = bcrypt.hashpw(password.encode(FORMAT), bcrypt.gensalt())

        # save to database
        cursor.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
            (username, hashed, get_timestamp())
        )
        conn.commit()
        conn.close()
        logger.info(f"New user registered: {username}")
        return True, "Registration successful!"

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return False, f"Registration error: {str(e)}"


def login_user(username, password):
    """Verify login credentials. Returns (success, message)."""
    try:
        conn   = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # find user in database
        user = cursor.execute(
            "SELECT password FROM users WHERE username=?", (username,)
        ).fetchone()

        conn.close()

        if not user:
            return False, "User not found! Please register first."

        # check password against hash
        if bcrypt.checkpw(password.encode(FORMAT), user[0]):
            logger.info(f"User logged in: {username}")
            return True, "Login successful!"
        else:
            logger.warning(f"Failed login attempt for: {username}")
            return False, "Wrong password!"

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return False, f"Login error: {str(e)}"


def save_message_db(sender, message):
    """Save a message to the database."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.execute(
            "INSERT INTO messages (sender, message, timestamp) VALUES (?, ?, ?)",
            (sender, message, get_timestamp())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save message: {str(e)}")


def get_message_history():
    """Fetch last N messages from database."""
    try:
        conn     = sqlite3.connect(DATABASE_FILE)
        messages = conn.execute(
            "SELECT sender, message, timestamp FROM messages ORDER BY id DESC LIMIT ?",
            (HISTORY_LIMIT,)
        ).fetchall()
        conn.close()
        messages.reverse()  # show oldest first
        return messages
    except Exception as e:
        logger.error(f"Failed to fetch history: {str(e)}")
        return []


# ─────────────────────────────────────
# SSL SETUP
# ─────────────────────────────────────

def create_ssl_context():
    """Create SSL context for secure connections."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT_FILE, KEY_FILE)
    logger.info("SSL context created")
    return context


# ─────────────────────────────────────
# SERVER SOCKET SETUP
# ─────────────────────────────────────

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(ADDR)

clients   = []
usernames = []


# ─────────────────────────────────────
# HELPER: TIMESTAMP
# ─────────────────────────────────────

def get_timestamp():
    return datetime.now().strftime("%I:%M %p")


# ─────────────────────────────────────
# CORE: SEND & RECEIVE
# ─────────────────────────────────────

def send_message(conn, msg):
    """Send a message to a specific client with a fixed-size header."""
    try:
        message     = msg.encode(FORMAT)
        msg_length  = len(message)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b' ' * (HEADER - len(send_length))
        conn.send(send_length)
        conn.send(message)
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")


def receive_message(conn):
    """Receive a message from a client. Returns None if connection is lost."""
    try:
        msg_length = conn.recv(HEADER).decode(FORMAT)
        if msg_length:
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode(FORMAT)
            return msg
        return None
    except:
        return None


# ─────────────────────────────────────
# BROADCAST
# ─────────────────────────────────────

def broadcast(conn, msg):
    """Send a timestamped message to all clients except the sender."""
    timestamped_msg = f"[{get_timestamp()}] {msg}"
    for client in clients:
        if client != conn:
            send_message(client, timestamped_msg)


def broadcast_file(filename, filesize, filedata, conn):
    """Send a file to all clients except the sender."""
    for client in clients:
        if client != conn:
            send_message(client, FILE_MESSAGE)
            send_message(client, filename)
            send_message(client, str(filesize))
            client.send(filedata)


# ─────────────────────────────────────
# FILE TRANSFER
# ─────────────────────────────────────

def receive_file(conn):
    """Receive a file from a client in chunks."""
    filename = receive_message(conn)
    filesize = int(receive_message(conn))

    filedata = b''
    while len(filedata) < filesize:
        chunk = conn.recv(BUFFER)
        if not chunk:
            break
        filedata += chunk

    return filename, filesize, filedata


# ─────────────────────────────────────
# PRIVATE MESSAGING
# ─────────────────────────────────────

def send_private_message(sender_username, target_username, msg):
    """Send a private message from one user to another."""
    timestamp = get_timestamp()

    if target_username not in usernames:
        sender_index = usernames.index(sender_username)
        send_message(clients[sender_index], f"[{timestamp}] [ERROR] User '{target_username}' not found!")
        return

    target_index = usernames.index(target_username)
    send_message(clients[target_index], f"[{timestamp}] [PRIVATE] [{sender_username}] {msg}")

    sender_index = usernames.index(sender_username)
    send_message(clients[sender_index], f"[{timestamp}] [PRIVATE -> {target_username}] {msg}")
    logger.info(f"Private message from {sender_username} to {target_username}")


# ─────────────────────────────────────
# MESSAGE HISTORY
# ─────────────────────────────────────

def send_history(conn):
    """Send the last N messages from database to a newly joined client."""
    messages = get_message_history()

    if not messages:
        send_message(conn, "[NO HISTORY YET]")
        return

    send_message(conn, "\n------- CHAT HISTORY -------")
    for sender, message, timestamp in messages:
        send_message(conn, f"[{timestamp}] [{sender}] {message}")
    send_message(conn, "----------- LIVE CHAT -----------\n")


# ─────────────────────────────────────
# AUTHENTICATION HANDLER
# ─────────────────────────────────────

def authenticate_client(conn):
    """Handle client registration or login. Returns username if successful."""
    while True:
        auth_type = receive_message(conn)

        if auth_type is None:
            return None

        if auth_type == REGISTER_MESSAGE:
            username = receive_message(conn)
            password = receive_message(conn)

            success, message = register_user(username, password)
            send_message(conn, message)

            if success:
                return username

        elif auth_type == LOGIN_MESSAGE:
            username = receive_message(conn)
            password = receive_message(conn)

            success, message = login_user(username, password)
            send_message(conn, message)

            if success:
                return username

        else:
            send_message(conn, "[ERROR] Invalid auth type! Use !REGISTER or !LOGIN")
            logger.warning(f"Invalid auth type received: {auth_type}")


# ─────────────────────────────────────
# CLIENT HANDLER
# ─────────────────────────────────────

def handle_client(conn, addr):
    logger.info(f"New connection from {addr}")

    # authenticate first
    username = authenticate_client(conn)

    if not username:
        logger.warning(f"Authentication failed from {addr}")
        conn.close()
        return

    # check if user already connected
    if username in usernames:
        send_message(conn, "[ERROR] This account is already logged in!")
        logger.warning(f"Duplicate login attempt for {username}")
        conn.close()
        return

    usernames.append(username)
    clients.append(conn)
    logger.info(f"{username} authenticated and joined from {addr}")

    # send history and announce join
    send_history(conn)
    broadcast(conn, f"[SERVER] {username} joined the chat!")
    save_message_db("SERVER", f"{username} joined the chat!")

    # main message loop
    connected = True
    while connected:
        msg = receive_message(conn)

        if msg is None:
            connected = False

        elif msg == DISCONNECT_MESSAGE:
            connected = False

        elif msg.startswith(DM_MESSAGE):
            parts = msg.split(" ", 2)
            if len(parts) < 3:
                send_message(conn, f"[{get_timestamp()}] [ERROR] Usage: !DM username message")
            else:
                send_private_message(username, parts[1], parts[2])

        elif msg == USERS_MESSAGE:
            timestamp  = get_timestamp()
            users_list = f"\n[{timestamp}] [ONLINE USERS]\n"
            for i, user in enumerate(usernames, 1):
                users_list += f"  {i}. {user}\n"
            users_list += f"  Total: {len(usernames)} users online"
            send_message(conn, users_list)

        elif msg == FILE_MESSAGE:
            filename, filesize, filedata = receive_file(conn)
            logger.info(f"{username} sent file: {filename} ({filesize} bytes)")

            with open(f"server_files/server_received_{filename}", 'wb') as f:
                f.write(filedata)

            broadcast_file(filename, filesize, filedata, conn)
            broadcast(conn, f"[{username}] sent a file: {filename}")

        else:
            logger.info(f"{username}: {msg}")
            save_message_db(username, msg)
            broadcast(conn, f"[{username}] {msg}")

    # cleanup on disconnect
    broadcast(conn, f"[SERVER] {username} left the chat!")
    save_message_db("SERVER", f"{username} left the chat!")

    if username in usernames:
        clients.remove(conn)
        usernames.remove(username)

    conn.close()
    logger.info(f"{username} disconnected")


# ─────────────────────────────────────
# START SERVER
# ─────────────────────────────────────

def start():
    init_database()

    ssl_context   = create_ssl_context()
    secure_server = ssl_context.wrap_socket(server, server_side=True)

    secure_server.listen()
    logger.info(f"Secure server listening on port {PORT}")

    while True:
        try:
            conn, addr = secure_server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
            logger.info(f"Active connections: {threading.active_count() - 1}")
        except Exception as e:
            logger.error(f"Server error: {str(e)}")


logger.info("Secure server is starting...")
start()