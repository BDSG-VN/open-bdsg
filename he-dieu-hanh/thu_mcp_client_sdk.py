"""SDK chính thức qua HTTP/socket gateway thật; không trả phí hoặc OAuth giả."""
import asyncio
import importlib.metadata
import json
import threading
import unittest

import thu_mcp_uy_quyen_don_vi as fixture
from may_chu import tao_may_chu

try:
    SDK_AVAILABLE = importlib.metadata.version('mcp') == '2.3.0'
except importlib.metadata.PackageNotFoundError:
    SDK_AVAILABLE = False
else:
    if not SDK_AVAILABLE:
        raise RuntimeError('Kiểm SDK cần đúng requirements-mcp-test.txt')
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    import httpx2


@unittest.skipUnless(SDK_AVAILABLE, 'Cần requirements-mcp-test.txt; CI cài và bắt buộc chạy SDK')
class ThuMCPClientSDK(unittest.TestCase):
    def setUp(self):
        fixture.ThuUyQuyenMCPDonVi.setUp(self)
        self.issued = self.service.create(self.actor, {'name': 'Client SDK thu', 'client_id': 'official-sdk-test',
            'tools': ['du_an.danh_sach', 'cong_viec.tao', 'cong_viec.chi_tiet'],
            'project_ids': [self.project], 'expires_in': 900, 'task_profile': {'allow_ai': False}})
        self.server = tao_may_chu(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.close_server)
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)+'/mcp'

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()

    def test_sdk_initialize_list_call_and_create_task(self):
        async def run():
            async with httpx2.AsyncClient(headers={'Authorization': 'Bearer '+self.issued['credential']},
                                           timeout=5, trust_env=False) as http:
                transport = streamable_http_client(self.url, http_client=http)
                async with Client(transport, mode='legacy', cache=None) as client:
                    self.assertEqual(client.protocol_version, '2025-06-18')
                    listed = await client.list_tools()
                    self.assertCountEqual([tool.name for tool in listed.tools], self.issued['tools'])
                    result = await client.call_tool('du_an.danh_sach', {})
                    self.assertFalse(result.is_error)
                    self.assertEqual([row['id'] for row in json.loads(result.content[0].text)['projects']], [self.project])
                    created = await client.call_tool('cong_viec.tao', {'prompt': 'Tong hop danh muc qua client SDK that',
                        'project_id': self.project, 'template': 'tong-quan', 'module_ids': []})
                    self.assertFalse(created.is_error)
                    identifier = json.loads(created.content[0].text)['id']
                    for _ in range(50):
                        detail = await client.call_tool('cong_viec.chi_tiet', {'id': identifier})
                        self.assertFalse(detail.is_error)
                        task = json.loads(detail.content[0].text)
                        if task['status'] == 'completed': break
                        await asyncio.sleep(.02)
                    self.assertEqual(task['status'], 'completed')
                    self.assertTrue(task['mcp_delegated'])
                    self.assertEqual(len(task['artifacts']), 1)
        asyncio.run(run())

    def test_sdk_revoked_credential_cannot_keep_using_connected_client(self):
        statuses = []
        async def record(response): statuses.append(response.status_code)
        async def run():
            async with httpx2.AsyncClient(headers={'Authorization': 'Bearer '+self.issued['credential']},
                    timeout=5, trust_env=False, event_hooks={'response': [record]}) as http:
                transport = streamable_http_client(self.url, http_client=http)
                async with Client(transport, mode='legacy', cache=None) as client:
                    await client.list_tools()
                    self.service.revoke(self.actor, self.issued['id'])
                    with self.assertRaises(Exception):
                        await client.call_tool('du_an.danh_sach', {})
                    self.assertEqual(statuses[-1], 401)
        asyncio.run(run())


if __name__ == '__main__': unittest.main()
