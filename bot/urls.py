from django.urls import path
from . import views

app_name = "bot"

urlpatterns = [
    path("control/",       views.bot_control_page, name="control"),
    path("start/",         views.bot_start,         name="start"),
    path("stop/",          views.bot_stop,           name="stop"),
    path("status/",        views.bot_status_api,     name="status"),
    path("logs/stream/",   views.log_stream,         name="log_stream"),
]
