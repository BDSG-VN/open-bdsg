"""MCP HTTP theo đơn vị, JSON không SSE; bearer thủ công hoặc OAuth cùng guard."""
import json
import re
from urllib.parse import urlsplit

from mcp_uy_quyen_don_vi import LoiChungThuMCP

PROTOCOL = '2025-06-18'
MAX_BODY = 65536


class MCPHTTPDonVi:
    def __init__(self, authority, *, origin):
        self.authority, self.origin = authority, origin.rstrip('/')

    @staticmethod
    def _error(status, code, message, identifier=None):
        return status, {'jsonrpc': '2.0', 'id': identifier,
                        'error': {'code': code, 'message': message}}, {}

    @staticmethod
    def _identifier(value):
        return ((type(value) is int and abs(value) <= 9007199254740991)
                or (isinstance(value, str) and 0 < len(value) <= 128))

    @staticmethod
    def _object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Khóa JSON trùng')
            result[key] = value
        return result

    @staticmethod
    def _accept(value):
        supported = set()
        for part in value.lower().split(','):
            media, *parameters = part.strip().split(';')
            quality = 1.0
            for parameter in parameters:
                key, sep, number = parameter.strip().partition('=')
                if key == 'q':
                    if not sep: return False
                    try: quality = float(number)
                    except ValueError: return False
            if 0 < quality <= 1:
                supported.add(media.strip())
        return {'application/json', 'text/event-stream'} <= supported

    def handle(self, method, path, headers, read, *, draining=False):
        for key in ('Authorization', 'Origin', 'Content-Type', 'Content-Length',
                    'Transfer-Encoding', 'MCP-Protocol-Version', 'Accept'):
            if len(headers.get_all(key, [])) > 1:
                return self._error(400, -32600, 'Header MCP không hợp lệ')
        if headers.get('Origin') is not None and headers['Origin'] != self.origin:
            return self._error(403, -32600, 'Nguồn truy cập không được phép')
        target = urlsplit(path)
        if target.query or target.fragment or target.path != '/mcp':
            return self._error(400, -32600, 'MCP không nhận tham số URL')
        if draining:
            return 503, {'error': 'Đang dừng dịch vụ'}, {'Retry-After': '5'}
        authorization = headers.get('Authorization', '')
        match = re.fullmatch(r'(?i:Bearer) (bdsg_u_[A-Za-z0-9_-]{43})', authorization)
        try:
            if match is None:
                raise LoiChungThuMCP()
            actor = self.authority.authenticate(match[1])
        except (PermissionError, ValueError):
            return self._unauthorized()
        if method != 'POST':
            return 405, {'error': 'Dùng POST cho MCP; không cung cấp SSE chủ động'}, {'Allow': 'POST'}
        version = headers.get('MCP-Protocol-Version', '2025-03-26')
        if version not in ('2025-03-26', PROTOCOL):
            return self._error(400, -32600, 'Phiên bản MCP chưa được hỗ trợ')
        if not self._accept(headers.get('Accept', '')):
            return self._error(406, -32600, 'Cần Accept application/json và text/event-stream')
        if headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/json':
            return self._error(415, -32600, 'Cần nội dung application/json')
        length = headers.get('Content-Length', '')
        if headers.get('Transfer-Encoding') is not None or not re.fullmatch(r'[0-9]{1,8}', length):
            return self._error(400, -32600, 'Cần Content-Length cụ thể')
        if not 0 < int(length) <= MAX_BODY:
            return self._error(413, -32600, 'Nội dung MCP vượt giới hạn')
        try:
            raw = read(int(length))
            if len(raw) != int(length): raise ValueError('Nội dung chưa đủ')
            def invalid_constant(_value): raise ValueError('JSON không hữu hạn')
            body = json.loads(raw.decode('utf-8'), object_pairs_hook=self._object,
                              parse_constant=invalid_constant)
            json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (ValueError, UnicodeError, RecursionError):
            return self._error(400, -32700, 'JSON MCP không hợp lệ')
        try:
            response = self._dispatch(actor, body)
            # Không gắn quyền vào handshake/session header hoặc giữ actor cũ.
            self.authority.authenticate(match[1])
            return response
        except LoiChungThuMCP:
            return self._unauthorized()
        except (PermissionError, ValueError):
            return self._error(403, -32001, 'Không có quyền MCP còn hiệu lực')

    def _unauthorized(self):
        return 401, {'error': 'Cần credential MCP đơn vị còn hiệu lực'}, {
            'WWW-Authenticate': 'Bearer realm="bdsg-unit-mcp", error="invalid_token", '
                                'resource_metadata="'+self.origin+'/.well-known/oauth-protected-resource/mcp"'}

    def _dispatch(self, actor, body):
        if (not isinstance(body, dict) or body.get('jsonrpc') != '2.0'
                or not isinstance(body.get('method'), str)
                or set(body)-{'jsonrpc', 'id', 'method', 'params'}
                or ('id' in body and not self._identifier(body['id']))):
            return self._error(400, -32600, 'Gói JSON-RPC không hợp lệ')
        method, identifier = body['method'], body.get('id')
        parameters = body.get('params', {})
        if not isinstance(parameters, dict) or ('_meta' in parameters and not isinstance(parameters['_meta'], dict)):
            return self._error(200 if 'id' in body else 400, -32602, 'Tham số JSON-RPC không hợp lệ', identifier)
        parameters = {key: value for key, value in parameters.items() if key != '_meta'}
        if 'id' not in body:
            if not method.startswith('notifications/'):
                return self._error(400, -32600, 'Yêu cầu MCP cần ID')
            if method == 'notifications/initialized' and parameters:
                return self._error(400, -32602, 'Notification không hợp lệ')
            if method == 'notifications/cancelled' and (set(parameters)-{'requestId', 'reason'}
                    or not self._identifier(parameters.get('requestId'))
                    or ('reason' in parameters and (not isinstance(parameters['reason'], str)
                                                   or len(parameters['reason']) > 512))):
                return self._error(400, -32602, 'Notification không hợp lệ')
            # Hủy RPC chỉ là gợi ý; dừng tác vụ nghiệp vụ cần công cụ đã cấp.
            return 202, None, {}
        result = None
        if method == 'initialize':
            client = parameters.get('clientInfo')
            if (set(parameters) != {'protocolVersion', 'capabilities', 'clientInfo'}
                    or not isinstance(parameters['protocolVersion'], str)
                    or not 1 <= len(parameters['protocolVersion']) <= 32
                    or not isinstance(parameters['capabilities'], dict) or not isinstance(client, dict)
                    or any(not isinstance(client.get(key), str) or not 1 <= len(client[key]) <= 128
                           for key in ('name', 'version'))):
                return self._error(200, -32602, 'Tham số khởi tạo không hợp lệ', identifier)
            result = {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'bdsg-thanhhoa-unit', 'version': '0.3.0'}}
        elif method == 'ping':
            if parameters: return self._error(200, -32602, 'Ping không nhận tham số', identifier)
            result = {}
        elif method == 'tools/list':
            if parameters: return self._error(200, -32602, 'Không nhận cursor hoặc scope tự gửi', identifier)
            result = self.authority.tools(actor)
        elif method == 'tools/call':
            if (set(parameters)-{'name', 'arguments'} or not isinstance(parameters.get('name'), str)
                    or not isinstance(parameters.get('arguments', {}), dict)):
                return self._error(200, -32602, 'Tham số gọi công cụ không hợp lệ', identifier)
            name = parameters['name']
            if name not in {tool['name'] for tool in self.authority.tools(actor)['tools']}:
                return self._error(200, -32602, 'Công cụ không có trong phạm vi', identifier)
            try:
                outcome = self.authority.call(actor, name, parameters.get('arguments', {}))
                failed = not outcome.get('ok')
                value = {'error': 'Không hoàn tất công cụ trong phạm vi hiện hành'} if failed else outcome['ket_qua']
                result = {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False, allow_nan=False)}],
                          'isError': failed}
            except LoiChungThuMCP:
                raise
            except (ValueError, PermissionError):
                result = {'content': [{'type': 'text', 'text': 'Tham số hoặc quyền công cụ không hợp lệ'}], 'isError': True}
        else:
            return self._error(200, -32601, 'Phương thức MCP không được hỗ trợ', identifier)
        return 200, {'jsonrpc': '2.0', 'id': identifier, 'result': result}, {}
