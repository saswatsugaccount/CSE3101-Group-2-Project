from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

ZERO = Decimal("0")
CENT = Decimal("0.01")


def not_in_future(value):
    """Business rule: a record cannot be dated in the future."""
    if value and value > timezone.localdate():
        raise ValidationError("The date cannot be in the future.")


class Farmer(models.Model):
    farmer_id = models.CharField("Farmer ID", max_length=20, unique=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    village = models.CharField("Village / region", max_length=100)
    date_joined = models.DateField(default=timezone.localdate, validators=[not_in_future])
    is_active = models.BooleanField(default=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="farmer_profile",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.farmer_id})"


class Crop(models.Model):
    class Unit(models.TextChoices):
        KG = "KG", "Kilogram (kg)"
        BAG = "BAG", "Bag"
        BUNCH = "BUNCH", "Bunch"
        DOZEN = "DOZEN", "Dozen"

    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.KG)
    price_per_unit = models.DecimalField(
        "Price paid to farmer per unit (GYD)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(CENT)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def available_stock(self):
        """Stock now = delivered + stock in - sold - stock out."""
        delivered = self.deliveries.aggregate(t=Sum("quantity"))["t"] or ZERO
        sold = self.sales.aggregate(t=Sum("quantity"))["t"] or ZERO
        moved_in = self.stock_movements.filter(movement_type="IN").aggregate(t=Sum("quantity"))["t"] or ZERO
        moved_out = self.stock_movements.filter(movement_type="OUT").aggregate(t=Sum("quantity"))["t"] or ZERO
        return delivered + moved_in - sold - moved_out


def check_enough_stock(record, old_quantity_out=ZERO):
    """Business rule: you cannot take out more produce than is in stock."""
    if not record.crop_id or record.quantity is None:
        return
    available = record.crop.available_stock() + old_quantity_out
    if record.quantity > available:
        raise ValidationError(
            {"quantity": f"Only {available} {record.crop.get_unit_display()} of {record.crop.name} is in stock."}
        )


class Delivery(models.Model):
    """Produce a farmer brings to the cooperative."""
    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, related_name="deliveries")
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="deliveries")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(CENT)])
    delivery_date = models.DateField(default=timezone.localdate, validators=[not_in_future])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=ZERO)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=ZERO)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="deliveries_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-delivery_date", "-id"]
        verbose_name_plural = "deliveries"

    def __str__(self):
        return f"{self.quantity} {self.crop} from {self.farmer.name} on {self.delivery_date}"

    def save(self, *args, **kwargs):
        # Business rule: value = quantity x the crop's price
        if not self.unit_price:
            self.unit_price = self.crop.price_per_unit
        self.total_value = (self.quantity * self.unit_price).quantize(CENT)
        super().save(*args, **kwargs)


class StockMovement(models.Model):
    """Manual stock changes that are not deliveries or sales (e.g. spoiled produce)."""
    class Type(models.TextChoices):
        IN = "IN", "Stock in (adjustment)"
        OUT = "OUT", "Stock out (spoiled, damaged, lost)"

    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="stock_movements")
    movement_type = models.CharField(max_length=3, choices=Type.choices)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(CENT)])
    reason = models.CharField(max_length=200)
    movement_date = models.DateField(default=timezone.localdate, validators=[not_in_future])
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="stock_movements_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-movement_date", "-id"]

    def __str__(self):
        return f"{self.get_movement_type_display()}: {self.quantity} {self.crop}"

    def clean(self):
        super().clean()
        if self.movement_type == self.Type.OUT:
            old = ZERO
            if self.pk:
                prev = StockMovement.objects.filter(pk=self.pk).first()
                if prev and prev.crop_id == self.crop_id and prev.movement_type == "OUT":
                    old = prev.quantity
            check_enough_stock(self, old)


class Sale(models.Model):
    """Produce the cooperative sells."""
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="sales")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(CENT)])
    unit_price = models.DecimalField(
        "Selling price per unit (GYD)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(CENT)],
    )
    buyer_name = models.CharField(max_length=100, blank=True)
    sale_date = models.DateField(default=timezone.localdate, validators=[not_in_future])
    total_value = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=ZERO)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="sales_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sale_date", "-id"]

    def __str__(self):
        return f"Sale of {self.quantity} {self.crop} on {self.sale_date}"

    def clean(self):
        super().clean()
        old = ZERO
        if self.pk:
            prev = Sale.objects.filter(pk=self.pk).first()
            if prev and prev.crop_id == self.crop_id:
                old = prev.quantity
        check_enough_stock(self, old)  # business rule: cannot sell more than in stock

    def save(self, *args, **kwargs):
        # Business rule: transaction value = quantity x selling price
        self.total_value = (self.quantity * self.unit_price).quantize(CENT)
        super().save(*args, **kwargs)