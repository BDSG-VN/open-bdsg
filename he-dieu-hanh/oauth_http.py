"""Đọc yêu cầu OAuth có giới hạn; token form và JSON consent dùng cùng parser."""
import json
import re
from urllib.parse import parse_qsl

from oauth_mcp_don_vi import LoiOAuth


def read_authorization_query(query):
    if (not query or len(query) > 8192 or not query.isascii()
            or re.search(r'%(?![0-9a-fA-F]{2})', query)):
        raise LoiOAuth('invalid_request')
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=12, encoding='utf-8', errors='strict')
        result = {}
        for key, value in pairs:
            if key in result or any(ord(c) < 32 or ord(c) == 127 for c in key+value):
                raise LoiOAuth('invalid_request')
            result[key] = value
        return result
    except (ValueError, UnicodeError):
        raise LoiOAuth('invalid_request') from None


def validate_headers(headers):
    for key in ('Content-Type', 'Content-Length', 'Transfer-Encoding', 'Origin', 'Authorization', 'Cookie',
                'X-BDSG-Actor', 'X-BDSG-Unit', 'X-BDSG-Unit-Epoch', 'X-BDSG-Unit-Revision'):
        if len(headers.get_all(key, [])) > 1: raise LoiOAuth('invalid_request')


def read_request(headers, read, *, form=False):
    validate_headers(headers)
    expected = 'application/x-www-form-urlencoded' if form else 'application/json'
    length = headers.get('Content-Length', '')
    if (headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != expected
            or headers.get('Transfer-Encoding') is not None or not length.isascii() or not length.isdecimal()
            or len(length) > 6 or not 0 < int(length) <= (8192 if form else 65536)):
        raise LoiOAuth('invalid_request')
    raw = read(int(length))
    if len(raw) != int(length): raise LoiOAuth('invalid_request')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise LoiOAuth('invalid_request')
            result[key] = value
        return result
    try:
        if form:
            return unique(parse_qsl(raw.decode('utf-8'), keep_blank_values=True, strict_parsing=True,
                                    max_num_fields=12, encoding='utf-8', errors='strict'))
        def nonfinite(_value): raise LoiOAuth('invalid_request')
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=nonfinite)
        if not isinstance(data, dict): raise LoiOAuth('invalid_request')
        json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        return data
    except (ValueError, UnicodeError, RecursionError):
        raise LoiOAuth('invalid_request') from None
