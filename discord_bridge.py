import discord
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
import time
import json
import requests
from bs4 import BeautifulSoup
from discord.ext import tasks, commands

# Configuration
TOKEN = os.environ.get("DISCORD_TOKEN")
DEV_CHANNEL_ID = 1511681696762957924
NOTIFICATION_CHANNEL_ID = 1511644508608270397 
STATE_FILE = "monitor_state.json"
CONFIG_FILE = "config.json"
CONFIG_TEMPLATE = "config.template.json"
DEV_REQUESTS_LOG = "dev_requests.log"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass

    if os.path.exists(CONFIG_TEMPLATE):
        try:
            with open(CONFIG_TEMPLATE, 'r') as f:
                return json.load(f)
        except:
            pass

    return {
        "stocks": {},
        "steam_machine": {"url": "https://store.steampowered.com/hardware/steammachine", "monitor": False},
        "check_interval_minutes": 10
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"steam_available": False, "stock_alerts": {}}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

# Monitoring Functions
def check_steam_availability(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        session = requests.Session()
        session.get("https://store.steampowered.com/", headers=headers)
        response = session.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        found = False
        for a in soup.find_all('a'):
            text = a.get_text().lower()
            href = a.get('href', '').lower()
            if any(term in text for term in ['buy now', 'add to cart', 'pre-order']):
                if 'steamdeck' not in href and 'steamcontroller' not in href:
                    found = True; break
        if not found:
            for btn in soup.find_all(['button', 'div', 'span']):
                text = btn.get_text().strip().lower()
                if text in ['add to cart', 'pre-order now', 'buy now']:
                    found = True; break
        return found
    except:
        return False

def generate_braille_sparkline(prices):
    if not prices or len(prices) < 2: return ""
    min_p, max_p = min(prices), max(prices)
    if max_p == min_p: max_p += 1

    # 4 levels of vertical dots (1,2,3,7 for left and 4,5,6,8 for right)
    # Solid bar style: fill from bottom to eliminate black spaces
    def get_dots_left(p):
        val = int(((p - min_p) / (max_p - min_p)) * 3)
        if val == 0: return [7]
        if val == 1: return [7, 3]
        if val == 2: return [7, 3, 2]
        return [7, 3, 2, 1]

    def get_dots_right(p):
        val = int(((p - min_p) / (max_p - min_p)) * 3)
        if val == 0: return [8]
        if val == 1: return [8, 6]
        if val == 2: return [8, 6, 5]
        return [8, 6, 5, 4]

    res = ""
    for i in range(0, len(prices), 2):
        dots = get_dots_left(prices[i])
        if i + 1 < len(prices):
            dots += get_dots_right(prices[i+1])
        base = 0x2800
        char_code = base
        for dot in dots:
            char_code += (1 << (dot - 1))
        res += chr(char_code)
    return res

def get_stock_info(symbol):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # Get 1d data for accurate previous close
        url_1d = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d"
        res_1d = requests.get(url_1d, headers=headers, timeout=15).json()['chart']['result'][0]
        price = res_1d['meta']['regularMarketPrice']
        prev_close = res_1d['meta']['chartPreviousClose']

        # Get 1y data for high-density sparkline
        url_1y = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
        res_1y = requests.get(url_1y, headers=headers, timeout=15).json()['chart']['result'][0]
        prices = res_1y['indicators']['quote'][0]['close']
        valid_prices = [p for p in prices if p is not None]

        # Sample 1 year of data using 4-day averaging to hold more information.
        # 252 days / 4 = 63 points. Braille shows 2 points per char = ~32 chars (3cm).
        spark_prices = []
        for i in range(0, len(valid_prices), 4):
            window = valid_prices[i:i+4]
            spark_prices.append(sum(window) / len(window))

        return price, prev_close, spark_prices
    except:
        return None, None, None

# Discord Bot
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    dev_channel = bot.get_channel(DEV_CHANNEL_ID)
    if dev_channel:
        await dev_channel.send("🤖 **Monitor Bot ONLINE**\nUse `!help` to see available commands.")
    if not monitor_loop.is_running():
        print("DEBUG: Starting monitor loop...")
        monitor_loop.start()

@bot.event
async def on_message(message):
    print(f"DEBUG: Message from {message.author} in {message.channel.id}: {message.content}")
    await bot.process_commands(message)

@tasks.loop(minutes=10) # Fixed interval for the loop itself, but it uses the config
async def monitor_loop():
    config = load_config()
    print(f"DEBUG: Running monitor cycle at {time.ctime()} (Checking {len(config.get('stocks', {}))} stocks and Steam: {config.get('steam_machine', {}).get('monitor')})")
    state = load_state()
    if "stock_alerts" not in state: state["stock_alerts"] = {}
    notif_channel = bot.get_channel(NOTIFICATION_CHANNEL_ID) or bot.get_channel(DEV_CHANNEL_ID)
    
    # Steam
    steam_cfg = config.get("steam_machine", {})
    if steam_cfg.get("monitor") and not state.get("steam_available", False):
        if check_steam_availability(steam_cfg.get("url")):
            if notif_channel:
                await notif_channel.send(f"🚨 **Steam Machine is AVAILABLE!** 🚨\nBuy it here: {steam_cfg.get('url')}")
            state["steam_available"] = True
    
    # Stocks
    for symbol, cfg in config.get("stocks", {}).items():
        price, prev_close, spark_prices = get_stock_info(symbol)
        if price is not None and prev_close is not None:
            diff_percent = ((price - prev_close) / prev_close) * 100
            alert_msg = None
            alert_type = None
            
            if diff_percent <= -cfg.get("drop_threshold", 999):
                alert_msg = f"📉 **{symbol} Stock Drop Alert!** 📉\nPrice: **${price}** (Down **{abs(diff_percent):.2f}%** from prev close ${prev_close})"
                alert_type = "drop"
            elif diff_percent >= cfg.get("raise_threshold", 999):
                alert_msg = f"🚀 **{symbol} Stock Raise Alert!** 🚀\nPrice: **${price}** (Up **{diff_percent:.2f}%** from prev close ${prev_close})"
                alert_type = "raise"
            elif price >= cfg.get("target_high", 999999):
                alert_msg = f"🚀 **{symbol} Stock Target Reached!** 🚀\nPrice: **${price}**"
                alert_type = "high"
            
            last_alert = state["stock_alerts"].get(symbol)
            if alert_type and last_alert != alert_type:
                if notif_channel:
                    await notif_channel.send(alert_msg)
                state["stock_alerts"][symbol] = alert_type
            elif not alert_type:
                state["stock_alerts"][symbol] = None
            
    save_state(state)

@bot.command()
async def status(ctx):
    config = load_config()
    state = load_state()
    report = ["📊 **Current Status Report** 📊"]
    
    steam_cfg = config.get("steam_machine", {})
    if steam_cfg.get("monitor"):
        report.append(f"**Steam Machine:** {'Available 🟢' if state.get('steam_available') else 'Not available 🔴'}")
    
    for symbol in config.get("stocks", {}):
        price, prev_close, spark_prices = get_stock_info(symbol)
        if price is not None:
            pct_change = ((price - prev_close) / prev_close) * 100
            change_str = f"{'+' if pct_change >= 0 else ''}{pct_change:.2f}%"
            sparkline = generate_braille_sparkline(spark_prices)
            report.append(f"**{symbol}**: ${price} ({change_str}) {sparkline}")
        else:
            report.append(f"**{symbol} Stock:** Error fetching price")
    await ctx.send("\n".join(report))

@bot.command()
async def check(ctx):
    await ctx.send("🔄 Manual check triggered...")
    await monitor_loop()
    await ctx.send("✅ Check completed.")

@bot.command()
async def add_stock(ctx, symbol: str, drop_threshold: float, target_high: float = 999999):
    config = load_config()
    symbol = symbol.upper()
    config["stocks"][symbol] = {"drop_threshold": drop_threshold, "target_high": target_high}
    save_config(config)
    await ctx.send(f"✅ Added **{symbol}** to monitor (Drop threshold: {drop_threshold}%, Target high: ${target_high})")

@bot.command()
async def remove_stock(ctx, symbol: str):
    config = load_config()
    symbol = symbol.upper()
    if symbol in config["stocks"]:
        del config["stocks"][symbol]
        save_config(config)
        await ctx.send(f"✅ Removed **{symbol}** from monitor.")
    else:
        await ctx.send(f"❌ **{symbol}** not found in monitor list.")

@bot.command()
async def dev(ctx, *, message: str):
    with open(DEV_REQUESTS_LOG, 'a') as f:
        f.write(f"[{time.ctime()}] FROM {ctx.author}: {message}\n")
    await ctx.send("📝 Request recorded. Jules will check this log during the next task update.")

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN not set.")
    else:
        bot.run(TOKEN)
