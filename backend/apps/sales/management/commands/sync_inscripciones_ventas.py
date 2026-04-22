from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.school.models import Inscripcion
from apps.sales.services.enrollment_sales import ensure_inscripcion_sale


class Command(BaseCommand):
    help = "Sincroniza ventas POS para inscripciones existentes (precio base 1000, sin factura por defecto)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--solo-activas",
            action="store_true",
            help="Procesa solo inscripciones activas.",
        )

    def handle(self, *args, **options):
        qs = Inscripcion.objects.select_related(
            "grupo", "alumno").all().order_by("id")
        if options.get("solo_activas"):
            qs = qs.filter(estado=Inscripcion.ESTADO_ACTIVA)

        total = 0
        for insc in qs.iterator():
            ensure_inscripcion_sale(insc, requiere_factura=False)
            total += 1

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización completada. Inscripciones procesadas: {total}"))
