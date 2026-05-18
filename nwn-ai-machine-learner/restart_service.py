"""Detached helper used by the web Restart button.

It waits for the old Flask process to leave the port, then starts main.py with
the same Python executable. Keeping this outside web/app.py avoids racing the
old process against the replacement process on Windows.
"""
import os
import socket
import subprocess
import sys
import time


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main():
    old_pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    base_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, "data", "restart_service.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] restart requested; old_pid={old_pid}, port={port}\n")
        deadline = time.time() + 20
        while time.time() < deadline and _port_open(port):
            time.sleep(0.5)

        if _port_open(port):
            log.write("port still busy after wait; starting anyway may fail\n")

        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

        stdout = open(log_path, "a", encoding="utf-8")
        subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=base_dir,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        log.write("spawned main.py\n")


if __name__ == "__main__":
    main()
