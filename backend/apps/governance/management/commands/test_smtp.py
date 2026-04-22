from __future__ import annotations

import smtplib

from django.core.management.base import BaseCommand

from apps.governance.models import ParametroSistema


class Command(BaseCommand):
    help = (
        "Prueba la conexión SMTP configurada en ParametroSistema. "
        "Úsalo en el VPS para validar la integración SMTP antes de habilitarla."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            help="Sobreescribe smtp_host de ParametroSistema (solo para esta prueba).",
        )
        parser.add_argument(
            "--port",
            type=int,
            help="Sobreescribe smtp_port de ParametroSistema (solo para esta prueba).",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=10,
            help="Timeout de conexión en segundos (default: 10).",
        )

    def handle(self, *args, **options):
        values = {
            row.clave: row.valor
            for row in ParametroSistema.objects.filter(clave__startswith="smtp_")
        }

        host = options.get("host") or values.get("smtp_host", "")
        port_raw = options.get("port") or values.get("smtp_port", "587")
        timeout = options["timeout"]

        if not host:
            self.stderr.write(
                self.style.ERROR(
                    "smtp_host no configurado. "
                    "Configúralo en /panel/gobierno/parametros/?modo=smtp o usa --host."
                )
            )
            return

        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            self.stderr.write(self.style.ERROR(
                f"smtp_port inválido: {port_raw!r}"))
            return

        self.stdout.write(
            f"Intentando conexión SMTP a {host}:{port} (timeout={timeout}s) …")
        try:
            with smtplib.SMTP(host, port, timeout=timeout) as conn:
                code, msg = conn.noop()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Conexión SMTP exitosa: {host}:{port}  —  respuesta NOOP: {code} {msg.decode('utf-8', errors='replace')}"
                )
            )
            self.stdout.write(
                "Puedes habilitar SMTP desde /panel/gobierno/parametros/?modo=smtp "
                "ejecutando la operación 'Probar' y luego 'Guardar habilitado'."
            )
        except smtplib.SMTPConnectError as exc:
            self.stderr.write(self.style.ERROR(f"SMTPConnectError: {exc}"))
        except smtplib.SMTPServerDisconnected as exc:
            self.stderr.write(self.style.ERROR(
                f"SMTPServerDisconnected: {exc}"))
        except ConnectionRefusedError:
            self.stderr.write(
                self.style.ERROR(
                    f"Conexión rechazada: {host}:{port}. Verifica host, puerto y firewall.")
            )
        except TimeoutError:
            self.stderr.write(
                self.style.ERROR(
                    f"Timeout alcanzado al conectar con {host}:{port}.")
            )
        except OSError as exc:
            self.stderr.write(self.style.ERROR(f"Error de red: {exc}"))
