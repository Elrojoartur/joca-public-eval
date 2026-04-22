from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.ui.views_reportes import (
    _load_report_schedule_values,
    _schedule_is_due,
    ejecutar_envio_periodico_reportes,
)


class Command(BaseCommand):
    help = "Ejecuta el envio periodico de reportes configurados"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Forzar envio aunque no sea hora/frecuencia programada",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help=(
                "Simula la ejecucion: verifica si el envio es debido y muestra "
                "destinatarios/formato/reporte, pero NO envia correo ni actualiza "
                "reportes_envio_ultimo. Util para validar cron en VPS."
            ),
        )

    def handle(self, *args, **options):
        now_dt = timezone.localtime(timezone.now())
        ts = now_dt.strftime("%Y-%m-%d %H:%M:%S %Z")

        if options.get("dry_run"):
            values = _load_report_schedule_values()
            activo = values.get("reportes_envio_activo") == "1"
            is_due = _schedule_is_due(values, now_dt)
            self.stdout.write(
                f"[{ts}] [DRY-RUN] activo={activo} is_due={is_due} "
                f"frecuencia={values.get('reportes_envio_frecuencia')} "
                f"hora={values.get('reportes_envio_hora')} "
                f"reporte={values.get('reportes_envio_reporte')} "
                f"formato={values.get('reportes_envio_formato')} "
                f"destinatarios={values.get('reportes_envio_destinatarios')!r} "
                f"ultimo={values.get('reportes_envio_ultimo')!r}"
            )
            if is_due or options.get("force"):
                self.stdout.write(self.style.SUCCESS(
                    f"[{ts}] [DRY-RUN] El envio SE EJECUTARIA ahora."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"[{ts}] [DRY-RUN] El envio NO es debido en este momento."
                ))
            return

        result = ejecutar_envio_periodico_reportes(
            force=bool(options.get("force")))
        status = result.get("status")

        if status == "ok":
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{ts}] Envio OK | reporte={result.get('report')} "
                    f"formato={result.get('format')} archivo={result.get('filename')}"
                )
            )
            return

        if status == "error":
            raise CommandError(
                f"[{ts}] Envio fallido: {result.get('reason', 'unknown')}"
            )

        reason = result.get("reason", "unknown")
        self.stdout.write(self.style.WARNING(
            f"[{ts}] Envio omitido: {reason}"
        ))
