import os
import socket
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 12000
CHUNK_SIZE = 4096
DOWNLOAD_DIR = "client_files"

HELP_TEXT = """Commands:
  LOGIN <username>       Log in (required before other commands)
  MSG <text>             Send a text message to the server
  LIST                   List files stored on the server
  UPLOAD <path>          Upload a local file to the server
  DOWNLOAD <filename>    Download a file from the server into ./client_files/
  HELP                   Show this help
  QUIT                   Disconnect and exit"""


class ServerDisconnected(Exception):
    """Raised when the server closes the connection unexpectedly."""


class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.reader = None

    # ---------- low-level helpers ----------

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        # Buffered reader: lets us read whole lines and exact byte counts.
        # All reads go through self.reader; never call self.sock.recv directly.
        self.reader = self.sock.makefile("rb")

    def send_line(self, text):
        self.sock.sendall((text + "\n").encode("utf-8"))

    def recv_line(self):
        line = self.reader.readline()
        if not line:
            raise ServerDisconnected()
        return line.decode("utf-8").rstrip("\r\n")

    @staticmethod
    def status_of(reply):
        """Return the 3-digit status code at the start of a reply, or None."""
        code = reply[:3]
        return int(code) if code.isdigit() else None

    def close(self):
        try:
            if self.reader:
                self.reader.close()
            if self.sock:
                self.sock.close()
        except OSError:
            pass

    # ---------- commands ----------

    def simple_command(self, line):
        """LOGIN and MSG: send one line, print one reply."""
        self.send_line(line)
        print(self.recv_line())

    def list_files(self):
        self.send_line("LIST")
        reply = self.recv_line()
        if self.status_of(reply) != 200:
            print(reply)
            return
        try:
            count = int(reply.split()[1])
        except (IndexError, ValueError):
            print(f"Unexpected reply from server: {reply}")
            return
        if count == 0:
            print("No files on server.")
            return
        print(f"{count} file(s) on server:")
        for _ in range(count):
            entry = self.recv_line()
            name, _, size = entry.rpartition(" ")
            print(f"  {name}  ({size} bytes)" if size.isdigit() else f"  {entry}")

    def upload(self, path):
        if not path:
            print("Usage: UPLOAD <path>")
            return
        if not os.path.isfile(path):
            print(f"Local file not found: {path}")
            return

        name = os.path.basename(path)
        size = os.path.getsize(path)
        self.send_line(f"UPLOAD {size} {name}")

        reply = self.recv_line()
        if self.status_of(reply) != 150:      # server refused (not logged in bad name...)
            print(reply)
            return

        sent = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                self.sock.sendall(chunk)
                sent += len(chunk)
        print(f"Sent {sent} bytes.")
        print(self.recv_line())

    def download(self, name):
        if not name:
            print("Usage: DOWNLOAD <filename>")
            return
        self.send_line(f"DOWNLOAD {name}")

        reply = self.recv_line()
        if self.status_of(reply) != 200:
            print(reply)
            return
        try:
            size = int(reply.split()[1])
        except (IndexError, ValueError):
            print(f"Unexpected reply from server: {reply}")
            return

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        dest = os.path.join(DOWNLOAD_DIR, os.path.basename(name))
        tmp = dest + ".part"
        remaining = size
        try:
            with open(tmp, "wb") as f:
                while remaining > 0:
                    chunk = self.reader.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ServerDisconnected()
                    f.write(chunk)
                    remaining -= len(chunk)
        except BaseException:
            # Don't leave a half-written file behind
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        os.replace(tmp, dest)
        print(f"Downloaded {name} ({size} bytes) -> {dest}")

    def quit(self):
        self.send_line("QUIT")
        try:
            print(self.recv_line())
        except ServerDisconnected:
            pass

    # ---------- main loop ----------

    def run(self):
        print(f"Connected to {self.host}:{self.port}. Type HELP for commands.")
        while True:
            try:
                user = input("> ").strip()
            except EOFError:
                user = "QUIT"

            if not user:
                print("Empty command. Type HELP for commands.")
                continue

            parts = user.split(maxsplit=1)
            cmd = parts[0].upper().rstrip(":")      # accept "login" and "LOGIN:"
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd == "HELP":
                print(HELP_TEXT)
            elif cmd == "LOGIN":
                if not arg:
                    print("Usage: LOGIN <username>")
                else:
                    self.simple_command(f"LOGIN {arg}")
            elif cmd == "MSG":
                if not arg:
                    print("Cannot send an empty message. Usage: MSG <text>")
                else:
                    self.simple_command(f"MSG {arg}")
            elif cmd == "LIST":
                self.list_files()
            elif cmd == "UPLOAD":
                self.upload(arg)
            elif cmd == "DOWNLOAD":
                self.download(arg)
            elif cmd == "QUIT":
                self.quit()
                return
            else:
                # Let the server decide it will answer with an error code.
                self.simple_command(user)


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    try:
        port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    except ValueError:
        print("Port must be a number.")
        return

    client = Client(host, port)
    try:
        client.connect()
    except ConnectionRefusedError:
        print(f"Could not connect to {host}:{port}. Is the server running?")
        return
    except OSError as e:
        print(f"Could not connect to {host}:{port}: {e}")
        return

    try:
        client.run()
    except ServerDisconnected:
        print("Server closed the connection.")
    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
        print("Lost connection to the server.")
    except KeyboardInterrupt:
        print("\nInterrupted. Disconnecting.")
        try:
            client.send_line("QUIT")
        except OSError:
            pass
    finally:
        client.close()
        print("Disconnected.")


if __name__ == "__main__":
    main()
