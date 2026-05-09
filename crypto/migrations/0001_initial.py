from __future__ import annotations

import datetime
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # ----------------------------------------------------------------
        # CryptoExchangeConfig
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="CryptoExchangeConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("exchange_id", models.CharField(
                    choices=[("coindcx", "CoinDCX"), ("wazirx", "WazirX"), ("binance", "Binance")],
                    default="coindcx",
                    max_length=30,
                    verbose_name="Exchange",
                    help_text="The ccxt exchange identifier to use.",
                )),
                ("api_key", models.CharField(
                    blank=True,
                    max_length=200,
                    verbose_name="API Key",
                    help_text="Exchange API key.",
                )),
                ("api_secret", models.CharField(
                    blank=True,
                    max_length=200,
                    verbose_name="API Secret",
                    help_text="Exchange API secret.",
                )),
                ("testnet", models.BooleanField(
                    default=False,
                    verbose_name="Use Testnet",
                    help_text="If enabled, connect to the exchange's sandbox/testnet environment.",
                )),
            ],
            options={
                "verbose_name": "Exchange Configuration",
                "verbose_name_plural": "Exchange Configuration",
            },
        ),
        # ----------------------------------------------------------------
        # CryptoRiskConfig
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="CryptoRiskConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stop_loss_pct", models.FloatField(default=2.0, verbose_name="Stop Loss %")),
                ("target_pct", models.FloatField(default=4.0, verbose_name="Target Profit %")),
                ("max_daily_loss", models.FloatField(default=5000, verbose_name="Max Daily Loss (Rs)")),
                ("max_open_positions", models.IntegerField(default=3, verbose_name="Max Open Positions")),
                ("trade_amount_inr", models.FloatField(default=1000, verbose_name="Trade Amount (Rs)")),
                ("daily_reset_hour", models.IntegerField(default=0, verbose_name="Daily Reset Hour (IST)")),
            ],
            options={
                "verbose_name": "Risk Configuration",
                "verbose_name_plural": "Risk Configuration",
            },
        ),
        # ----------------------------------------------------------------
        # EMACrossoverConfig
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="EMACrossoverConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=True)),
                ("symbols", models.JSONField(
                    default=list,
                    help_text='JSON list of ccxt symbols — e.g. ["BTC/INR", "ETH/INR"]',
                )),
                ("fast_period", models.IntegerField(default=9, verbose_name="Fast EMA Period")),
                ("slow_period", models.IntegerField(default=21, verbose_name="Slow EMA Period")),
                ("trend_period", models.IntegerField(default=55, verbose_name="Trend EMA Period")),
                ("candle_interval", models.CharField(
                    choices=[
                        ("1m", "1 min"), ("3m", "3 min"), ("5m", "5 min"),
                        ("15m", "15 min"), ("30m", "30 min"), ("1h", "1 hour"),
                        ("2h", "2 hours"), ("4h", "4 hours"), ("1d", "1 day"),
                    ],
                    default="15m",
                    max_length=10,
                    verbose_name="Candle Interval",
                )),
                ("trade_amount_inr", models.FloatField(default=1000, verbose_name="Trade Amount (Rs)")),
                ("check_interval_minutes", models.IntegerField(default=15, verbose_name="Check Every (minutes)")),
                ("stop_on_profit", models.BooleanField(default=False, verbose_name="Trade Until Profit")),
                ("max_entries_per_day", models.IntegerField(default=0, verbose_name="Max Entries Per Day")),
                ("active_from", models.TimeField(default=datetime.time(0, 0), verbose_name="Active From (HH:MM)")),
                ("active_until", models.TimeField(default=datetime.time(23, 59), verbose_name="Active Until (HH:MM)")),
            ],
            options={
                "verbose_name": "EMA Crossover Strategy",
                "verbose_name_plural": "EMA Crossover Strategy",
            },
        ),
        # ----------------------------------------------------------------
        # SupertrendConfig
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="SupertrendConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=True)),
                ("symbols", models.JSONField(
                    default=list,
                    help_text='JSON list of ccxt symbols — e.g. ["BTC/INR", "ETH/INR", "SOL/INR"]',
                )),
                ("atr_period", models.IntegerField(default=10, verbose_name="ATR Period")),
                ("multiplier", models.FloatField(default=3.0, verbose_name="ATR Multiplier")),
                ("candle_interval", models.CharField(
                    choices=[
                        ("1m", "1 min"), ("3m", "3 min"), ("5m", "5 min"),
                        ("15m", "15 min"), ("30m", "30 min"), ("1h", "1 hour"),
                        ("2h", "2 hours"), ("4h", "4 hours"), ("1d", "1 day"),
                    ],
                    default="15m",
                    max_length=10,
                    verbose_name="Candle Interval",
                )),
                ("trade_amount_inr", models.FloatField(default=1000, verbose_name="Trade Amount (Rs)")),
                ("check_interval_minutes", models.IntegerField(default=15, verbose_name="Check Every (minutes)")),
                ("stop_on_profit", models.BooleanField(default=False, verbose_name="Trade Until Profit")),
                ("max_entries_per_day", models.IntegerField(default=0, verbose_name="Max Entries Per Day")),
                ("active_from", models.TimeField(default=datetime.time(0, 0), verbose_name="Active From (HH:MM)")),
                ("active_until", models.TimeField(default=datetime.time(23, 59), verbose_name="Active Until (HH:MM)")),
            ],
            options={
                "verbose_name": "Supertrend Strategy",
                "verbose_name_plural": "Supertrend Strategy",
            },
        ),
        # ----------------------------------------------------------------
        # RSIBBConfig
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="RSIBBConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=True)),
                ("symbols", models.JSONField(
                    default=list,
                    help_text='JSON list of ccxt symbols — e.g. ["BTC/INR", "ETH/INR"]',
                )),
                ("rsi_period", models.IntegerField(default=14, verbose_name="RSI Period")),
                ("rsi_oversold", models.IntegerField(default=35, verbose_name="RSI Oversold Threshold")),
                ("rsi_overbought", models.IntegerField(default=65, verbose_name="RSI Overbought Threshold")),
                ("bb_period", models.IntegerField(default=20, verbose_name="Bollinger Band Period")),
                ("bb_std_dev", models.FloatField(default=2.0, verbose_name="Bollinger Band Std Dev")),
                ("allow_short", models.BooleanField(default=False, verbose_name="Allow Short Selling")),
                ("candle_interval", models.CharField(
                    choices=[
                        ("1m", "1 min"), ("3m", "3 min"), ("5m", "5 min"),
                        ("15m", "15 min"), ("30m", "30 min"), ("1h", "1 hour"),
                        ("2h", "2 hours"), ("4h", "4 hours"), ("1d", "1 day"),
                    ],
                    default="1h",
                    max_length=10,
                    verbose_name="Candle Interval",
                )),
                ("trade_amount_inr", models.FloatField(default=1000, verbose_name="Trade Amount (Rs)")),
                ("check_interval_minutes", models.IntegerField(default=60, verbose_name="Check Every (minutes)")),
                ("stop_on_profit", models.BooleanField(default=False, verbose_name="Trade Until Profit")),
                ("max_entries_per_day", models.IntegerField(default=0, verbose_name="Max Entries Per Day")),
                ("active_from", models.TimeField(default=datetime.time(0, 0), verbose_name="Active From (HH:MM)")),
                ("active_until", models.TimeField(default=datetime.time(23, 59), verbose_name="Active Until (HH:MM)")),
            ],
            options={
                "verbose_name": "RSI + Bollinger Band Strategy",
                "verbose_name_plural": "RSI + Bollinger Band Strategy",
            },
        ),
        # ----------------------------------------------------------------
        # CryptoBotControl
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="CryptoBotControl",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_running", models.BooleanField(default=False)),
                ("pid", models.IntegerField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("stopped_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Crypto Bot Control",
                "verbose_name_plural": "Crypto Bot Control",
            },
        ),
        # ----------------------------------------------------------------
        # CryptoTradeLog
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="CryptoTradeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("strategy", models.CharField(blank=True, max_length=30)),
                ("symbol", models.CharField(max_length=20)),
                ("side", models.CharField(max_length=4)),
                ("quantity", models.FloatField(default=0.0)),
                ("price", models.FloatField(default=0.0)),
                ("amount_inr", models.FloatField(default=0.0)),
                ("order_id", models.CharField(blank=True, max_length=100)),
                ("tag", models.CharField(blank=True, max_length=30)),
                ("status", models.CharField(default="PLACED", max_length=20)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Crypto Trade",
                "verbose_name_plural": "Crypto Trade Log",
                "ordering": ["-timestamp"],
            },
        ),
    ]
