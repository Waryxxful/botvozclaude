from django import forms
from .models import Script, TTS_VOICE_CHOICES, AgentGlobalConfig


class ScriptForm(forms.ModelForm):
    class Meta:
        model = Script
        fields = [
            "name", "description", "greeting", "prompt_template",
            "tts_voice", "tts_speed", "tts_pitch",
            "llm_temperature", "llm_max_tokens",
            "vad_silence_ms", "max_call_duration_seconds",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "greeting": forms.TextInput(attrs={"class": "form-control"}),
            "prompt_template": forms.Textarea(attrs={"rows": 12, "class": "form-control font-monospace"}),
            "tts_voice": forms.Select(attrs={"class": "form-select"}),
            "tts_speed": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "min": "0.5", "max": "2.0"}),
            "tts_pitch": forms.NumberInput(attrs={"class": "form-control", "step": "1", "min": "-10", "max": "10"}),
            "llm_temperature": forms.NumberInput(attrs={"class": "form-control", "step": "0.05", "min": "0", "max": "1"}),
            "llm_max_tokens": forms.NumberInput(attrs={"class": "form-control", "min": "50", "max": "1000"}),
            "vad_silence_ms": forms.NumberInput(attrs={"class": "form-control", "min": "300", "max": "3000", "step": "100"}),
            "max_call_duration_seconds": forms.NumberInput(attrs={"class": "form-control", "min": "60", "max": "1800"}),
        }


class GlobalConfigForm(forms.ModelForm):
    class Meta:
        model = AgentGlobalConfig
        fields = ["tts_voice", "tts_speed", "tts_pitch", "llm_temperature",
                  "llm_max_tokens", "vad_silence_ms", "max_call_duration_seconds"]
        widgets = {
            "tts_voice": forms.Select(attrs={"class": "form-select"}),
            "tts_speed": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "min": "0.5", "max": "2.0"}),
            "tts_pitch": forms.NumberInput(attrs={"class": "form-control", "step": "1", "min": "-10", "max": "10"}),
            "llm_temperature": forms.NumberInput(attrs={"class": "form-control", "step": "0.05", "min": "0", "max": "1"}),
            "llm_max_tokens": forms.NumberInput(attrs={"class": "form-control", "min": "50", "max": "1000"}),
            "vad_silence_ms": forms.NumberInput(attrs={"class": "form-control", "min": "300", "max": "3000", "step": "100"}),
            "max_call_duration_seconds": forms.NumberInput(attrs={"class": "form-control", "min": "60", "max": "1800"}),
        }
