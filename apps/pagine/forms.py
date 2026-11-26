from django import forms

from apps.fatti.models import SegnalazioneErrore


class SegnalazioneForm(forms.ModelForm):
    class Meta:
        model = SegnalazioneErrore
        fields = ["testo", "email"]
        labels = {"testo": "Cosa non è corretto?", "email": "Email (facoltativa)"}
        widgets = {"testo": forms.Textarea(attrs={"rows": 3})}


class ContattoForm(forms.Form):
    MOTIVI = [
        ("informazioni", "Informazioni o collaborazioni"),
        ("errore", "Errore in una scheda"),
        ("rimozione", "Rettifica o rimozione di un contenuto che mi riguarda"),
        ("privacy", "Richiesta sui miei dati personali"),
        ("altro", "Altro"),
    ]
    motivo = forms.ChoiceField(choices=MOTIVI)
    nome = forms.CharField(max_length=100, required=False, label="Nome (facoltativo)")
    email = forms.EmailField(label="La tua email, per risponderti")
    messaggio = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}), max_length=5000)
    # campo trappola per i programmi di spam: le persone non lo vedono e lo lasciano vuoto
    sito_web = forms.CharField(required=False, label="Lascia vuoto questo campo")
