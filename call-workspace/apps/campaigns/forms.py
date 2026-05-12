from django import forms
from .models import Campaign, Agent

_inp = "w-full rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-500"


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "description", "ftp_directory", "script_text", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": _inp}),
            "description": forms.Textarea(attrs={"class": _inp, "rows": 2}),
            "ftp_directory": forms.TextInput(attrs={"class": _inp}),
            "script_text": forms.Textarea(attrs={"class": _inp, "rows": 8}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded border-gray-300 text-slate-700"}),
        }


class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = ["name", "employee_id", "campaigns", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": _inp}),
            "employee_id": forms.TextInput(attrs={"class": _inp}),
            "campaigns": forms.CheckboxSelectMultiple(),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded border-gray-300 text-slate-700"}),
        }
