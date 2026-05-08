# Trading Bot — NSE Intraday (Zerodha MIS)

An automated intraday trading bot for NSE stocks using Zerodha web credentials (no paid API subscription required).

---

## Features

- **Multiple strategies** running simultaneously
- **Risk management** — per-trade stop-loss, profit target, daily loss limit, auto square-off
- **No API subscription needed** — uses Zerodha web login (jugaad-trader)
- **One trade per stock per day** per strategy — no over-trading

---

## Strategies

| Strategy | How it works | Runs every |
|---|---|---|
| **Fixed Buy** | Buys a fixed qty at market open | Once at 09:21 |
| **MA Crossover** | BUY when EMA(9) crosses above EMA(21) | 5 minutes |
| **Open Range Breakout** | BUY on breakout above first 15-min high | 1 minute |
| **Bollinger Band** | BUY when price bounces back above lower band | 5 minutes |

---

## Project Structure

```
TradingProject/
├── main.py             # Entry point
├── config.py           # All strategy & risk settings
├── trader.py           # Order placement, Zerodha login
├── market_data.py      # Live prices & historical candles
├── risk_manager.py     # Stop-loss, targets, daily P&L
├── scheduler.py        # Time-based strategy execution
├── logger.py           # Logging setup
├── strategies/
│   ├── base.py
│   ├── fixed_buy.py
│   ├── ma_crossover.py
│   ├── open_range.py
│   └── bollinger.py
├── .env                # Credentials (never commit this)
├── requirements.txt
└── logs/               # Daily log files
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create `.env` file

```env
ZERODHA_USER_ID=your_user_id
ZERODHA_PASSWORD=your_password
ZERODHA_TOTP_SECRET=          # leave blank — bot will prompt for app code
```

### 3. Configure strategies

Edit `config.py` to set:
- Which stocks to trade (`stocks` list in each strategy config)
- Quantity per trade (`quantity_per_stock`)
- Risk limits (`RISK_CONFIG`)
- Enable/disable strategies (`ENABLED_STRATEGIES`)

### 4. Run the bot

```bash
python main.py
```

When prompted, enter the **6-digit code** from your Zerodha authenticator app.

---

## Risk Configuration

```python
RISK_CONFIG = {
    "stop_loss_pct":      1.5,    # Stop loss % below entry
    "target_pct":         3.0,    # Profit target % above entry
    "max_daily_loss":     5000,   # Halt trading if loss exceeds ₹5000
    "max_open_positions": 5,      # Max concurrent open trades
    "auto_squareoff_time": "15:15" # Square off all positions at this time
}
```

---

## Important Notes

- **MIS product** — all positions are intraday only; Zerodha auto-squares off at 3:20 PM
- **Short selling** — disabled by default; set `allow_short: True` in config to enable
- **Paper trade first** — test with `quantity_per_stock: 1` on a low-value stock before scaling up
- **Market hours** — bot only executes between 9:15 AM and 3:30 PM IST

---

## Disclaimer

This bot is for **educational purposes only**. Trading involves significant financial risk. Past strategy performance does not guarantee future results. Use at your own risk.
