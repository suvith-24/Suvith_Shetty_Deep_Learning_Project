"""Launch LexiSyncAI (API + web interface) on http://127.0.0.1:8000.

    python app.py                 # start and open the browser
    python app.py --no-browser    # start only
    python app.py --port 8080
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def _lexisync_already_running(url: str) -> bool:
    try:
        with urlopen(f"{url}/api/health", timeout=2) as response:
            return json.loads(response.read().decode("utf-8")).get("status") == "ok"
    except (OSError, ValueError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="LexiSyncAI — evidence-grounded legal document analyst")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"

    # Check the port before loading any models, so a busy port fails fast
    # with a useful message instead of a socket error after model loading.
    if not _port_is_free(args.host, args.port):
        if _lexisync_already_running(url):
            print(f"\n  LexiSyncAI is already running at {url} (another terminal or window).")
            print("  Opening it in the browser. Stop the other instance with Ctrl+C if you want to restart.\n")
            if not args.no_browser:
                webbrowser.open(url)
            return
        print(f"\n  ERROR: port {args.port} is already used by another program.")
        print(f"  Start on a different port:   .\\run.ps1 -Port {args.port + 1}   (or: python app.py --port {args.port + 1})\n")
        sys.exit(1)

    import uvicorn

    from lexisync.api.server import create_app

    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(2.0), webbrowser.open(url)), daemon=True).start()

    print(f"\n  LexiSyncAI is starting at {url}  (Ctrl+C to stop)\n")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
