from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),

    # Sales
    path("sales/", views.sale_list, name="sale_list"),
    path("sales/new/", views.sale_create, name="sale_create"),
    path("sales/<int:pk>/", views.sale_detail, name="sale_detail"),
    path("sales/<int:pk>/edit/", views.sale_update, name="sale_update"),
    path("sales/<int:pk>/delete/", views.sale_delete, name="sale_delete"),

    # Reports
    path("reports/monthly/", views.report_monthly, name="report_monthly"),
    path("reports/farmers/", views.report_farmer, name="report_farmer"),
    path("reports/stock/", views.report_stock, name="report_stock"),
]