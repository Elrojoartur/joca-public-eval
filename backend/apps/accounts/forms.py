from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from apps.ui.input_validation import (
    validate_email_value,
    validate_human_name,
    validate_username_value,
)

User = get_user_model()


class UsuarioCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "required": True}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname in ("password1", "password2"):
            if fname in self.fields:
                self.fields[fname].widget.attrs["class"] = "form-control"
        # Email es obligatorio para que funcione la recuperación de acceso.
        self.fields["email"].required = True
        # Guía para el operador sobre cómo se asigna el username según el rol.
        self.fields["username"].help_text = (
            "Para <strong>Alumno</strong>: ingresa la matrícula del alumno. "
            "Para <strong>Superusuario, Director Escolar y Administrativo Comercial</strong> "
            "el nombre de usuario se genera automáticamente al asignar el rol "
            "(el valor que escribas aquí será reemplazado)."
        )

    def clean_username(self):
        username = validate_username_value(self.cleaned_data.get("username"))
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError("Ese usuario ya existe. Elige otro.")
        return username

    def clean_email(self):
        email = validate_email_value(self.cleaned_data.get("email"), "Correo")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ese correo ya está registrado.")
        return email

    def clean_first_name(self):
        return validate_human_name(self.cleaned_data.get("first_name"), "Nombre", allow_blank=True)

    def clean_last_name(self):
        return validate_human_name(self.cleaned_data.get("last_name"), "Apellido", allow_blank=True)


class UsuarioEditForm(forms.ModelForm):
    """Formulario de edición: solo nombre, apellido y acceso staff."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "is_staff")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_first_name(self):
        return validate_human_name(self.cleaned_data.get("first_name"), "Nombre", allow_blank=True)

    def clean_last_name(self):
        return validate_human_name(self.cleaned_data.get("last_name"), "Apellido", allow_blank=True)


class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name",
                  "last_name", "is_active", "is_staff")

    def clean_username(self):
        # Evita cambios de username
        if self.instance and self.instance.pk:
            return self.instance.username
        return super().clean_username()

    def clean_email(self):
        # Evita cambios de email en edición
        if self.instance and self.instance.pk:
            return self.instance.email
        return super().clean_email()


class UsuarioCreateFormUI(UserCreationForm):
    """Formulario de alta de usuario para la interfaz de gobierno.

    El username se genera automáticamente según el rol seleccionado;
    no es visible ni editable por el operador.
    """

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname in ("password1", "password2"):
            if fname in self.fields:
                self.fields[fname].widget.attrs["class"] = "form-control"
        # El username no forma parte del formulario; se asignará externamente.
        self.fields.pop("username", None)

    def clean_email(self):
        email = validate_email_value(self.cleaned_data.get("email"), "Correo")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ese correo ya está registrado.")
        return email

    def clean_first_name(self):
        return validate_human_name(
            self.cleaned_data.get("first_name"), "Nombre", allow_blank=True
        )

    def clean_last_name(self):
        return validate_human_name(
            self.cleaned_data.get("last_name"), "Apellido", allow_blank=True
        )
