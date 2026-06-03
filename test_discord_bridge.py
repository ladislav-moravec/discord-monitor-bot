import unittest
from unittest.mock import patch, MagicMock
from discord_bridge import check_steam_availability, get_stock_price

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
    def test_stock_price_normal(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'chart': {'result': [{'meta': {'regularMarketPrice': 100.0, 'previousClose': 100.0}}]}
        }
        mock_get.return_value = mock_response
        price, prev = get_stock_price("GOOGL")
        self.assertEqual(price, 100.0)
        self.assertEqual(prev, 100.0)

    @patch('discord_bridge.requests.get')
    def test_stock_price_aapl_drop(self, mock_get):
        # 150 to 135 is a 10% drop
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'chart': {'result': [{'meta': {'regularMarketPrice': 135.0, 'previousClose': 150.0}}]}
        }
        mock_get.return_value = mock_response
        price, prev = get_stock_price("AAPL")
        self.assertEqual(price, 135.0)
        self.assertEqual(prev, 150.0)
        drop_percent = ((prev - price) / prev) * 100
        self.assertAlmostEqual(drop_percent, 10.0)

if __name__ == '__main__':
    unittest.main()
