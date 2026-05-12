from django import forms

from .models import Script


class ScriptForm(forms.ModelForm):
    class Meta:
        model = Script
        fields = ["name", "description", "prompt_template", "greeting"]
        widgets = {
            "prompt_template": forms.Textarea(attrs={"rows": 12, "class": "w-full font-mono text-sm"}),
            "description": forms.Textarea(attrs={"rows": 2, "class": "w-full"}),
            "name": forms.TextInput(attrs={"class": "w-full"}),
            "greeting": forms.TextInput(attrs={"class": "w-full"}),
        }
