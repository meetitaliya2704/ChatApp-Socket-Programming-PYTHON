# ============================================================
#   CHAT SERVER — ASYNCIO (HIGH PERFORMANCE)
#   Features: Multi-client, File Transfer, Private Messaging,
#             Online Users, Message History, Timestamps,
#             SQLite Database, Authentication, SSL Encryption,
#             Proper Logging
#
#   Same protocol as server_modified.py — all existing clients
#   work without changes.
# ============================================================

import asyncio
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
# CONNECTED CLIENTS (replaces parallel lists)
# ─────────────────────────────────────
# { "username": (reader, writer) }
connected_clients = {}


# ─────────────────────────────────────
# HELPER: TIMESTAMP
# ─────────────────────────────────────

def get_timestamp():
    return datetime.now().strftime("%I:%M %p")


# ─────────────────────────────────────
# DATABASE SETUP (no change — pure SQLite)
# ─────────────────────────────────────

def init_database():
    """Create database tables if they don't exist."""
    conn   = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

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
    """Register a new user. Returns (success, message).
    Called via asyncio.to_thread() — runs in background thread.
    """
    try:
        conn   = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        existing = cursor.execute(
            "SELECT username FROM users WHERE username=?", (username,)
        ).fetchone()

        if existing:
            conn.close()
            return False, "Username already taken!"

        hashed = bcrypt.hashpw(password.encode(FORMAT), bcrypt.gensalt())

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
    """Verify login credentials. Returns (success, message).
    Called via asyncio.to_thread() — runs in background thread.
    """
    try:
        conn   = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        user = cursor.execute(
            "SELECT password FROM users WHERE username=?", (username,)
        ).fetchone()

        conn.close()

        if not user:
            return False, "User not found! Please register first."

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
    """Save a message to the database.
    Called via asyncio.to_thread() — runs in background thread.
    """
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
        messages.reverse()
        return messages
    except Exception as e:
        logger.error(f"Failed to fetch history: {str(e)}")
        return []


# ─────────────────────────────────────
# SSL SETUP (no change)
# ─────────────────────────────────────

