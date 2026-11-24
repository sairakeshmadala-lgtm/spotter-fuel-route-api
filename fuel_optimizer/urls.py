from django.urls import path
from .views import fuel_prices, route_preview, fuel_optimize

urlpatterns = [
    path("fuel-prices/", fuel_prices, name="fuel-prices"),
    path("route/", route_preview, name="route-preview"),
    path("fuel-optimize/", fuel_optimize, name="fuel-optimize"),
]