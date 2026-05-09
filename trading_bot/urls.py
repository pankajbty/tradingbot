from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Trading Bot Admin — NSE Equities & Crypto"
admin.site.site_title  = "Trading Bot"
admin.site.index_title = "Strategy Configuration (Equities + Crypto)"

urlpatterns = [
    path("admin/",  admin.site.urls),
    path("bot/",    include("bot.urls",    namespace="bot")),
    path("crypto/", include("crypto.urls", namespace="crypto")),
]
