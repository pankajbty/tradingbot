from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Trading Bot Admin"
admin.site.site_title  = "Trading Bot"
admin.site.index_title = "Strategy Configuration"

urlpatterns = [
    path("admin/",  admin.site.urls),
    path("bot/",    include("bot.urls", namespace="bot")),
]
