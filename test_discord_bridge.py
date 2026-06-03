import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from discord_bridge import check_steam_availability, get_stock_info, generate_braille_sparkline

class TestMultiMonitor(unittest.TestCase):

    @patch('discord_bridge.requests.Session')
    def test_steam_not_available(self, mock_session_class):
        mock_session = mock_session_class.return_value
        mock_html = "<html><body>No products here</body></html>"
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        self.assertFalse(check_steam_availability("http://test.com"))

    @patch('discord_bridge.requests.get')
    def test_stock_info_normal(self, mock_get):
        mock_res_1d = MagicMock()
        mock_res_1d.json.return_value = {
            'chart': {'result': [{
                'meta': {'regularMarketPrice': 100.0, 'chartPreviousClose': 100.0}
            }]}
        }
        mock_res_1y = MagicMock()
        mock_res_1y.json.return_value = {
            'chart': {'result': [{
                'indicators': {'quote': [{'close': [90.0, 95.0, 100.0, 105.0]}]}
            }]}
        }
        mock_get.side_effect = [mock_res_1d, mock_res_1y]

        price, prev, spark = get_stock_info("GOOGL")
        self.assertEqual(price, 100.0)
        self.assertEqual(prev, 100.0)
        # Average of [90, 95, 100, 105] is 97.5
        self.assertEqual(spark, [97.5])

    @patch('discord_bridge.requests.get')
    def test_stock_info_aapl_drop_logic(self, mock_get):
        # 150 to 135 is a 10% drop
        mock_res_1d = MagicMock()
        mock_res_1d.json.return_value = {
            'chart': {'result': [{
                'meta': {'regularMarketPrice': 135.0, 'chartPreviousClose': 150.0}
            }]}
        }
        mock_res_1y = MagicMock()
        mock_res_1y.json.return_value = {
            'chart': {'result': [{
                'indicators': {'quote': [{'close': [150.0, 140.0, 135.0]}]}
            }]}
        }
        mock_get.side_effect = [mock_res_1d, mock_res_1y]

        price, prev, spark = get_stock_info("AAPL")
        self.assertEqual(price, 135.0)
        self.assertEqual(prev, 150.0)
        drop_percent = ((prev - price) / prev) * 100
        self.assertAlmostEqual(drop_percent, 10.0)

    def test_generate_braille_sparkline(self):
        # Prices that will map to bottom and top dots
        prices = [10, 10, 80, 80]
        spark = generate_braille_sparkline(prices)
        # Expected: ⢀ + ⣾ (actually more complex, but let's check it's Braille)
        self.assertEqual(len(spark), 2)
        for char in spark:
            self.assertTrue(0x2800 <= ord(char) <= 0x28FF)

    @patch('discord_bridge.check_steam_availability')
    @patch('discord_bridge.bot.get_channel')
    @patch('discord_bridge.load_config')
    @patch('discord_bridge.load_state')
    @patch('discord_bridge.save_state')
    @patch('discord_bridge.get_stock_info')
    def test_monitor_loop_steam(self, mock_stock, mock_save, mock_load_state, mock_load_cfg, mock_get_channel, mock_steam):
        mock_load_cfg.return_value = {
            "steam_machine": {"url": "http://steam.com", "monitor": True},
            "stocks": {}
        }
        mock_load_state.return_value = {"steam_available": False, "stock_alerts": {}}
        mock_steam.return_value = True # Now available

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_get_channel.return_value = mock_channel

        from discord_bridge import monitor_loop
        asyncio.run(monitor_loop())

        mock_channel.send.assert_called()
        self.assertTrue("Steam Machine is AVAILABLE" in mock_channel.send.call_args[0][0])

    @patch('discord_bridge.bot.get_channel')
    @patch('discord_bridge.load_config')
    @patch('discord_bridge.load_state')
    @patch('discord_bridge.save_state')
    @patch('discord_bridge.get_stock_info')
    def test_monitor_loop_raise(self, mock_stock, mock_save, mock_load_state, mock_load_cfg, mock_get_channel):
        mock_load_cfg.return_value = {
            "stocks": {"AAPL": {"raise_threshold": 5}},
            "steam_machine": {"monitor": False}
        }
        mock_load_state.return_value = {"stock_alerts": {}}
        # 100 to 110 is a 10% raise, which is > 5% threshold
        mock_stock.return_value = (110.0, 100.0, [100.0, 105.0, 110.0])

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_get_channel.return_value = mock_channel

        from discord_bridge import monitor_loop
        asyncio.run(monitor_loop())

        mock_channel.send.assert_called()
        self.assertTrue("Stock Raise Alert" in mock_channel.send.call_args[0][0])

if __name__ == '__main__':
    unittest.main()
