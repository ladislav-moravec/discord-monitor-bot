import unittest
from unittest.mock import patch, MagicMock
from discord_bridge import check_steam_availability, get_stock_info, generate_sparkline

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
                'indicators': {'quote': [{'close': [90.0, 95.0, 100.0]}]}
            }]}
        }
        mock_get.side_effect = [mock_res_1d, mock_res_1y]

        price, prev, spark = get_stock_info("GOOGL")
        self.assertEqual(price, 100.0)
        self.assertEqual(prev, 100.0)
        self.assertEqual(spark, [90.0, 100.0]) # [::2] of [90, 95, 100] is [90, 100]

    @patch('discord_bridge.requests.get')
    def test_stock_info_aapl_drop(self, mock_get):
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

    def test_generate_sparkline(self):
        prices = [10, 20, 30, 40, 50, 60, 70, 80]
        spark = generate_sparkline(prices)
        self.assertEqual(spark, " ▂▃▄▅▆▇█")

        prices_same = [50, 50, 50]
        spark_same = generate_sparkline(prices_same)
        self.assertEqual(spark_same, "▅▅▅")

if __name__ == '__main__':
    unittest.main()
