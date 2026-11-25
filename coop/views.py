from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Crop, Delivery, Farmer, Sale


@login_required
def home(request):
    """Dashboard shown after login."""
    context = {
        "farmer_count": Farmer.objects.filter(is_active=True).count(),
        "crop_count": Crop.objects.filter(is_active=True).count(),
        "delivery_count": Delivery.objects.count(),
        "sale_count": Sale.objects.count(),
    }
    return render(request, "coop/home.html", context)