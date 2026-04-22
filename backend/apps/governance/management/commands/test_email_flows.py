from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Verifica los flujos de correo de HU-005 (contacto) y HU-014 (recuperación de contraseña) "
        "enviando correos de prueba reales al destinatario configurado. "
        "Úsalo en el VPS para confirmar que SMTP funciona end-to-end."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--destinatario",
            required=True,
            help="Dirección de correo donde se recibirán los mensajes de prueba.",
        )
        parser.add_argument(
            "--flujo",
            choices=["contacto", "reset", "ambos"],
            default="ambos",
            help="Flujo a probar: 'contacto' (HU-005), 'reset' (HU-014) o 'ambos' (default).",
        )

    def handle(self, *args, **options):
        destinatario = options["destinatario"].strip()
        flujo = options["flujo"]
        now_ts = timezone.localtime(
            timezone.now()).strftime("%Y-%m-%d %H:%M:%S %Z")
        site_name = getattr(settings, "SITE_NAME", "CCENT")
        remitente = getattr(settings, "DEFAULT_FROM_EMAIL",
                            "noreply@joca.local")

        errores = []

        if flujo in ("contacto", "ambos"):
            self.stdout.write(
                f"[{now_ts}] [HU-005] Enviando correo de prueba del flujo de contacto…")
            try:
                # Simula la notificación interna que genera enviar_correo_contacto()
                send_mail(
                    subject=f"[{site_name}] [PRUEBA HU-005] Mensaje de contacto",
                    message=(
                        f"Este es un correo de prueba del flujo HU-005 (Contacto).\n\n"
                        f"Nombre: Visitante de Prueba\n"
                        f"Correo: {destinatario}\n"
                        f"Teléfono: No proporcionado\n"
                        f"Asunto: Verificación de flujo de contacto\n\n"
                        f"Mensaje:\nEste correo valida que el envío de notificación interna funciona en {site_name}.\n\n"
                        f"Generado: {now_ts}"
                    ),
                    from_email=remitente,
                    recipient_list=[destinatario],
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"[{now_ts}] [HU-005] Notificación interna enviada a {destinatario}"
                ))

                # Simula el acuse de recibo que va al remitente del formulario
                send_mail(
                    subject=f"[{site_name}] [PRUEBA HU-005] Acuse de recibo",
                    message=(
                        f"Hola Visitante de Prueba,\n\n"
                        f"Recibimos tu mensaje en {site_name}. "
                        f"Nos pondremos en contacto contigo a la brevedad.\n\n"
                        f"(Este correo es una prueba del flujo de contacto generada en {now_ts}.)"
                    ),
                    from_email=remitente,
                    recipient_list=[destinatario],
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"[{now_ts}] [HU-005] Acuse de recibo enviado a {destinatario}"
                ))
            except Exception as exc:
                msg = f"[HU-005] Error al enviar correo de contacto: {exc}"
                self.stderr.write(self.style.ERROR(f"[{now_ts}] {msg}"))
                errores.append(msg)

        if flujo in ("reset", "ambos"):
            self.stdout.write(
                f"[{now_ts}] [HU-014] Enviando correo de prueba del flujo de recuperación de contraseña…")
            try:
                send_mail(
                    subject=f"Recuperación de acceso — {site_name} [PRUEBA HU-014]",
                    message=(
                        f"Hola usuario_de_prueba,\n\n"
                        f"Recibimos una solicitud para restablecer tu contraseña en {site_name}.\n\n"
                        f"Tu nombre de usuario es: usuario_de_prueba\n\n"
                        f"Para crear una nueva contraseña, abre este enlace (este es un enlace simulado):\n"
                        f"https://ccentnikolatesla.online/acceso/recuperar/TEST_UID64/TEST_TOKEN/\n\n"
                        f"Si no solicitaste este cambio, puedes ignorar este correo con seguridad.\n\n"
                        f"Equipo {site_name}\n\n"
                        f"(Correo de prueba del flujo HU-014 generado en {now_ts}.)"
                    ),
                    from_email=remitente,
                    recipient_list=[destinatario],
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"[{now_ts}] [HU-014] Correo de recuperación de contraseña enviado a {destinatario}"
                ))
            except Exception as exc:
                msg = f"[HU-014] Error al enviar correo de recuperación: {exc}"
                self.stderr.write(self.style.ERROR(f"[{now_ts}] {msg}"))
                errores.append(msg)

        if errores:
            raise CommandError(
                f"Hubo {len(errores)} error(es) al enviar correos. "
                "Verifica la configuración SMTP en /panel/gobierno/parametros/?modo=smtp"
            )

        self.stdout.write(self.style.SUCCESS(
            f"[{now_ts}] Prueba de flujos de correo completada. "
            f"Verifica la bandeja de {destinatario!r}."
        ))
