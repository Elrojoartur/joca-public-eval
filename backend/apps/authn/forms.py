from django import forms
from django.contrib.auth.forms import AuthenticationForm


class PortalAuthForm(AuthenticationForm):
    # Campo honeypot invisible: debe permanecer vacio
    verificacion = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"autocomplete": "off"}))

    def clean(self):
        cleaned = super().clean()
        # Si honeypot viene con valor, invalidar de forma generica
        if self.cleaned_data.get("verificacion"):
            raise forms.ValidationError(
                "No se pudo validar el acceso. Intenta de nuevo.")
        return cleaned
