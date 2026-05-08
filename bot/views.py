import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import BotControl, ZerodhaConfig

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_log_file() -> Path:
    return BASE_DIR / "logs" / f"trading_{datetime.now().strftime('%Y%m%d')}.log"


def _is_alive(pid: int) -> bool:
    """Return True if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _sync_status(ctrl: BotControl) -> BotControl:
    """If the DB says running but PID is dead, mark it stopped."""
    if ctrl.is_running and ctrl.pid and not _is_alive(ctrl.pid):
        ctrl.is_running = False
        ctrl.stopped_at = datetime.now()
        ctrl.save()
    return ctrl


# ---------------------------------------------------------------------------
# Bot control page
# ---------------------------------------------------------------------------

@staff_member_required
def bot_control_page(request):
    ctrl    = _sync_status(BotControl.load())
    zerodha = ZerodhaConfig.load()

    context = {
        **admin.site.each_context(request),
        "title":           "Bot Control",
        "ctrl":            ctrl,
        "has_totp_secret": bool(zerodha.totp_secret.strip()),
        "log_file":        str(_get_log_file().relative_to(BASE_DIR)),
    }
    return render(request, "admin/bot_control.html", context)


# ---------------------------------------------------------------------------
# Start bot
# ---------------------------------------------------------------------------

@staff_member_required
@require_POST
def bot_start(request):
    ctrl = _sync_status(BotControl.load())

    if ctrl.is_running:
        messages.warning(request, f"Bot is already running (PID {ctrl.pid}).")
        return redirect("bot:control")

    # Resolve TOTP code -------------------------------------------------------
    zerodha   = ZerodhaConfig.load()
    totp_code = ""

    if zerodha.totp_secret.strip():
        # Auto-generate from stored secret
        try:
            import pyotp
            totp_code = pyotp.TOTP(zerodha.totp_secret.strip()).now()
        except Exception:
            # Secret is invalid or pyotp not installed — fall back to form input
            totp_code = request.POST.get("totp_code", "").strip()
    else:
        totp_code = request.POST.get("totp_code", "").strip()

    if not totp_code:
        messages.error(request, "TOTP code is required. Enter the 6-digit code from your authenticator app.")
        return redirect("bot:control")

    # Build environment -------------------------------------------------------
    env = os.environ.copy()
    env["BOT_TOTP_CODE"]          = totp_code
    env["DJANGO_SETTINGS_MODULE"] = "trading_bot.settings"

    # Ensure logs directory exists
    (BASE_DIR / "logs").mkdir(exist_ok=True)

    log_file = _get_log_file()

    # Launch subprocess -------------------------------------------------------
    proc = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "manage.py"), "runbot"],
        env=env,
        cwd=str(BASE_DIR),
        stdout=open(log_file, "a"),
        stderr=subprocess.STDOUT,
    )

    ctrl.is_running = True
    ctrl.pid        = proc.pid
    ctrl.started_at = datetime.now()
    ctrl.stopped_at = None
    ctrl.save()

    messages.success(request, f"Bot started successfully (PID {proc.pid}).")
    return redirect("bot:control")


# ---------------------------------------------------------------------------
# Stop bot
# ---------------------------------------------------------------------------

@staff_member_required
@require_POST
def bot_stop(request):
    ctrl = BotControl.load()

    if not ctrl.is_running or not ctrl.pid:
        messages.warning(request, "Bot is not running.")
        return redirect("bot:control")

    try:
        # SIGINT triggers the KeyboardInterrupt handler for a clean shutdown
        os.kill(ctrl.pid, signal.SIGINT)
        messages.success(request, f"Stop signal sent to bot (PID {ctrl.pid}).")
    except ProcessLookupError:
        messages.info(request, "Bot process was no longer running.")
    except Exception as e:
        messages.error(request, f"Failed to stop bot: {e}")

    ctrl.is_running = False
    ctrl.stopped_at = datetime.now()
    ctrl.save()

    return redirect("bot:control")


# ---------------------------------------------------------------------------
# Status API — polled by the UI every few seconds
# ---------------------------------------------------------------------------

@staff_member_required
def bot_status_api(request):
    ctrl  = _sync_status(BotControl.load())
    alive = ctrl.is_running and ctrl.pid and _is_alive(ctrl.pid)

    return JsonResponse({
        "running":    bool(alive),
        "pid":        ctrl.pid,
        "started_at": ctrl.started_at.strftime("%d %b %Y %H:%M:%S") if ctrl.started_at else None,
        "stopped_at": ctrl.stopped_at.strftime("%d %b %Y %H:%M:%S") if ctrl.stopped_at else None,
    })


# ---------------------------------------------------------------------------
# SSE log stream
# ---------------------------------------------------------------------------

@staff_member_required
def log_stream(request):
    """
    Server-Sent Events endpoint.
    Sends the last 200 lines of today's log file immediately,
    then tails new lines as they appear.
    """
    def _event_stream():
        log_file = _get_log_file()

        # Wait up to 5 s for the log file to appear (bot may still be starting)
        for _ in range(10):
            if log_file.exists():
                break
            time.sleep(0.5)
            yield "data: [waiting for log file...]\n\n"

        if not log_file.exists():
            yield f"data: [log file not found: {log_file.name}]\n\n"
            return

        with open(log_file, "r") as fh:
            # Deliver the last 200 lines as history
            all_lines = fh.readlines()
            for line in all_lines[-200:]:
                text = line.rstrip()
                if text:
                    yield f"data: {text}\n\n"

            # Tail — deliver new lines as they arrive
            while True:
                line = fh.readline()
                if line:
                    text = line.rstrip()
                    if text:
                        yield f"data: {text}\n\n"
                else:
                    time.sleep(0.3)

    response = StreamingHttpResponse(_event_stream(), content_type="text/event-stream")
    response["Cache-Control"]    = "no-cache"
    response["X-Accel-Buffering"] = "no"   # disable nginx buffering if behind a proxy
    return response
