"""Custom validators for the school app."""

import datetime
import re

from django.core.exceptions import ValidationError

CURP_RE = re.compile(
    r'^[A-Z][AEIOUX][A-Z]{2}\d{2}(0[1-9]|1[0-2])'
    r'(0[1-9]|[12]\d|3[01])[HM]'
    r'(AS|BC|BS|CC|CS|CH|CL|CM|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)'
    r'[B-DF-HJ-NP-TV-Z]{3}[0-9A-Z]\d$'
)

RFC10_RE = re.compile(r'^[A-Z&Ñ]{4}\d{6}$')
RFC_MX_RE = re.compile(r'^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$')

_CURP_DICT = {str(i): i for i in range(10)}
# A=10 ... N=23, Ñ=24, O=25 ... Z=36
for idx, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=10):
    _CURP_DICT[ch] = idx
_CURP_DICT["Ñ"] = 24  # entre N y O, ajusta O..Z +1
# Re-ajuste: O debe ser 25, P 26 ... Z 36
for idx, ch in enumerate("OPQRSTUVWXYZ", start=25):
    _CURP_DICT[ch] = idx


def _curp_check_digit(curp17: str) -> str:
    total = 0
    weights = list(range(18, 1, -1))  # 18..2 (17 valores)
    for ch, w in zip(curp17, weights):
        v = _CURP_DICT.get(ch, 0)
        total += v * w
    dv = (10 - (total % 10)) % 10
    return str(dv)

def validate_curp(value: str):
    curp = (value or "").strip().upper()
    if not curp:
        return
    if not CURP_RE.match(curp):
        raise ValidationError(
            "CURP inválida. Revisa formato y datos (fecha/estado/sexo).")

    # valida fecha
    yy = int(curp[4:6])
    mm = int(curp[6:8])
    dd = int(curp[8:10])
    # (No inferimos siglo; solo verificamos que sea una fecha posible)
    try:
        datetime.date(2000 + yy if yy <= 30 else 1900 + yy, mm, dd)
    except ValueError:
        raise ValidationError(
            "CURP inválida: la fecha de nacimiento no es válida.")

    # dígito verificador (último)
    expected = _curp_check_digit(curp[:17])
    if curp[-1] != expected:
        raise ValidationError("CURP inválida: dígito verificador no coincide.")


def validate_rfc_mexico(value: str):
    rfc = (value or "").strip().upper()
    if not rfc:
        return
    if not RFC_MX_RE.match(rfc):
        raise ValidationError(
            "RFC inválido. Debe tener formato mexicano vigente de 12 o 13 caracteres (incluye homoclave).")

    date_start = 4 if len(rfc) == 13 else 3
    yy = int(rfc[date_start:date_start + 2])
    mm = int(rfc[date_start + 2:date_start + 4])
    dd = int(rfc[date_start + 4:date_start + 6])
    try:
        datetime.date(2000 + yy if yy <= 30 else 1900 + yy, mm, dd)
    except ValueError:
        raise ValidationError("RFC inválido: la fecha (AAMMDD) no es válida.")


_CP_RE = re.compile(r'^\d{5}$')


def validate_codigo_postal(value: str):
    cp = (value or "").strip()
    if not cp:
        return
    if not _CP_RE.match(cp):
        raise ValidationError(
            "El código postal debe tener exactamente 5 dígitos numéricos."
        )


def validate_rfc_sin_homoclave(value: str):
    """Compatibilidad retroactiva: redirige al validador oficial vigente."""
    return validate_rfc_mexico(value)
