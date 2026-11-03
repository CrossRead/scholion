"""Level five: real CLI, HTTP, MCP wire and plugin adapters agree on readings."""
from __future__ import annotations
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import support
from scholion import contract, core, i18n, mcp_server, ouroboros_tools, server


class MeasurementInterfaces(unittest.TestCase):
    def test_same_observations_cross_every_product_adapter(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary).resolve() / 'profile'
            shutil.copytree(support.FIXTURE_PROFILE, profile)
            before = {p.name: p.read_bytes() for p in profile.iterdir() if p.is_file()}
            with mock.patch.dict(os.environ, {'SCHOLION_PROFILE_DIR': str(profile)}):
                core.reset_cache()
                ouroboros_tools.unpin_session()
                srv = server._Server(('127.0.0.1', 0), server.Handler)
                thread = threading.Thread(target=srv.serve_forever, daemon=True)
                thread.start()
                try:
                    self.assertTrue({'cli', 'mcp', 'web'}.issubset(contract.access()['doors']))
                    tools = {tool.name: tool for tool in ouroboros_tools.get_tools()}
                    for language in ('en', 'ru'):
                        i18n.set_lang(language)
                        for command in ('metrics', 'lifestyle'):
                            with self.subTest(language=language, command=command):
                                data = support.run_json([command], profile_dir=profile, lang=language)
                                with urllib.request.urlopen(f'http://127.0.0.1:{srv.server_address[1]}/api/{command}?lang={language}', timeout=30) as response:
                                    web = json.load(response)
                                name = contract.PLUGIN[command]
                                args = contract.PLUGIN_ARGS.get(command, {})
                                messages = [
                                    {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
                                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': name, 'arguments': args}},
                                ]
                                output = io.StringIO()
                                mcp_server.serve(iter(json.dumps(m)+'\n' for m in messages), output)
                                reply = json.loads(output.getvalue().splitlines()[-1])['result']
                                self.assertFalse(reply.get('isError'), reply)
                                plugin_text = tools[name].handler(ouroboros_tools.ToolContext(), **args)
                                self.assertEqual(plugin_text, reply['content'][0]['text'])
                                code, text, error = support.run([command], profile_dir=profile, lang=language)
                                self.assertEqual(0, code, error)
                                self.assertEqual(text.strip(), plugin_text.strip())
                                self.assertEqual(data['metrics'], web['metrics'])
                                self.assertGreater(len(web['metrics']), 0)
                                if command == 'metrics':
                                    self.assertEqual(data['metrics'], reply['structuredContent']['metrics'])
                finally:
                    srv.shutdown(); srv.server_close(); thread.join(timeout=5)
                    ouroboros_tools.unpin_session()
                    i18n.set_lang('en')
                    core.reset_cache()
            after = {p.name: p.read_bytes() for p in profile.iterdir() if p.is_file()}
            self.assertEqual(before, after)
