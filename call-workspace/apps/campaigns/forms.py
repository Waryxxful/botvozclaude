from django import forms

from .models import Campaign


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "description", "script", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "class": "w-full"}),
            "name": forms.TextInput(attrs={"class": "w-full"}),
        }
