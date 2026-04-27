from __future__ import annotations

import os
import threading
import time
import webbrowser

from web_ui.app import app


def _open_browser_later(url: str, delay: float = 1.0) -> None:
    def _worker() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


if __name__ == "__main__":
    host = os.environ.get("GOMOKU_HOST", "127.0.0.1")
    port = int(os.environ.get("GOMOKU_PORT", "7860"))
    _open_browser_later(f"http://{host}:{port}/")
    app.run(host=host, port=port, debug=False)
