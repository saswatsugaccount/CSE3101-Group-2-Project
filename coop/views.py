from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import DateRangeForm, MonthForm, SaleForm
from .models import ZERO, Crop, Delivery, Farmer, Sale, StockMovement

# Who can do what (checked on the server)
SALES_ROLES = ("ADMIN", "MANAGER", "STAFF")   # can record and edit sales
MANAGE_ROLES = ("ADMIN", "MANAGER")           # can delete sales and see reports


def has_role(user, *roles):
    return user.is_superuser or getattr(user, "role", None) in roles


def require_role(*roles):
    """Stop the request with 403 Forbidden if the user's role is not allowed."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not has_role(request.user, *roles):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return login_required(wrapper)
    return decorator


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


# ---------- SALES ----------

@require_role(*SALES_ROLES)
def sale_list(request):
    query = request.GET.get("q", "").strip()
    sales = Sale.objects.select_related("crop", "recorded_by")
    if query:
        sales = sales.filter(Q(crop__name__icontains=query) | Q(buyer_name__icontains=query))
    total = sales.aggregate(t=Sum("total_value"))["t"] or ZERO
    return render(request, "coop/sale_list.html", {"sales": sales, "query": query, "total": total})


@require_role(*SALES_ROLES)
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("crop", "recorded_by"), pk=pk)
    return render(request, "coop/sale_detail.html", {"sale": sale})


@require_role(*SALES_ROLES)
def sale_create(request):
    form = SaleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sale = form.save(commit=False)
        sale.recorded_by = request.user
        sale.save()
        messages.success(request, f"Sale saved. Total: GYD {sale.total_value}")
        return redirect("sale_detail", pk=sale.pk)
    return render(request, "coop/sale_form.html", {"form": form, "title": "Record a sale"})


@require_role(*SALES_ROLES)
def sale_update(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    # Business rule: staff can only edit sales they recorded themselves
    if not has_role(request.user, *MANAGE_ROLES) and sale.recorded_by != request.user:
        raise PermissionDenied
    form = SaleForm(request.POST or None, instance=sale)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Sale updated.")
        return redirect("sale_detail", pk=sale.pk)
    return render(request, "coop/sale_form.html", {"form": form, "title": "Edit sale", "sale": sale})


@require_role(*MANAGE_ROLES)
def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == "POST":
        sale.delete()
        messages.success(request, "Sale deleted. The stock has been updated.")
        return redirect("sale_list")
    # GET shows the "Are you sure?" page
    return render(request, "coop/sale_confirm_delete.html", {"sale": sale})


# ---------- REPORTS ----------

@require_role(*MANAGE_ROLES)
def report_monthly(request):
    """Report 1: total deliveries by produce type for a chosen month."""
    form = MonthForm(request.GET or None, initial={"month": timezone.localdate().strftime("%Y-%m")})
    rows, totals = None, None
    if form.is_valid():
        year, month = form.cleaned_data["month"]
        deliveries = Delivery.objects.filter(delivery_date__year=year, delivery_date__month=month)
        rows = (deliveries.values("crop__name", "crop__unit")
                .annotate(count=Count("id"), quantity=Sum("quantity"), value=Sum("total_value"))
                .order_by("-quantity"))
        totals = deliveries.aggregate(count=Count("id"), value=Sum("total_value"))
    return render(request, "coop/report_monthly.html", {"form": form, "rows": rows, "totals": totals})


@require_role(*MANAGE_ROLES)
def report_farmer(request):
    """Report 2: deliveries per farmer between two dates."""
    form = DateRangeForm(request.GET or None)
    rows, totals = None, None
    if form.is_valid():
        deliveries = Delivery.objects.filter(
            delivery_date__range=(form.cleaned_data["start"], form.cleaned_data["end"])
        )
        rows = (deliveries.values("farmer__farmer_id", "farmer__name")
                .annotate(count=Count("id"), quantity=Sum("quantity"), value=Sum("total_value"))
                .order_by("-value"))
        totals = deliveries.aggregate(count=Count("id"), value=Sum("total_value"))
    return render(request, "coop/report_farmer.html", {"form": form, "rows": rows, "totals": totals})


@require_role(*MANAGE_ROLES)
def report_stock(request):
    """Report 3: how much of each produce is in stock right now."""
    rows = []
    for crop in Crop.objects.filter(is_active=True):
        delivered = crop.deliveries.aggregate(t=Sum("quantity"))["t"] or ZERO
        sold = crop.sales.aggregate(t=Sum("quantity"))["t"] or ZERO
        adjust_in = crop.stock_movements.filter(movement_type="IN").aggregate(t=Sum("quantity"))["t"] or ZERO
        adjust_out = crop.stock_movements.filter(movement_type="OUT").aggregate(t=Sum("quantity"))["t"] or ZERO
        rows.append({
            "crop": crop,
            "delivered": delivered,
            "sold": sold,
            "adjustments": adjust_in - adjust_out,
            "available": delivered + adjust_in - sold - adjust_out,
        })
    return render(request, "coop/report_stock.html", {"rows": rows})