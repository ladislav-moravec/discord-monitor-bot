import requests
import json
headers = {'User-Agent': 'Mozilla/5.0'}
url_1d = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=1d&interval=1d"
meta_1d = requests.get(url_1d, headers=headers).json()['chart']['result'][0]['meta']
print(f"1d Price: {meta_1d['regularMarketPrice']}, Prev Close: {meta_1d['chartPreviousClose']}")

url_3mo = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=3mo&interval=1d"
res_3mo = requests.get(url_3mo, headers=headers).json()['chart']['result'][0]
meta_3mo = res_3mo['meta']
prices_3mo = res_3mo['indicators']['quote'][0]['close']
print(f"3mo Price: {meta_3mo['regularMarketPrice']}, Prices Count: {len(prices_3mo)}")
