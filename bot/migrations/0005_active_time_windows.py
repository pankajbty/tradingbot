"""
Migration 0005 — add active_from / active_until to MA Crossover,
Open Range Breakout, and Bollinger Band strategy config models.
"""
import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot", "0004_bollingerconfig_max_entries_per_day_and_more"),
    ]

    operations = [
        # MA Crossover
        migrations.AddField(
            model_name="macrossoverconfig",
            name="active_from",
            field=models.TimeField(
                default=datetime.time(9, 15),
                verbose_name="Active From (HH:MM IST)",
                help_text="Strategy will not run before this time each day.",
            ),
        ),
        migrations.AddField(
            model_name="macrossoverconfig",
            name="active_until",
            field=models.TimeField(
                default=datetime.time(15, 15),
                verbose_name="Active Until (HH:MM IST)",
                help_text="Strategy will not run after this time each day.",
            ),
        ),
        # Open Range Breakout
        migrations.AddField(
            model_name="openrangeconfig",
            name="active_from",
            field=models.TimeField(
                default=datetime.time(9, 15),
                verbose_name="Active From (HH:MM IST)",
                help_text="Strategy will not run before this time each day.",
            ),
        ),
        migrations.AddField(
            model_name="openrangeconfig",
            name="active_until",
            field=models.TimeField(
                default=datetime.time(15, 15),
                verbose_name="Active Until (HH:MM IST)",
                help_text="Strategy will not run after this time each day. Recommended: 11:00 for ORB.",
            ),
        ),
        # Bollinger Band
        migrations.AddField(
            model_name="bollingerconfig",
            name="active_from",
            field=models.TimeField(
                default=datetime.time(9, 15),
                verbose_name="Active From (HH:MM IST)",
                help_text="Strategy will not run before this time each day.",
            ),
        ),
        migrations.AddField(
            model_name="bollingerconfig",
            name="active_until",
            field=models.TimeField(
                default=datetime.time(15, 15),
                verbose_name="Active Until (HH:MM IST)",
                help_text="Strategy will not run after this time each day.",
            ),
        ),
    ]
