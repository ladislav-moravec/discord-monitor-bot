import discord
import asyncio
import os
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
        "stocks": {"AAPL": {"drop_threshold": 10}},
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

def get_stock_price(symbol):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        meta = data['chart']['result'][0]['meta']
        return meta['regularMarketPrice'], meta['previousClose']
    except:
        return None, None

# Discord Bot
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    dev_channel = bot.get_channel(DEV_CHANNEL_ID)
    if dev_channel:
        await dev_channel.send("🤖 **Monitor Bot ONLINE**\nUse `!help` to see available commands.")
    if not monitor_loop.is_running():
        monitor_loop.start()

@bot.event
async def on_message(message):
    if message.channel.id == DEV_CHANNEL_ID:
        print(f"DEBUG: [{message.author}] {message.content}")
    await bot.process_commands(message)

@tasks.loop(minutes=10) # Fixed interval for the loop itself, but it uses the config
async def monitor_loop():
    config = load_config()
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
        price, prev_close = get_stock_price(symbol)
        if price is not None and prev_close is not None:
            drop_percent = ((prev_close - price) / prev_close) * 100
            alert_msg = None
            alert_type = None
            
            if drop_percent >= cfg.get("drop_threshold", 999):
                alert_msg = f"📉 **{symbol} Stock Drop Alert!** 📉\nPrice: **${price}** (Down **{drop_percent:.2f}%** from prev close ${prev_close})"
                alert_type = "drop"
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
    if ctx.channel.id != DEV_CHANNEL_ID: return
    config = load_config()
    state = load_state()
    report = ["📊 **Current Status Report** 📊"]
    
    steam_cfg = config.get("steam_machine", {})
    if steam_cfg.get("monitor"):
        report.append(f"**Steam Machine:** {'Available 🟢' if state.get('steam_available') else 'Not available 🔴'}")
    
    for symbol in config.get("stocks", {}):
        price, prev_close = get_stock_price(symbol)
        if price is not None:
            report.append(f"**{symbol} Stock:** ${price} (Prev: ${prev_close})")
        else:
            report.append(f"**{symbol} Stock:** Error fetching price")
    await ctx.send("\n".join(report))

@bot.command()
async def check(ctx):
    if ctx.channel.id != DEV_CHANNEL_ID: return
    await ctx.send("🔄 Manual check triggered...")
    await monitor_loop()
    await ctx.send("✅ Check completed.")

@bot.command()
async def add_stock(ctx, symbol: str, drop_threshold: float, target_high: float = 999999):
    if ctx.channel.id != DEV_CHANNEL_ID: return
    config = load_config()
    symbol = symbol.upper()
    config["stocks"][symbol] = {"drop_threshold": drop_threshold, "target_high": target_high}
    save_config(config)
    await ctx.send(f"✅ Added **{symbol}** to monitor (Drop threshold: {drop_threshold}%, Target high: ${target_high})")

@bot.command()
async def remove_stock(ctx, symbol: str):
    if ctx.channel.id != DEV_CHANNEL_ID: return
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
    if ctx.channel.id != DEV_CHANNEL_ID: return
    with open(DEV_REQUESTS_LOG, 'a') as f:
        f.write(f"[{time.ctime()}] FROM {ctx.author}: {message}\n")
    await ctx.send("📝 Request recorded. Jules will check this log during the next task update.")

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN not set.")
    else:
        bot.run(TOKEN)
