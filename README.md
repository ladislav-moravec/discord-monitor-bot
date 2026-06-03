# Discord Multi-Monitor Bot

A Python-based Discord bot that monitors Steam Machine availability and stock price thresholds (e.g., SOFI, GOOGL).

## Features
- **Steam Machine Monitoring:** Checks the official Steam store for hardware availability.
- **Stock Price Alerts:** Tracks specific stocks and alerts on significant price drops or target highs.
- **Dynamic Configuration:** Add or remove stocks to monitor directly via Discord commands.
- **Interactive Commands:** 
  - `!status`: Get a current report of all monitored items.
  - `!check`: Manually trigger a monitoring cycle.
  - `!add_stock <symbol> <drop_threshold> [target_high]`: Add a new stock.
  - `!remove_stock <symbol>`: Remove a stock from the list.
  - `!dev <message>`: Record a request or note for the developer.

## Setup

### Prerequisites
- Python 3.8+
- A Discord Bot Token (with Message Content Intent enabled).

### Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd discord-monitor-bot
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration
1. Create a `.env` file or set the following environment variable:
   - `DISCORD_TOKEN`: Your Discord bot token.
2. Update the `DEV_CHANNEL_ID` and `NOTIFICATION_CHANNEL_ID` in `discord_bridge.py` to match your server's channel IDs.

### Running
To run the bot in the background:
```bash
python3 -u discord_bridge.py > discord_bot.log 2>&1 &
```

## License
MIT
