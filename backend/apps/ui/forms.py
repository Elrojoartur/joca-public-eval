from django import forms
from django.db import transaction
from django.utils import timezone

from apps.school.models import Alumno, AlumnoDomicilio, Grupo, Inscripcion, Calificacion, ActaCierre
from apps.ui.input_validation import (
    validate_curp_value,
    validate_email_value,
    validate_human_name,
    validate_phone,
    validate_rfc13,
    validate_cp5,
)


def _bootstrapize_form_fields(form):
    for field in form.fields.values():
        widget = field.widget
        css_class = widget.attrs.get("class", "")

        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            base_class = "form-select"
        elif isinstance(widget, forms.CheckboxInput):
            base_class = "form-check-input"
        else:
            base_class = "form-control"

        widget.attrs["class"] = f"{css_class} {base_class}".strip()


class AlumnoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapize_form_fields(self)

        for field in self.fields.values():
            widget = field.widget
            css_class = widget.attrs.get("class", "")

            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                if "form-select-sm" not in css_class:
                    widget.attrs["class"] = f"{css_class} form-select-sm".strip()
            elif not isinstance(widget, forms.CheckboxInput):
                if "form-control-sm" not in css_class:
                    widget.attrs["class"] = f"{css_class} form-control-sm".strip()

        self.fields["curp"].widget.attrs.setdefault(
            "placeholder", "CURP oficial (18 caracteres)"
        )
        self.fields["rfc"].widget.attrs.setdefault(
            "placeholder", "RFC vigente (12 o 13, ej. XAXX010101000)"
        )

    class Meta:
        model = Alumno
        fields = [
            "nombres",
            "apellido_paterno",
            "apellido_materno",
            "correo",
            "telefono",
            "curp",
            "rfc",
        ]
        error_messages = {
            "correo": {
                "unique": "Ya existe un alumno con este correo.",
                "required": "El correo es obligatorio.",
            },
            "curp": {
                "unique": "Ya existe un alumno con esta CURP.",
            },
            "rfc": {
                "invalid": "El RFC no tiene un formato válido.",
            },
        }

    def clean_curp(self):
        curp = (self.cleaned_data.get("curp") or "").strip().upper()
        if not curp:
            return None
        return validate_curp_value(curp, "CURP")

    def clean_nombres(self):
        return validate_human_name(self.cleaned_data.get("nombres"), "Nombres")

    def clean_apellido_paterno(self):
        return validate_human_name(
            self.cleaned_data.get("apellido_paterno"),
            "Apellido paterno",
        )

    def clean_apellido_materno(self):
        return validate_human_name(
            self.cleaned_data.get("apellido_materno"),
            "Apellido materno",
            allow_blank=True,
        )

    def clean_correo(self):
        return validate_email_value(self.cleaned_data.get("correo"), "Correo")

    def clean_telefono(self):
        return validate_phone(
            self.cleaned_data.get("telefono"),
            "Teléfono",
            allow_blank=True,
        )

    def clean_rfc(self):
        rfc = (self.cleaned_data.get("rfc") or "").strip().upper()
        if not rfc:
            return None
        return validate_rfc13(rfc, "RFC")

    @transaction.atomic
    def save_with_domicilio(self, domicilio_form, commit=True):
        """
        Guarda Alumno y AlumnoDomicilio en una sola transacción.

        Si domicilio_form.is_valid() es False, se lanza ValueError para que
        la vista lo gestione antes de llamar este método.
        """
        if not domicilio_form.is_valid():
            raise ValueError("El formulario de domicilio contiene errores.")

        alumno = self.save(commit=commit)

        if commit:
            dom = domicilio_form.save(commit=False)
            dom.alumno = alumno
            dom.save()

        return alumno

    @transaction.atomic
    def save_full_expediente(self, domicilio_form, inscripcion_form, commit=True):
        """
        Guarda Alumno + AlumnoDomicilio + Inscripcion inicial en una sola
        transacción atómica.
        inscripcion_form debe ser InscripcionInicialForm (campo grupo
        es requerido=False).  Si no se selecciona grupo no se crea
        inscripción.
        """
        alumno = self.save_with_domicilio(domicilio_form, commit=commit)
        if commit and inscripcion_form.is_valid():
            grupo = inscripcion_form.cleaned_data.get("grupo")
            if grupo:
                insc_activa = Inscripcion.objects.filter(
                    alumno=alumno, estado=Inscripcion.ESTADO_ACTIVA
                ).first()
                if insc_activa:
                    if insc_activa.grupo_id != grupo.pk:
                        insc_activa.grupo = grupo
                        insc_activa.save(update_fields=["grupo"])
                elif not Inscripcion.objects.filter(
                    alumno=alumno, grupo=grupo
                ).exists():
                    Inscripcion.objects.create(
                        alumno=alumno,
                        grupo=grupo,
                        fecha_inscripcion=timezone.localdate(),
                        estado=Inscripcion.ESTADO_ACTIVA,
                    )
        return alumno


