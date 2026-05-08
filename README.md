# Trading Bot — NSE Intraday (Zerodha MIS)

An automated intraday trading bot for NSE stocks using Zerodha web credentials (no paid API subscription required). Includes a **Django Admin UI** to manage all strategy configuration from a browser.

---

## Features

- **Multiple strategies** running simultaneously
- **Django Admin UI** — configure all strategies and risk settings from a browser, no code editing needed
- **Risk management** — per-trade stop-loss, profit target, daily loss limit, auto square-off
- **Trade log** — every order is recorded and visible in the admin UI
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
├── manage.py               # Django entry point
├── config.py               # Fallback defaults (used by standalone main.py)
├── trader.py               # Order placement, Zerodha login
├── market_data.py          # Live prices & historical candles
├── risk_manager.py         # Stop-loss, targets, daily P&L
├── scheduler.py            # Time-based strategy execution
├── logger.py               # Logging setup
├── main.py                 # Standalone entry point (no Django)
├── strategies/
│   ├── base.py
│   ├── fixed_buy.py
│   ├── ma_crossover.py
│   ├── open_range.py
│   └── bollinger.py
├── trading_bot/            # Django project settings
│   ├── settings.py
│   └── urls.py
├── bot/                    # Django app
│   ├── models.py           # DB models for all strategy configs + TradeLog
│   ├── admin.py            # Admin UI registration
│   ├── config_loader.py    # Reads DB config and converts to dicts
│   ├── logging_trader.py   # Trader subclass that logs every order to DB
│   └── management/
│       └── commands/
│           ├── runbot.py       # Run the bot using DB config
│           └── seed_config.py  # Populate DB from config.py defaults
├── .env                    # Credentials (never commit this)
├── db.sqlite3              # Django database (never commit this)
├── requirements.txt
└── logs/                   # Daily log files
```

---

## Setup — Django Admin UI (recommended)

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

### 3. Create database tables

```bash
python manage.py makemigrations bot
python manage.py migrate
```

### 4. Seed the database with default config

This copies your existing `config.py` values into the database so you have a starting point.

```bash
python manage.py seed_config
```

### 5. Create an admin login

```bash
python manage.py createsuperuser
```

### 6. Start the admin UI

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000/admin/** in your browser. You'll see all strategies listed — click any to edit its settings.

### 7. Run the trading bot

```bash
python manage.py runbot
```

This reads all configuration from the database. When prompted, enter the **6-digit code** from your Zerodha authenticator app.

> **Tip:** Any time you change settings in the admin UI, restart `runbot` to pick up the new config.

---

## Setup — Standalone (no Django)

If you prefer to skip the admin UI and configure via code:

### 1. Create `.env` file

```env
ZERODHA_USER_ID=your_user_id
ZERODHA_PASSWORD=your_password
```

### 2. Edit `config.py`

Set the stocks, quantities, and risk limits directly in `config.py`.

### 3. Run the bot

```bash
python main.py
```

---

## Admin UI — What You Can Configure

| Section | Settings |
|---|---|
| **Zerodha Credentials** | User ID, password |
| **Risk Configuration** | Stop loss %, target %, max daily loss, max positions, square-off time |
| **Fixed Buy Strategy** | Enable/disable, stocks + quantities, order type, execution time |
| **MA Crossover Strategy** | Enable/disable, stocks, EMA periods, candle interval, quantity |
| **Open Range Breakout** | Enable/disable, stocks, range minutes, allow short, quantity |
| **Bollinger Band Strategy** | Enable/disable, stocks, period, std dev multiplier, allow short |
| **Trade Log** | Read-only log of every order placed by the bot |

---

## Risk Configuration

| Setting | Default | Description |
|---|---|---|
| `stop_loss_pct` | 1.5% | Stop loss placed below (BUY) or above (SELL) entry |
| `target_pct` | 3.0% | Profit target — position auto-exited when hit |
| `max_daily_loss` | ₹5000 | All new trades halted if cumulative loss exceeds this |
| `max_open_positions` | 5 | Max concurrent open MIS positions |
| `auto_squareoff_time` | 15:15 | All open positions squared off at this time |

---

## Important Notes

- **MIS product** — all positions are intraday only; Zerodha auto-squares off at 3:20 PM
- **Short selling** — disabled by default; enable the `Allow Short Selling` toggle in the admin UI
- **DB security** — `db.sqlite3` stores your Zerodha password; never commit it to git (already in `.gitignore`)
- **Paper trade first** — test with `quantity_per_stock: 1` on a low-value stock before scaling up
- **Market hours** — bot only executes between 9:15 AM and 3:30 PM IST
- **Config changes** — after editing settings in the admin UI, restart `python manage.py runbot` to apply them

---

## Disclaimer

This bot is for **educational purposes only**. Trading involves significant financial risk. Past strategy performance does not guarantee future results. Use at your own risk.
