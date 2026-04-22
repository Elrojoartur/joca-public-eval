from django import forms

from apps.ui.input_validation import (
    validate_email_value,
    validate_human_name,
    validate_phone,
    validate_required_text,
)


class ContactForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=150)
    email = forms.EmailField(label="Correo electrónico")
    telefono = forms.CharField(label="Teléfono", max_length=50, required=False)
    asunto = forms.CharField(label="Asunto", max_length=150, required=False)
    mensaje = forms.CharField(label="Mensaje", widget=forms.Textarea)
    security_answer = forms.CharField(
        label="Respuesta de seguridad", max_length=10)

    def clean_nombre(self):
        return validate_human_name(self.cleaned_data.get("nombre"), "Nombre")

    def clean_email(self):
        return validate_email_value(self.cleaned_data.get("email"), "Correo electrónico")

    def clean_telefono(self):
        return validate_phone(self.cleaned_data.get("telefono"), "Teléfono", allow_blank=True)

    def clean_asunto(self):
        return validate_required_text(self.cleaned_data.get("asunto") or "Contacto", "Asunto")

    def clean_mensaje(self):
        return validate_required_text(self.cleaned_data.get("mensaje"), "Mensaje")