def create_ssl_context():
    """Create SSL context for secure connections."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT_FILE, KEY_FILE)
    logger.info("SSL context created")
    return context


# ─────────────────────────────────────
# CORE: ASYNC SEND & RECEIVE
# ─────────────────────────────────────

async def send_message(writer, msg):
    """Send a message to a specific client with a fixed-size header."""
    try:
        message     = msg.encode(FORMAT)
        msg_length  = len(message)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b' ' * (HEADER - len(send_length))
        writer.write(send_length + message)
        await writer.drain()
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")


async def receive_message(reader):
    """Receive a message from a client. Returns None if connection is lost."""
    try:
        header = await reader.readexactly(HEADER)
        msg_length = int(header.decode(FORMAT).strip())
        data = await reader.readexactly(msg_length)
        return data.decode(FORMAT)
    except (asyncio.IncompleteReadError, ConnectionError, ValueError):
        return None
    except Exception:
        return None


# ─────────────────────────────────────
# BROADCAST
# ─────────────────────────────────────

async def broadcast(sender_username, msg):
    """Send a timestamped message to all clients except the sender."""
    timestamped_msg = f"[{get_timestamp()}] {msg}"
    for username, (_, writer) in list(connected_clients.items()):
        if username != sender_username:
            await send_message(writer, timestamped_msg)


async def broadcast_file(filename, filesize, filedata, sender_username):
    """Send a file to all clients except the sender."""
    for username, (_, writer) in list(connected_clients.items()):
        if username != sender_username:
            await send_message(writer, FILE_MESSAGE)
            await send_message(writer, filename)
            await send_message(writer, str(filesize))
            writer.write(filedata)
            await writer.drain()


# ─────────────────────────────────────
# FILE TRANSFER
# ─────────────────────────────────────

async def receive_file(reader):
    """Receive a file from a client in chunks."""
    filename = await receive_message(reader)
    filesize = int(await receive_message(reader))

    filedata = b''
    while len(filedata) < filesize:
        remaining = filesize - len(filedata)
        chunk = await reader.read(min(BUFFER, remaining))
        if not chunk:
            break
        filedata += chunk

    return filename, filesize, filedata


# ─────────────────────────────────────
# PRIVATE MESSAGING
# ─────────────────────────────────────

async def send_private_message(sender_username, target_username, msg):
    """Send a private message from one user to another."""
    timestamp = get_timestamp()

    if target_username not in connected_clients:
        _, sender_writer = connected_clients[sender_username]
        await send_message(sender_writer, f"[{timestamp}] [ERROR] User '{target_username}' not found!")
        return

    _, target_writer = connected_clients[target_username]
    await send_message(target_writer, f"[{timestamp}] [PRIVATE] [{sender_username}] {msg}")

    _, sender_writer = connected_clients[sender_username]
    await send_message(sender_writer, f"[{timestamp}] [PRIVATE -> {target_username}] {msg}")
    logger.info(f"Private message from {sender_username} to {target_username}")


# ─────────────────────────────────────
# MESSAGE HISTORY
# ─────────────────────────────────────

async def send_history(writer):
    """Send the last N messages from database to a newly joined client."""
    messages = get_message_history()

    if not messages:
        await send_message(writer, "[NO HISTORY YET]")
        return

    await send_message(writer, "\n------- CHAT HISTORY -------")
    for sender, message, timestamp in messages:
        await send_message(writer, f"[{timestamp}] [{sender}] {message}")
    await send_message(writer, "----------- LIVE CHAT -----------\n")


# ─────────────────────────────────────
# AUTHENTICATION HANDLER
# ─────────────────────────────────────

async def authenticate_client(reader, writer):
    """Handle client registration or login. Returns username if successful."""
    while True:
        auth_type = await receive_message(reader)

        if auth_type is None:
            return None

        if auth_type == REGISTER_MESSAGE:
            username = await receive_message(reader)
            password = await receive_message(reader)

            # offload bcrypt to thread so it doesn't block the event loop
            success, message = await asyncio.to_thread(register_user, username, password)
            await send_message(writer, message)

            if success:
                return username

        elif auth_type == LOGIN_MESSAGE:
            username = await receive_message(reader)
            password = await receive_message(reader)

            # offload bcrypt to thread so it doesn't block the event loop
            success, message = await asyncio.to_thread(login_user, username, password)
            await send_message(writer, message)

            if success:
                return username

        else:
            await send_message(writer, "[ERROR] Invalid auth type! Use !REGISTER or !LOGIN")
            logger.warning(f"Invalid auth type received: {auth_type}")


# ─────────────────────────────────────
# CLIENT HANDLER
# ─────────────────────────────────────

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    logger.info(f"New connection from {addr}")

    # authenticate first
    username = await authenticate_client(reader, writer)

    if not username:
        logger.warning(f"Authentication failed from {addr}")
        writer.close()
        await writer.wait_closed()
        return

    # check if user already connected
    if username in connected_clients:
        await send_message(writer, "[ERROR] This account is already logged in!")
        logger.warning(f"Duplicate login attempt for {username}")
        writer.close()
        await writer.wait_closed()
        return

    # register this client
    connected_clients[username] = (reader, writer)
    logger.info(f"{username} authenticated and joined from {addr}")

    # send history and announce join
    await send_history(writer)
    await broadcast(username, f"[SERVER] {username} joined the chat!")
    await asyncio.to_thread(save_message_db, "SERVER", f"{username} joined the chat!")

    # main message loop
    try:
        while True:
            msg = await receive_message(reader)

            if msg is None:
                break

            elif msg == DISCONNECT_MESSAGE:
                break

            elif msg.startswith(DM_MESSAGE):
                parts = msg.split(" ", 2)
                if len(parts) < 3:
                    await send_message(writer, f"[{get_timestamp()}] [ERROR] Usage: !DM username message")
                else:
                    await send_private_message(username, parts[1], parts[2])

            elif msg == USERS_MESSAGE:
                timestamp  = get_timestamp()
                users_list = f"\n[{timestamp}] [ONLINE USERS]\n"
                for i, user in enumerate(connected_clients.keys(), 1):
                    users_list += f"  {i}. {user}\n"
                users_list += f"  Total: {len(connected_clients)} users online"
                await send_message(writer, users_list)

            elif msg == FILE_MESSAGE:
                filename, filesize, filedata = await receive_file(reader)
                logger.info(f"{username} sent file: {filename} ({filesize} bytes)")

                # save file on server (offload to thread)
                await asyncio.to_thread(_save_file, filename, filedata)

                await broadcast_file(filename, filesize, filedata, username)
                await broadcast(username, f"[{username}] sent a file: {filename}")

            else:
                logger.info(f"{username}: {msg}")
                await asyncio.to_thread(save_message_db, username, msg)
                await broadcast(username, f"[{username}] {msg}")

    except Exception as e:
        logger.error(f"Error handling {username}: {str(e)}")

    # cleanup on disconnect
    await broadcast(username, f"[SERVER] {username} left the chat!")
    await asyncio.to_thread(save_message_db, "SERVER", f"{username} left the chat!")

    if username in connected_clients:
        del connected_clients[username]

    writer.close()
    await writer.wait_closed()
    logger.info(f"{username} disconnected")


def _save_file(filename, filedata):
    """Helper to save received file (runs in thread)."""
    with open(f"server_files/server_received_{filename}", 'wb') as f:
        f.write(filedata)


# ─────────────────────────────────────
# START SERVER
# ─────────────────────────────────────

async def main():
    init_database()

    ssl_context = create_ssl_context()

    server = await asyncio.start_server(
        handle_client,
        SERVER, PORT,
        ssl=ssl_context
    )

    logger.info(f"Secure server listening on port {PORT}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    logger.info("Secure async server is starting...")
    asyncio.run(main())
