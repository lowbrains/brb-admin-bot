"""Routing and container-configuration tests.

Telegram and the model host must leave the server over *different* routes —
that split is the whole reason the deployment has a proxy container at all.
These tests check the socket destination, not the configuration object, so a
change in urllib's handler assembly cannot make them pass while routing breaks.
"""
import importlib
import os
import unittest
from unittest.mock import patch, MagicMock
from urllib.request import Request

import discussion

TELEGRAM = 'https://api.telegram.org/bot42:FAKE/getMe'
YANDEX = 'https://ai.api.cloud.yandex.net/v1/responses'
OPENAI = 'https://api.openai.com/v1/responses'
TG_PROXY = 'http://tg-proxy:3128'
MODEL_PROXY = 'http://model-proxy:3129'


def socket_target(url, env):
    """Host urllib actually opens a TCP connection to for this request."""
    with patch.dict(os.environ, env, clear=True):
        discussion._OPENERS.clear()
        with patch('http.client.HTTPSConnection') as connection:
            connection.return_value.getresponse.return_value = MagicMock(status=999)
            try:
                discussion.urlopen(Request(url, b'{}', {'Content-Type': 'application/json'}))
            except Exception:
                pass  # The fake response fails later; the connect target is already recorded.
            return connection.call_args.args[0] if connection.call_args else None


class RoutingTests(unittest.TestCase):
    def tearDown(self):
        discussion._OPENERS.clear()

    def test_direct_when_no_proxy_configured(self):
        self.assertEqual(socket_target(TELEGRAM, {}), 'api.telegram.org')
        self.assertEqual(socket_target(OPENAI, {}), 'api.openai.com')

    def test_telegram_goes_through_its_own_proxy(self):
        self.assertEqual(socket_target(TELEGRAM, {'TELEGRAM_PROXY': TG_PROXY}), 'tg-proxy:3128')

    def test_model_goes_through_its_own_proxy(self):
        self.assertEqual(socket_target(OPENAI, {'MODEL_PROXY': MODEL_PROXY}), 'model-proxy:3129')
        self.assertEqual(socket_target(YANDEX, {'MODEL_PROXY': MODEL_PROXY}), 'model-proxy:3129')

    def test_neither_variable_leaks_into_the_other_destination(self):
        """Which side needs a tunnel depends on where the server stands — a Russian
        host reaches Yandex but not OpenAI, a foreign host the reverse — so the two
        routes must stay independent rather than share one hardcoded rule."""
        self.assertEqual(socket_target(OPENAI, {'TELEGRAM_PROXY': TG_PROXY}), 'api.openai.com')
        self.assertEqual(socket_target(TELEGRAM, {'MODEL_PROXY': MODEL_PROXY}), 'api.telegram.org')

    def test_both_destinations_can_be_proxied_separately(self):
        env = {'TELEGRAM_PROXY': TG_PROXY, 'MODEL_PROXY': MODEL_PROXY}
        self.assertEqual(socket_target(TELEGRAM, env), 'tg-proxy:3128')
        self.assertEqual(socket_target(OPENAI, env), 'model-proxy:3129')

    def test_a_global_environment_proxy_is_never_inherited(self):
        """A stray HTTPS_PROXY on the host must not silently route anything."""
        env = {'HTTPS_PROXY': 'http://everything:3128', 'https_proxy': 'http://everything:3128'}
        self.assertEqual(socket_target(OPENAI, env), 'api.openai.com')
        self.assertEqual(socket_target(TELEGRAM, env), 'api.telegram.org')

    def test_whitespace_proxy_is_ignored(self):
        self.assertEqual(socket_target(TELEGRAM, {'TELEGRAM_PROXY': '   '}), 'api.telegram.org')
        self.assertEqual(socket_target(OPENAI, {'MODEL_PROXY': '   '}), 'api.openai.com')

    def test_proxied_request_uses_connect_so_the_secret_stays_in_tls(self):
        """The bot token sits in the Telegram URL path. Over an HTTPS target the
        proxy must only learn host:port, never the path."""
        with patch.dict(os.environ, {'TELEGRAM_PROXY': TG_PROXY}, clear=True):
            discussion._OPENERS.clear()
            with patch('http.client.HTTPSConnection') as connection:
                connection.return_value.getresponse.return_value = MagicMock(status=999)
                try:
                    discussion.urlopen(Request(TELEGRAM, b'{}'))
                except Exception:
                    pass
                tunnel = connection.return_value.set_tunnel
                self.assertTrue(tunnel.called, 'CONNECT не использован — путь с токеном виден прокси')
                self.assertEqual(tunnel.call_args.args[0], 'api.telegram.org')
                self.assertNotIn('FAKE', str(tunnel.call_args))


class ConfigurationTests(unittest.TestCase):
    def reloaded(self, env):
        with patch.dict(os.environ, env, clear=True):
            module = importlib.reload(discussion)
        self.addCleanup(importlib.reload, discussion)
        return module

    def test_runtime_dir_from_environment(self):
        module = self.reloaded({'BRB_RUNTIME_DIR': '/srv/brb'})
        self.assertEqual(str(module.CONFIG_DIR), '/srv/brb/config')
        self.assertEqual(str(module.DATA_DIR), '/srv/brb/data')
        self.assertEqual(str(module.TEAM_FILE), '/srv/brb/team.txt')
        self.assertEqual(str(module.LOCK_FILE), '/srv/brb/bot.lock')

    def test_runtime_dir_defaults_beside_sources(self):
        module = self.reloaded({})
        self.assertEqual(module.RUNTIME.name, 'runtime')
        self.assertEqual(module.BOT_USERNAME, 'brb_team_admin_bot')

    def test_bot_username_from_environment(self):
        self.assertEqual(self.reloaded({'BRB_BOT_USERNAME': 'other_bot'}).BOT_USERNAME, 'other_bot')


if __name__ == '__main__':
    unittest.main()
