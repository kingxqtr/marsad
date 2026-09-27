#!/usr/bin/env python3
"""Local server for المرصد: serves the website from www/ and powers the Refresh button.

    python3 server/server.py            # http://localhost:8787
    python3 server/server.py --open     # also opens the browser

Endpoints:
    GET  /api/status    server + source status
    GET  /api/live      auto-fetched items (www/data/live.json)
    POST /api/refresh   fetch official/community sources now, return the merged items
"""
import argparse
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refresh  # noqa: E402


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".webmanifest": "application/manifest+json", ".js": "text/javascript; charset=utf-8",
                      ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=refresh.WWW, **kwargs)

    def end_headers(self):
        path = getattr(self, "path", "").split("?", 1)[0]  # no path on a malformed request line
        if path.startswith(("/api/", "/data/")) or path in ("/", "/index.html") or path.endswith((".js", ".css")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if getattr(self, "path", "").startswith("/api/refresh"):
            sys.stderr.write("[refresh] %s\n" % (fmt % args))

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            return self.send_json(200, refresh.status())
        if path == "/api/live":
            return self.send_json(200, refresh.load_live())
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/refresh":
            return self.send_json(404, {"ok": False, "error": "not found"})
        # Only the site's own page may trigger a refresh: other web pages can't send this header
        # without a CORS preflight this server never answers, and a foreign Origin is refused.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if self.headers.get("X-Marsad") != "1" or (origin and origin.split("://", 1)[-1] != host):
            return self.send_json(403, {"ok": False, "error": "forbidden"})
        try:
            return self.send_json(200, refresh.run())
        except Exception as e:  # report instead of dropping the connection
            return self.send_json(500, {"ok": False, "error": str(e)[:300]})


def refresh_every(minutes):
    """Fetch the sources again on a fixed interval while the server runs."""
    while True:
        time.sleep(minutes * 60)
        try:
            res = refresh.run()
            if res.get("added"):
                sys.stderr.write(f"[auto-refresh] {res['added']} new item(s)\n")
        except Exception as e:  # keep the loop alive through network hiccups
            sys.stderr.write(f"[auto-refresh] failed: {e}\n")


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; this only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(description="المرصد news server")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8787)))
    ap.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    ap.add_argument("--open", action="store_true", help="open the site in the default browser")
    ap.add_argument("--no-refresh", action="store_true", help="don't fetch news at startup")
    ap.add_argument("--every", type=int, default=60, help="fetch news again every N minutes (0 = only on demand)")
    args = ap.parse_args()

    url = f"http://localhost:{args.port}/"
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError:
        # Usually the site is already running (start.command opened twice): just show it.
        print(f"الموقع شغّال من قبل على هذا العنوان / the site is already running: {url}")
        if args.open:
            webbrowser.open(url)
        return
    print(f"المرصد يعمل الآن / Marsad is running:\n  {url}")
    ip = lan_ip()
    if ip and args.host in ("0.0.0.0", ""):
        print(f"  من الجوال على نفس شبكة الواي فاي / from a phone on the same Wi-Fi: http://{ip}:{args.port}/")
    print("للإيقاف اضغط Ctrl+C / press Ctrl+C to stop\n")

    if not args.no_refresh:
        threading.Thread(target=refresh.run, daemon=True).start()
    if args.every > 0:
        threading.Thread(target=refresh_every, args=(args.every,), daemon=True).start()
        print(f"تحديث تلقائي كل {args.every} دقيقة / auto-refresh every {args.every} min\n")
    if args.open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
