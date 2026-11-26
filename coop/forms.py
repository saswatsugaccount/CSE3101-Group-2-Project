from django import forms

from .models import Crop, Sale


class SaleForm(forms.ModelForm):
    """Form to record or edit a sale. Checks are done on the server."""

    class Meta:
        model = Sale
        fields = ["crop", "quantity", "unit_price", "buyer_name", "sale_date"]
        widgets = {
            "sale_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show crops that are still active
        self.fields["crop"].queryset = Crop.objects.filter(is_active=True)
        # Bootstrap styling for every box
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = css


class MonthForm(forms.Form):
    """Pick a month for the monthly delivery report."""
    month = forms.CharField(widget=forms.TextInput(attrs={"type": "month", "class": "form-control"}))

    def clean_month(self):
        value = self.cleaned_data["month"]
        try:
            year, month = value.split("-")
            return int(year), int(month)
        except ValueError:
            raise forms.ValidationError("Please choose a valid month.")


class DateRangeForm(forms.Form):
    """Pick a start and end date for the farmer delivery report."""
    start = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    end = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start"), cleaned.get("end")
        if start and end and start > end:
            raise forms.ValidationError("The start date must be before the end date.")
        return cleaned