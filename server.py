import os
import socket
import protocol  # Sam's protocol file (protocol.py)

HOST = "127.0.0.1"
PORT = 12000


def get_users():
  """Read users.txt, stripping whitespace and handling utf-8 clean."""
  if not os.path.exists("users.txt"):
    return []
  with open("users.txt", "r", encoding="utf-8-sig") as f:
    return [line.strip() for line in f if line.strip()]


def main():
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.setsockopt(
      socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
  )  # Prevents 'Address already in use' errors
  s.bind((HOST, PORT))
  s.listen(5)
  print(f"Server started on port {PORT}...")

  while True:
    conn, addr = s.accept()
    print("Client connected from:", addr)
    user = None
    reader = conn.makefile("rb")

    while True:
      try:
        # Step 1: Read a line using Sam's helper
        line = protocol.recv_line(reader)
        if line is None:
          break  # Client disconnected

        if not line.strip():
          continue

        # Parse command and arguments
        parts = line.split(maxsplit=1)
        cmd = parts[0].upper()
        args = parts[1].strip() if len(parts) > 1 else ""

        # Step 2: Handle Commands

        # --- LOGIN ---
        if cmd == "LOGIN":
          users_list = get_users()
          if args in users_list:
            user = args
            protocol.send_line(conn, f"200 Welcome {user}")
          else:
            protocol.send_line(conn, "401 Invalid user")

        # --- MSG ---
        elif cmd == "MSG":
          if user is None:
            protocol.send_line(conn, "400 Please login first")
          else:
            print(f"Message from {user}: {args}")
            protocol.send_line(conn, "200 Message received")

        # --- LIST ---
        elif cmd == "LIST":
          if user is None:
            protocol.send_line(conn, "400 Please login first")
            continue

          files = protocol.list_server_files()
          protocol.send_line(conn, f"200 {len(files)}")
          for fname, fsize in files:
            protocol.send_line(conn, f"{fname} {fsize}")

        # --- UPLOAD ---
        elif cmd == "UPLOAD":
          if user is None:
            protocol.send_line(conn, "400 Please login first")
            continue

          # Tyler's client sends: UPLOAD <size> <filename>
          upload_parts = args.split(maxsplit=1)
          if len(upload_parts) < 2:
            protocol.send_line(conn, "400 Invalid upload format")
            continue

          try:
            file_size = int(upload_parts[0])
            fname = upload_parts[1]
          except ValueError:
            protocol.send_line(conn, "400 Invalid size specification")
            continue

          # Signal Tyler's client that server is ready (Status 150)
          protocol.send_line(conn, "150 Ready to receive file")

          # Receive file using Sam's safe function
          success = protocol.receive_file(reader, fname, file_size)
          if success:
            protocol.send_line(
                conn, f"200 Uploaded {fname} successfully"
            )
          else:
            protocol.send_line(conn, "500 Upload failed")

        # --- DOWNLOAD ---
        elif cmd == "DOWNLOAD":
          if user is None:
            protocol.send_line(conn, "400 Please login first")
            continue

          fname = args
          target_path = protocol.get_file_path(fname)

          if target_path and os.path.isfile(target_path):
            fsize = os.path.getsize(target_path)
            # Tyler's client expects: 200 <size>
            protocol.send_line(conn, f"200 {fsize}")
            # Stream bytes using Sam's send_file
            protocol.send_file(conn, target_path)
          else:
            protocol.send_line(conn, "404 File not found")

        # --- QUIT ---
        elif cmd == "QUIT":
          protocol.send_line(conn, "200 Goodbye")
          break

        # --- UNKNOWN COMMAND ---
        else:
          protocol.send_line(conn, "400 Unknown command")

      except Exception as e:
        print(f"Error handling client {addr}: {e}")
        break

    conn.close()
    print("Client disconnected:", addr)


if __name__ == "__main__":
  main()