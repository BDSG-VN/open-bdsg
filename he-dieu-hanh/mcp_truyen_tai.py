"""MCP HTTP ghim IP công khai nhưng vẫn kiểm TLS/SNI theo hostname.

Không dùng proxy môi trường, không redirect hoặc tự retry nghiệp vụ. Resolver
và HTTP exchange là seam truyền tải; kiểm giao thức không cần gọi Internet.
"""
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from urllib.parse import urlsplit

PROTOCOL = "2025-06-18"
MAX_BODY = 2 * 1024 * 1024


def _remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("Hết thời gian truyền tải MCP")
    return min(10, value)


class _Body:
    def __init__(self, connection, response, sock):
        self.connection, self.response, self.sock = connection, response, sock
        self.status = response.status

    def getheader(self, name):
        return self.response.getheader(name)

    def read1(self, size, timeout):
        # HTTPResponse có thể đóng socket ngay khi đọc đủ Content-Length.
        if self.response.isclosed():
            return b""
        self.sock.settimeout(timeout)
        return self.response.read1(size)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.response.close()
        self.connection.close()


def _https(host, address, path, method, headers, body, deadline, guard):
    connection, raw, secured = None, None, None
    try:
        guard()
        raw = socket.create_connection((address, 443), timeout=_remaining(deadline))
        if ipaddress.ip_address(raw.getpeername()[0]) != ipaddress.ip_address(address):
            raise PermissionError("Địa chỉ kết nối không khớp IP đã ghim")
        raw.settimeout(_remaining(deadline))
        context = ssl.create_default_context()
        secured = context.wrap_socket(raw, server_hostname=host)
        connection = http.client.HTTPSConnection(host, 443, context=context)
        # HTTP client dùng socket đã kiểm, không resolve hostname lần nữa.
        connection.sock = secured
        guard()
        secured.settimeout(_remaining(deadline))
        connection.request(method, path, body=body, headers=headers)
        secured.settimeout(_remaining(deadline))
        response = connection.getresponse()
        return _Body(connection, response, secured)
    except BaseException:
        if connection:
            connection.close()
        if secured:
            secured.close()
        if raw:
            raw.close()
        raise


class TruyenTaiMCP:
    def __init__(self, *, resolver=None, exchange=None):
        self.resolver = resolver or socket.getaddrinfo
        self.exchange = exchange or _https

    @staticmethod
    def _reply(response, identifier, deadline):
        content_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type not in ("application/json", "text/event-stream"):
            raise ValueError("Kiểu phản hồi MCP không được hỗ trợ")
        used, buffer, value = 0, b"", None
        while True:
            chunk = response.read1(min(8192, MAX_BODY-used+1), _remaining(deadline))
            used += len(chunk)
            if used > MAX_BODY:
                raise ValueError("Phản hồi MCP vượt giới hạn")
            buffer += chunk
            if content_type == "text/event-stream":
                buffer = buffer.replace(b"\r\n", b"\n")
                while b"\n\n" in buffer:
                    frame, buffer = buffer.split(b"\n\n", 1)
                    fields = [line[5:].lstrip(b" ") for line in frame.split(b"\n") if line.startswith(b"data:")]
                    if fields:
                        candidate = json.loads(b"\n".join(fields))
                        if isinstance(candidate, dict) and type(candidate.get("id")) is int and candidate["id"] == identifier:
                            value = candidate
                            break
                if value is not None:
                    break
            if not chunk:
                if content_type == "application/json":
                    value = json.loads(buffer)
                break
        if (not isinstance(value, dict) or value.get("jsonrpc") != "2.0"
                or type(value.get("id")) is not int or value["id"] != identifier
                or "error" in value or not isinstance(value.get("result"), dict)):
            raise ValueError("Phản hồi JSON-RPC MCP không hợp lệ")
        return value["result"]

    def goi(self, config, method, parameters, guard):
        if method not in ("tools/list", "tools/call") or not isinstance(parameters, dict):
            raise ValueError("Phương thức MCP không được hỗ trợ")
        parsed = urlsplit(config["url"])
        host, token = parsed.hostname, config.get("token")
        if (parsed.scheme != "https" or not host
                or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+bdsg\.vn", host)
                or parsed.port not in (None, 443) or parsed.username or parsed.password
                or parsed.query or parsed.fragment or any(ord(c) < 33 or ord(c) > 126 for c in config["url"])
                or not isinstance(token, str) or not 1 <= len(token) <= 4096
                or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise ValueError("Endpoint hoặc chứng thư MCP không hợp lệ")
        deadline = time.monotonic() + 30
        guard()
        addresses = [ipaddress.ip_address(row[4][0]) for row in self.resolver(host, 443, type=socket.SOCK_STREAM)]
        if not addresses or any(not address.is_global or "%" in str(address) for address in addresses):
            raise PermissionError("MCP chỉ được kết nối tới địa chỉ công khai")
        address, path, session = str(addresses[0]), parsed.path or "/", {}

        def rpc(identifier, name, params):
            guard()
            headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                       "Authorization": "Bearer "+token, "MCP-Protocol-Version": PROTOCOL, **session}
            payload = {"jsonrpc": "2.0", "method": name, "params": params}
            if identifier is not None:
                payload["id"] = identifier
            raw = json.dumps(payload, allow_nan=False).encode()
            if len(raw) > 64*1024:
                raise ValueError("Yêu cầu MCP vượt giới hạn")
            with self.exchange(host, address, path, "POST", headers, raw, deadline, guard) as response:
                if identifier is None:
                    if response.status != 202:
                        raise ValueError("MCP không nhận thông báo khởi tạo")
                    return None
                if response.status != 200:
                    raise ValueError("MCP từ chối yêu cầu HTTP")
                remote_session = response.getheader("Mcp-Session-Id")
                if remote_session is not None:
                    if (not 1 <= len(remote_session) <= 256 or any(ord(c) < 33 or ord(c) > 126 for c in remote_session)
                            or session and session["MCP-Session-Id"] != remote_session):
                        raise ValueError("Session MCP không hợp lệ")
                    session["MCP-Session-Id"] = remote_session
                return self._reply(response, identifier, deadline)

        try:
            initialized = rpc(1, "initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                "clientInfo": {"name": "open-bdsg-thanhhoa", "version": "0.3.0"}})
            if initialized.get("protocolVersion") != PROTOCOL:
                raise ValueError("MCP chưa hỗ trợ phiên bản được endpoint chọn")
            rpc(None, "notifications/initialized", {})
            result = rpc(2, method, parameters)
            guard()
            return result
        finally:
            if session:
                try:
                    guard()
                    headers = {"Authorization": "Bearer "+token, "MCP-Protocol-Version": PROTOCOL, **session}
                    with self.exchange(host, address, path, "DELETE", headers, None, deadline, guard):
                        pass
                except Exception:
                    pass  # Cleanup không mở lại quyền hoặc thử lại nghiệp vụ đã gửi.
