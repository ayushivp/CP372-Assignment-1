
import os

CHUNK_SIZE = 4096
SERVER_FILES = "server_files"


def send_line(conn, text):
    """Send a text response ending with a newline."""
    conn.sendall((text + "\n").encode("utf-8"))


def recv_line(reader):
    """Receive one complete command or text line."""
    line = reader.readline()

    if not line:
        return None

    return line.decode("utf-8").rstrip("\r\n")


def safe_filename(filename):
    """Allow only a filename, not a directory path."""
    if not filename or filename in (".", ".."):
        return None

    if "/" in filename or "\\" in filename:
        return None

    if "\n" in filename or "\r" in filename:
        return None

    if os.path.basename(filename) != filename:
        return None

    return filename


def get_file_path(filename):
    """Get the path to a file stored on the server."""
    name = safe_filename(filename)

    if name is None:
        return None

    return os.path.join(SERVER_FILES, name)


def list_server_files():
    """Return filenames and sizes of stored files."""
    os.makedirs(SERVER_FILES, exist_ok=True)
    files = []

    for name in sorted(os.listdir(SERVER_FILES)):
        path = get_file_path(name)

        if path is not None and os.path.isfile(path):
            files.append((name, os.path.getsize(path)))

    return files


def receive_file(reader, filename, size):
    """Receive exactly size bytes and save them to the server."""
    path = get_file_path(filename)

    if path is None or size < 0:
        return False

    os.makedirs(SERVER_FILES, exist_ok=True)
    temp_path = path + ".part"
    remaining = size

    try:
        with open(temp_path, "wb") as f:
            while remaining > 0:
                chunk = reader.read(min(CHUNK_SIZE, remaining))

                if not chunk:
                    raise ConnectionError("Client disconnected")

                f.write(chunk)
                remaining -= len(chunk)

        os.replace(temp_path, path)
        return True

    except (OSError, ConnectionError):
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return False


def send_file(conn, path):
    """Send a file in chunks."""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)

            if not chunk:
                break

            conn.sendall(chunk)
