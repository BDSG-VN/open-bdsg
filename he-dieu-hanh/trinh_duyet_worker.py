"""Separate unprivileged browser worker. Unix socket only; TLS via IP-pinning proxy."""

import base64
import ipaddress
import json
import os
import queue
import re
import secrets
import select
import socket
import socketserver
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def public_addresses(host):
    records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not records or any(not ipaddress.ip_address(r[4][0]).is_global for r in records):
        raise ValueError("Địa chỉ đích không công khai")
    return records


def check_url(url, hosts):
    if not isinstance(url, str) or len(url) > 2000 or re.search(r"[\x00-\x20\\]", url):
        raise ValueError("URL không hợp lệ")
    u = urlsplit(url)
    if (
        u.scheme != "https"
        or u.port not in (None, 443)
        or u.username
        or u.password
        or u.hostname not in hosts
    ):
        raise ValueError("URL ngoài phạm vi HTTPS đã chọn")
    return url


def public_url(value):
    try:
        u = urlsplit(value)
        return (
            urlunsplit((u.scheme, u.hostname or "", u.path, "", ""))
            if u.scheme in ("http", "https")
            else None
        )
    except ValueError:
        return None


class Tunnel(socketserver.StreamRequestHandler):
    def handle(self):
        remote = None
        try:
            self.connection.settimeout(10)
            line = self.rfile.readline(4096).decode("ascii").strip().split(" ")
            if len(line) != 3 or line[0] != "CONNECT":
                return
            target = line[1]
            host, port = target.rsplit(":", 1)
            if port != "443" or not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", host):
                return
            size = 0
            while True:
                header = self.rfile.readline(4096)
                size += len(header)
                if size > 16384:
                    return
                if header in (b"\r\n", b"\n", b""):
                    break
            # Resolve once, reject mixed public/private answers, connect to the numeric IP.
            record = public_addresses(host)[0]
            remote = socket.socket(record[0], socket.SOCK_STREAM)
            remote.settimeout(10)
            remote.connect(record[4])
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            expiry = time.monotonic() + 60
            total = 0
            while time.monotonic() < expiry and total < 10 * 1024 * 1024:
                readable, _, _ = select.select([self.connection, remote], [], [], 1)
                for source in readable:
                    value = source.recv(65536)
                    if not value:
                        return
                    total += len(value)
                    (remote if source is self.connection else self.connection).sendall(
                        value
                    )
        except Exception:
            pass
        finally:
            if remote:
                remote.close()


class Proxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class BrowserWorker:
    def __init__(self):
        self.requests = queue.Queue(maxsize=8)
        self.ready = threading.Event()
        self.healthy = False

        def run():
            try:
                self.loop()
            finally:
                self.healthy = False
                self.ready.set()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def call(self, data):
        if not self.ready.wait(10) or not self.healthy:
            raise RuntimeError("Browser unavailable")
        answer = queue.Queue(maxsize=1)
        self.requests.put((data, answer), timeout=2)
        return answer.get(timeout=35)

    def loop(self):
        from playwright.sync_api import sync_playwright

        sessions = {}
        with Proxy(("127.0.0.1", 0), Tunnel) as proxy, sync_playwright() as p:
            threading.Thread(target=proxy.serve_forever, daemon=True).start()
            browser = p.chromium.launch(
                chromium_sandbox=True,
                proxy={"server": "http://127.0.0.1:" + str(proxy.server_address[1])},
                args=[
                    "--proxy-bypass-list=<-loopback>",
                    "--disable-quic",
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                ],
            )
            self.healthy = True
            self.ready.set()
            while True:
                for key in list(sessions):
                    if time.monotonic() > sessions[key]["expires"]:
                        sessions.pop(key)["context"].close()
                try:
                    data, answer = self.requests.get(timeout=2)
                except queue.Empty:
                    continue
                try:
                    answer.put(
                        {"ok": True, "result": self.command(browser, sessions, data)}
                    )
                except Exception:
                    answer.put(
                        {
                            "ok": False,
                            "error": "Không hoàn tất thao tác trình duyệt. Kiểm URL, phạm vi hoặc mở phiên mới.",
                        }
                    )

    def command(self, browser, sessions, data):
        key, owner = data.get("task_id"), data.get("owner")
        if not isinstance(key, str) or not isinstance(owner, str):
            raise ValueError()
        action = data.get("action")
        s = sessions.get(key)
        if action == "open" and s is None:
            hosts = data.get("hosts")
            if (
                not isinstance(hosts, list)
                or not 1 <= len(hosts) <= 5
                or any(
                    not isinstance(h, str)
                    or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,252}", h)
                    for h in hosts
                )
            ):
                raise ValueError()
            if len(sessions) >= 2:
                raise ValueError("Tối đa hai phiên")
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                accept_downloads=False,
                service_workers="block",
            )

            def guard(route):
                try:
                    check_url(route.request.url, hosts)
                    route.continue_()
                except Exception:
                    route.abort()

            context.route("**/*", guard)
            context.route_web_socket("**/*", lambda ws: ws.close())
            context.on(
                "page", lambda page: page.close() if len(context.pages) > 1 else None
            )
            page = context.new_page()
            page.set_default_timeout(8000)
            page.on("dialog", lambda dialog: dialog.dismiss())
            s = {
                "owner": owner,
                "hosts": hosts,
                "context": context,
                "page": page,
                "expires": time.monotonic() + 900,
                "nodes": [],
                "nonce": "",
                "count": 0,
            }
            sessions[key] = s
        if not s or s["owner"] != owner:
            raise PermissionError()
        if action == "close":
            s["context"].close()
            del sessions[key]
            return {"closed": True}
        s["count"] += 1
        if s["count"] > 150:
            raise ValueError("Đã hết hạn lượt của phiên")
        page = s["page"]
        if action == "open":
            page.goto(
                check_url(data.get("url"), s["hosts"]),
                wait_until="domcontentloaded",
                timeout=15000,
            )
        elif action in ("click", "fill", "select", "key", "link"):
            if data.get("nonce") != s["nonce"]:
                raise ValueError("Quan sát đã cũ")
            # Consume the observed control state before any potential side effect.
            s["nonce"] = secrets.token_hex(12)
            index = data.get("node")
            if type(index) is not int or not 0 <= index < len(s["nodes"]):
                raise ValueError()
            node = s["nodes"][index]
            if action == "link":
                href = node.get_attribute("href")
                # Agent navigation only follows a verified HTTPS link; it never submits forms.
                page.goto(
                    check_url(href, s["hosts"]),
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
            elif action == "click":
                node.click(timeout=8000)
            elif action in ("fill", "select"):
                value = data.get("text", "")
                if not isinstance(value, str) or len(value) > 4000:
                    raise ValueError()
                node.fill(value) if action == "fill" else node.select_option(value)
            elif action == "key":
                if data.get("text") not in (
                    "Enter",
                    "Tab",
                    "Escape",
                    "ArrowDown",
                    "ArrowUp",
                ):
                    raise ValueError()
                node.press(data["text"])
        elif action != "observe":
            raise ValueError()
        url = page.url
        check_url(url, s["hosts"])
        for node in s["nodes"]:
            try:
                node.dispose()
            except Exception:
                pass
        s["nodes"] = page.query_selector_all(
            "a,button,input:not([type=hidden]),textarea,select"
        )[:80]
        nodes = []
        for index, node in enumerate(s["nodes"]):
            try:
                if not node.is_visible():
                    continue
                info = node.evaluate(
                    '(e)=>({tag:e.tagName.toLowerCase(),type:e.getAttribute("type")||"",label:e.getAttribute("aria-label")||e.getAttribute("placeholder")||e.innerText?.slice(0,120)||"",href:e.tagName==="A"?e.href:null})'
                )
                if info.get("href"):
                    info["href"] = public_url(info["href"])
                nodes.append({"id": index, **info})
            except Exception:
                pass
        s["nonce"] = secrets.token_hex(12)
        result = {
            "url": public_url(url),
            "title": page.title(),
            "text": page.locator("body").inner_text()[:12000],
            "nodes": nodes,
            "nonce": s["nonce"],
            "expires_in": max(0, int(s["expires"] - time.monotonic())),
        }
        if data.get("image"):
            result["screenshot"] = base64.b64encode(
                page.screenshot(type="jpeg", quality=55, timeout=5000)
            ).decode()
        return result


class UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def main():
    if os.geteuid() == 0:
        raise SystemExit("Browser worker must not run as root")
    os.umask(0o077)
    worker = BrowserWorker()
    if not worker.ready.wait(20) or not worker.healthy:
        raise SystemExit("Browser failed startup")

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(40)
            try:
                raw = self.rfile.readline(65537)
                if len(raw) > 65536:
                    raise ValueError()
                result = worker.call(json.loads(raw))
            except Exception:
                result = {"ok": False, "error": "Dịch vụ trình duyệt chưa sẵn sàng"}
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode() + b"\n")

    path = Path(os.environ.get("BDSG_BROWSER_SOCKET", "/run/bdsg-browser/worker.sock"))
    if path.is_socket():
        path.unlink()
    with UnixServer(str(path), Handler) as server:
        os.chmod(path, 0o660)
        server.serve_forever()


if __name__ == "__main__":
    main()
