from django import forms

from apps.fatti.models import SegnalazioneErrore


class SegnalazioneForm(forms.ModelForm):
    class Meta:
        model = SegnalazioneErrore
        fields = ["testo", "email"]
        labels = {"testo": "Cosa non è corretto?", "email": "Email (facoltativa)"}
        widgets = {"testo": forms.Textarea(attrs={"rows": 3})}