class AlumnoDomicilioForm(forms.ModelForm):
    """
    Formulario para la información de domicilio complementaria del Alumno.
    Se usa junto con AlumnoForm; no expone el campo alumno al usuario.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapize_form_fields(self)

        for field in self.fields.values():
            widget = field.widget
            css_class = widget.attrs.get("class", "")
            if not isinstance(widget, forms.CheckboxInput):
                if "form-control-sm" not in css_class:
                    widget.attrs["class"] = f"{css_class} form-control-sm".strip()

        # pais tiene default en modelo pero no blank=True; no obligar al usuario.
        self.fields["pais"].required = False

        self.fields["calle"].widget.attrs.setdefault("placeholder", "Calle")
        self.fields["numero"].widget.attrs.setdefault(
            "placeholder", "Número ext./int.")
        self.fields["colonia"].widget.attrs.setdefault(
            "placeholder", "Colonia")
        self.fields["codigo_postal"].widget.attrs.setdefault(
            "placeholder", "5 dígitos")
        self.fields["estado"].widget.attrs.setdefault(
            "placeholder", "Estado / Provincia")
        self.fields["pais"].widget.attrs.setdefault("placeholder", "País")

    class Meta:
        model = AlumnoDomicilio
        fields = ["calle", "numero", "colonia",
                  "codigo_postal", "estado", "pais"]
        error_messages = {
            "codigo_postal": {
                "invalid": "El código postal debe tener exactamente 5 dígitos.",
            },
        }

    def clean_codigo_postal(self):
        cp = (self.cleaned_data.get("codigo_postal") or "").strip()
        if not cp:
            return ""
        return validate_cp5(cp, "Código postal")

    def clean_calle(self):
        return (self.cleaned_data.get("calle") or "").strip()

    def clean_numero(self):
        return (self.cleaned_data.get("numero") or "").strip()

    def clean_colonia(self):
        return (self.cleaned_data.get("colonia") or "").strip()

    def clean_estado(self):
        return (self.cleaned_data.get("estado") or "").strip()

    def clean_pais(self):
        pais = (self.cleaned_data.get("pais") or "").strip()
        return pais if pais else "México"


class InscripcionInicialForm(forms.Form):
    """
    Selector de grupo para la inscripción inicial dentro del flujo de
    alta / edición de alumno.  El campo es opcional: si no se elige grupo
    no se genera inscripción.
    """

    grupo = forms.ModelChoiceField(
        queryset=Grupo.objects.none(),  # se asigna en __init__
        required=False,
        label="Grupo",
        empty_label="— Sin inscripción inicial —",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo"].queryset = (
            Grupo.objects.filter(estado=Grupo.ESTADO_ACTIVO)
            .select_related("curso_ref", "periodo_ref")
            .order_by("periodo_ref__codigo", "curso_ref__nombre")
        )
        _bootstrapize_form_fields(self)
        widget = self.fields["grupo"].widget
        css = widget.attrs.get("class", "")
        if "form-select-sm" not in css:
            widget.attrs["class"] = f"{css} form-select-sm".strip()

    def clean_grupo(self):
        grupo = self.cleaned_data.get("grupo")
        if not grupo:
            return grupo
        if grupo.estado != Grupo.ESTADO_ACTIVO:
            raise forms.ValidationError(
                "Ese grupo está inactivo. Elige otro grupo activo."
            )
        ocupados = Inscripcion.objects.filter(
            grupo=grupo
        ).exclude(estado=Inscripcion.ESTADO_BAJA).count()
        if ocupados >= grupo.cupo:
            raise forms.ValidationError(
                "Ese grupo ya no tiene lugares disponibles."
            )
        return grupo


class GrupoForm(forms.ModelForm):
    """
    Formulario de Grupo (sin campos legacy de horario).
    El horario se gestiona mediante el modelo GrupoHorario.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapize_form_fields(self)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("curso_ref"):
            raise forms.ValidationError("Debes seleccionar un curso.")
        if not cleaned.get("periodo_ref"):
            raise forms.ValidationError(
                "Debes seleccionar un periodo académico.")
        return cleaned

    class Meta:
        model = Grupo
        fields = ("curso_ref", "periodo_ref", "tipo_horario", "cupo", "estado")
        labels = {
            "curso_ref": "Curso",
            "periodo_ref": "Periodo académico",
        }


class InscripcionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapize_form_fields(self)

    class Meta:
        model = Inscripcion
        fields = ["alumno", "grupo", "fecha_inscripcion", "estado"]

    def clean(self):
        cleaned = super().clean()
        alumno = cleaned.get("alumno")
        grupo = cleaned.get("grupo")
        estado = cleaned.get("estado")

        if alumno and grupo:
            qs = Inscripcion.objects.filter(alumno=alumno, grupo=grupo)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Este alumno ya está inscrito en ese grupo."
                )

        if grupo:
            if grupo.estado != Grupo.ESTADO_ACTIVO:
                raise forms.ValidationError(
                    "Ese grupo está inactivo. Actívalo o elige otro."
                )

            if estado != Inscripcion.ESTADO_BAJA:
                ocupados = Inscripcion.objects.filter(grupo=grupo).exclude(
                    estado=Inscripcion.ESTADO_BAJA
                )
                if self.instance and self.instance.pk:
                    ocupados = ocupados.exclude(pk=self.instance.pk)
                if ocupados.count() >= grupo.cupo:
                    raise forms.ValidationError(
                        "Este grupo ya no tiene lugares disponibles."
                    )

        return cleaned


class CalificacionForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        self._acta_cierre = None
        super().__init__(*args, **kwargs)
        _bootstrapize_form_fields(self)

    class Meta:
        model = Calificacion
        fields = ["inscripcion", "valor"]

    def clean(self):
        cleaned = super().clean()
        inscripcion = cleaned.get("inscripcion")

        if inscripcion:
            qs = Calificacion.objects.filter(inscripcion=inscripcion)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Esa inscripción ya tiene calificación registrada."
                )

            cierre = ActaCierre.objects.filter(
                grupo=inscripcion.grupo,
            ).first()
            self._acta_cierre = cierre
            if cierre and not (self.user and self.user.is_superuser):
                raise forms.ValidationError(
                    "El acta de ese grupo ya está cerrada; no se pueden mover calificaciones."
                )

        return cleaned
