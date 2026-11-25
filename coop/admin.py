from django.contrib import admin

from .models import Crop, Delivery, Farmer, Sale, StockMovement


@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ("farmer_id", "name", "phone", "village", "is_active")
    search_fields = ("farmer_id", "name", "phone")


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "unit", "price_per_unit", "is_active")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("delivery_date", "farmer", "crop", "quantity", "total_value")
    readonly_fields = ("unit_price", "total_value", "recorded_by")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("movement_date", "crop", "movement_type", "quantity", "reason")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("sale_date", "crop", "quantity", "unit_price", "total_value", "buyer_name")
    readonly_fields = ("total_value", "recorded_by")