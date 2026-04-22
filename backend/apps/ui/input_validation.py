import re
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

HUMAN_NAME_RE = re.compile(
    r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{4,32}$")
MATRICULA_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{2,31}$")
PHONE_RE = re.compile(r"^[0-9+()\-\s]{7,20}$")
PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
RFC13_RE = re.compile(r"^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$")
CURP_RE = re.compile(
    r"^[A-Z][AEIOUX][A-Z]{2}\d{2}(0[1-9]|1[0-2])"
    r"(0[1-9]|[12]\d|3[01])[HM]"
    r"(AS|BC|BS|CC|CS|CH|CL|CM|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)"
    r"[B-DF-HJ-NP-TV-Z]{3}[0-9A-Z]\d$"
)
CP5_RE = re.compile(r"^[0-9]{5}$")
HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
AUTH_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{0,40}$")
TEXT_GENERAL_RE = re.compile(
    r"^[A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ\s.,;:()#%\-_/+@]+$")


def normalize_text(value):
    return " ".join((value or "").strip().split())


def validate_required_text(value, field_label="Campo"):
    text = normalize_text(value)
    if not text:
        raise ValidationError(f"{field_label} es obligatorio.")
    return text


def validate_human_name(value, field_label="Nombre", allow_blank=False):
    text = normalize_text(value)
    if not text:
        if allow_blank:
            return ""
        raise ValidationError(f"{field_label} es obligatorio.")

    if not HUMAN_NAME_RE.match(text):
        raise ValidationError(
            f"{field_label} inválido. Solo se permiten letras y espacios."
        )
    return text


def validate_email_value(value, field_label="Correo"):
    email = normalize_text(value).lower()
    if not email:
        raise ValidationError(f"{field_label} es obligatorio.")
    try:
        validate_email(email)
    except ValidationError:
        raise ValidationError(f"{field_label} inválido.")
    return email


def validate_phone(value, field_label="Teléfono", allow_blank=True):
    phone = normalize_text(value)
    if not phone:
        if allow_blank:
            return ""
        raise ValidationError(f"{field_label} es obligatorio.")
    if not PHONE_RE.match(phone):
        raise ValidationError(f"{field_label} inválido.")
    return phone


def validate_username_value(value):
    username = normalize_text(value)
    if not USERNAME_RE.match(username):
        raise ValidationError(
            "Usuario inválido. Usa 4-32 caracteres con letras, números, punto, guion o guion bajo."
        )
    return username


def validate_matricula_value(value):
    matricula = normalize_text(value).upper()
    if not MATRICULA_RE.match(matricula):
        raise ValidationError(
            "Matrícula inválida. Ingrese letras mayúsculas y números solamente (3-32 caracteres)."
        )
    return matricula


def validate_periodo_value(value):
    periodo = normalize_text(value)
    if not PERIODO_RE.match(periodo):
        raise ValidationError("Periodo inválido. Usa formato YYYY-MM.")
    return periodo


def validate_rfc13(value, field_label="RFC"):
    rfc = normalize_text(value).upper()
    if not RFC13_RE.match(rfc):
        raise ValidationError(
            f"{field_label} inválido. Usa formato mexicano vigente (12 o 13 caracteres, ej. XAXX010101000)."
        )

    # Estructura fecha AAMMDD inmediatamente despues del prefijo (3 moral / 4 fisica).
    date_start = 4 if len(rfc) == 13 else 3
    yy = int(rfc[date_start:date_start + 2])
    mm = int(rfc[date_start + 2:date_start + 4])
    dd = int(rfc[date_start + 4:date_start + 6])
    try:
        date(2000 + yy if yy <= 30 else 1900 + yy, mm, dd)
    except ValueError:
        raise ValidationError(
            f"{field_label} inválido: la fecha (AAMMDD) no es válida."
        )

    return rfc


def validate_curp_value(value, field_label="CURP"):
    curp = normalize_text(value).upper()
    if not curp:
        raise ValidationError(f"{field_label} es obligatorio.")

    if not CURP_RE.match(curp):
        raise ValidationError(
            f"{field_label} inválida. Usa el formato oficial de 18 caracteres."
        )

    yy = int(curp[4:6])
    mm = int(curp[6:8])
    dd = int(curp[8:10])
    try:
        date(2000 + yy if yy <= 30 else 1900 + yy, mm, dd)
    except ValueError:
        raise ValidationError(
            f"{field_label} inválida: la fecha de nacimiento no es válida."
        )

    return curp


def validate_cp5(value, field_label="Código postal"):
    cp = normalize_text(value)
    if not CP5_RE.match(cp):
        raise ValidationError(f"{field_label} inválido. Debe tener 5 dígitos.")
    return cp


def validate_choice(value, allowed_values, field_label="Campo"):
    candidate = normalize_text(value)
    if candidate not in set(allowed_values):
        raise ValidationError(f"{field_label} inválido.")
    return candidate


def validate_hhmm(value, field_label="Hora"):
    text = normalize_text(value)
    if not HHMM_RE.match(text):
        raise ValidationError(f"{field_label} inválida. Usa formato HH:MM.")
    return text


def validate_int_range(value, min_value, max_value, field_label="Campo"):
    text = normalize_text(value)
    try:
        number = int(text)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_label} inválido.")
    if number < min_value or number > max_value:
        raise ValidationError(
            f"{field_label} fuera de rango ({min_value}-{max_value})."
        )
    return str(number)


def validate_password_strength(value, min_length=8, field_label="Contraseña"):
    password = value or ""
    if len(password) < min_length:
        raise ValidationError(
            f"{field_label} debe tener al menos {min_length} caracteres.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValidationError(
            f"{field_label} debe incluir al menos una letra y un número."
        )
    return password


def validate_auth_code(value, field_label="Referencia"):
    text = normalize_text(value)
    if not AUTH_CODE_RE.match(text):
        raise ValidationError(
            f"{field_label} inválida. Usa solo letras, números, guion y guion bajo."
        )
    return text


def validate_text_general(
    value,
    field_label="Campo",
    allow_blank=False,
    min_length=1,
    max_length=250,
):
    text = normalize_text(value)
    if not text:
        if allow_blank:
            return ""
        raise ValidationError(f"{field_label} es obligatorio.")

    if len(text) < int(min_length) or len(text) > int(max_length):
        raise ValidationError(
            f"{field_label} inválido. Longitud permitida: {min_length}-{max_length} caracteres."
        )

    if not TEXT_GENERAL_RE.match(text):
        raise ValidationError(
            f"{field_label} inválido. Usa solo letras, números y signos básicos (. , ; : ( ) # % - _ / + @)."
        )

    return text


def sanitize_csv_cell(value):
    text = "" if value is None else str(value)
    if text and text[0] in {"=", "+", "-", "@"}:
        return "'" + text
    return text
