"""Servidor local que imita a API do Telegram (sendMessage, getUpdates, setMyCommands)."""

import http.server
import json
import queue
import threading
import time


def make_server():
    sent, inbox = [], queue.Queue()
    counter = {"id": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
            method = self.path.rsplit("/", 1)[-1]
            result = True
            if method == "sendMessage":
                sent.append((str(body["chat_id"]), body["text"]))
                result = {"message_id": len(sent)}
            elif method == "getUpdates":
                result, deadline = [], time.time() + min(body.get("timeout", 0), 2)
                while not result and time.time() < deadline:
                    try:
                        text = inbox.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    counter["id"] += 1
                    result.append({"update_id": counter["id"], "message": {
                        "text": text, "chat": {"id": 111, "type": "private"}, "from": {"first_name": "Washington"}}})
            data = json.dumps({"ok": True, "result": result}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, sent, inbox
