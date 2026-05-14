from django import forms

from apps.campaigns.models import Campaign


class BatchUploadForm(forms.Form):
    campaign = forms.ModelChoiceField(queryset=Campaign.objects.filter(is_active=True))
    csv_file = forms.FileField(help_text="CSV con columnas phone_number + parámetros del script.")
