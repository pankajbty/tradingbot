# Trading Bot — NSE Intraday (Zerodha MIS)

An automated intraday trading bot for NSE stocks using Zerodha web credentials (no paid API subscription required). Includes a **Django Admin UI** to manage all strategy configuration, start/stop the bot, and watch live logs — all from a browser.

---

## Features

- **Multiple strategies** running simultaneously
- **Django Admin UI** — configure all strategies and risk settings from a browser, no code editing needed
- **Bot Control panel** — start and stop the bot from the browser with a single click
- **Live log viewer** — real-time colour-coded log stream built into the admin UI
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
│   ├── models.py           # DB models for all strategy configs + TradeLog + BotControl
│   ├── admin.py            # Admin UI registration
│   ├── views.py            # Bot control, start/stop, status API, SSE log stream
│   ├── urls.py             # Bot control URL routes
│   ├── config_loader.py    # Reads DB config and converts to dicts
│   ├── logging_trader.py   # Trader subclass that logs every order to DB
│   └── management/
│       └── commands/
│           ├── runbot.py       # Run the bot using DB config
│           └── seed_config.py  # Populate DB from config.py defaults
├── .env                    # Credentials (never commit this)
├── db.sqlite3              # Django database (never commit this)
├── requirements.txt
└── logs/                   # Daily log files (trading_YYYYMMDD.log)
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
ZERODHA_TOTP_SECRET=          # leave blank — you will enter the app code from the UI
```

### 3. Create database tables

```bash
python manage.py makemigrations bot
python manage.py migrate
```

### 4. Seed the database with default config

Copies your existing `config.py` values into the database as a starting point. Safe to re-run — skips tables that already have data.

```bash
python manage.py seed_config
```

### 5. Create an admin login

```bash
python manage.py createsuperuser
```

### 6. Start the admin server

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000/admin/** in your browser.

### 7. Start the bot from the UI

- Click **Bot Control** in the admin sidebar
- Enter your **6-digit app code** from the Zerodha authenticator app
- Click **▶ Start Bot**

> **Note:** After changing any settings in the admin UI, click **Stop Bot** then **Start Bot** to apply the new config.

---

## Setup — Standalone (no Django)

If you prefer to configure via code and run from the terminal:

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

## Bot Control Panel

The **Bot Control** page (Admin → Bot Control) lets you manage the bot entirely from the browser.

### Starting the bot

**Option A — Manual app code (default)**

1. Leave the **TOTP Secret** field blank in Zerodha Credentials
2. On the Bot Control page, enter the 6-digit code from your Zerodha authenticator app
3. Click **▶ Start Bot**

> The TOTP code expires every 30 seconds — enter and submit within the same window.

**Option B — Auto TOTP (no manual entry)**

1. Get your base-32 TOTP secret key from Zerodha:
   - Log in to **kite.zerodha.com**
   - Go to **Profile → My Profile → Security**
   - Click **Reset TOTP** — copy the text key shown below the QR code (e.g. `JBSWY3DPEHPK3PXP`)
2. Paste it into **Admin → Zerodha Credentials → TOTP Secret** and save
3. Click **▶ Start Bot** — the code is generated automatically, no typing needed

### Stopping the bot

Click **■ Stop Bot** — this sends a clean shutdown signal. All open positions remain as-is (square-off happens via the scheduled 15:15 job or Zerodha's own MIS auto-square-off).

### Status indicators

| Indicator | Meaning |
|---|---|
| 🟢 Animated green dot | Bot is running |
| 🔴 Red dot | Bot is stopped |
| PID | OS process ID of the running bot |
| Started / Stopped | Timestamps of the last start and stop |

---

## Live Log Viewer

The log viewer on the Bot Control page streams today's log file in real time using Server-Sent Events (SSE) — no page refresh needed.

### Features

| Feature | Details |
|---|---|
| **History** | Last 200 lines are loaded immediately when you open the page |
| **Live tail** | New log lines appear as the bot writes them |
| **Colour coding** | INFO = blue, WARNING = yellow, ERROR = red, DEBUG = green/dim |
| **Filter pills** | Click All / INFO / WARN / ERROR / DEBUG to show only that level |
| **Auto-scroll** | Scroll down automatically as new lines arrive |
| **Pause scroll** | Scroll up manually — auto-scroll pauses and the button shows ⏸ Paused |
| **Clear** | Wipe the visible log without deleting the file |
| **SSE status chip** | Shows `● live`, `connecting`, or `reconnecting` in the card header |

Log files are saved to `logs/trading_YYYYMMDD.log` and rotate daily.

---

## Admin UI — What You Can Configure

| Section | Settings |
|---|---|
| **Zerodha Credentials** | User ID, password, TOTP secret (optional) |
| **Risk Configuration** | Stop loss %, target %, max daily loss, max positions, square-off time |
| **Fixed Buy Strategy** | Enable/disable, stocks + quantities, order type, execution time |
| **MA Crossover Strategy** | Enable/disable, stocks, EMA periods, candle interval, quantity |
| **Open Range Breakout** | Enable/disable, stocks, range minutes, allow short selling, quantity |
| **Bollinger Band Strategy** | Enable/disable, stocks, SMA period, std dev multiplier, allow short selling |
| **Trade Log** | Read-only log of every order placed by the bot with strategy tag and status |
| **Bot Control** | Start / Stop the bot, live status, real-time log viewer |

---

## Risk Configuration

| Setting | Default | Description |
|---|---|---|
| `stop_loss_pct` | 1.5% | Stop loss placed below (BUY) or above (SELL) entry |
| `target_pct` | 3.0% | Profit target — position auto-exited when hit |
| `max_daily_loss` | ₹5000 | All new trades halted if cumulative loss exceeds this |
| `max_open_positions` | 5 | Max concurrent open MIS positions |
| `auto_squareoff_time` | 15:15 | All open positions squared off at this time daily |

---

## Important Notes

- **MIS product** — all positions are intraday only; Zerodha auto-squares off at 3:20 PM
- **Short selling** — disabled by default; enable the `Allow Short Selling` toggle in the admin UI
- **DB security** — `db.sqlite3` stores your Zerodha password; never commit it to git (already in `.gitignore`)
- **TOTP window** — TOTP codes are valid for 30 seconds; submit the start form quickly after getting the code from your app
- **Config changes** — edits in the admin UI take effect only after restarting the bot (Stop → Start)
- **Paper trade first** — test with `quantity_per_stock: 1` on a low-value stock before scaling up
- **Market hours** — bot only executes between 9:15 AM and 3:30 PM IST
- **Log rotation** — a new log file is created each day; old files remain in `logs/` and are never deleted automatically

---

## Disclaimer

This bot is for **educational purposes only**. Trading involves significant financial risk. Past strategy performance does not guarantee future results. Use at your own risk.
