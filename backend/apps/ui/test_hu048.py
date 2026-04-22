from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, ParametroSistema


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ProgramarEnvioPeriodicoReportesHU048Tests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.rol_alumno = Rol.objects.create(
            nombre="Alumno",
            codigo="ALUMNO",
            activo=True,
        )

    def _user_with_role(self, username, role):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=role)
        return user

    def test_director_guarda_programacion_de_envio(self):
        director = self._user_with_role(
            "director_hu048_cfg", self.rol_director)
        self.client.force_login(director)

        response = self.client.post(
            "/panel/reportes/programacion/",
            {
                "operation": "save",
                "reportes_envio_activo": "on",
                "reportes_envio_frecuencia": "semanal",
                "reportes_envio_hora": "07:30",
                "reportes_envio_dia_semana": "2",
                "reportes_envio_dia_mes": "15",
                "reportes_envio_reporte": "comercial",
                "reportes_envio_formato": "csv",
                "reportes_envio_destinatarios": "a@test.local,b@test.local",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ParametroSistema.objects.filter(
                categoria=ParametroSistema.CATEGORIA_REPORTES,
                clave="reportes_envio_frecuencia",
                valor="semanal",
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="REPORTES::PROGRAMACION_UPDATE",
                entidad="ParametroSistema",
                resultado="ok",
            ).exists()
        )

    def test_director_envia_ahora_reporte_programado(self):
        director = self._user_with_role(
            "director_hu048_send", self.rol_director)
        self.client.force_login(director)

        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_activo",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "1",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_reporte",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "ejecutivo",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_formato",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "pdf",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_destinatarios",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "dir@test.local",
                "activo": True,
            },
        )

        response = self.client.post(
            "/panel/reportes/programacion/",
            {"operation": "send_now"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["dir@test.local"])
        self.assertEqual(len(mail.outbox[0].attachments), 1)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="REPORTES::ENVIO_PERIODICO",
                entidad="ReporteProgramado",
                resultado="ok",
            ).exists()
        )

    def test_comando_envio_periodico_force(self):
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_activo",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "1",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_reporte",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "academico",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_formato",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "csv",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_destinatarios",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "ops@test.local",
                "activo": True,
            },
        )

        buffer = StringIO()
        call_command("enviar_reportes_programados", "--force", stdout=buffer)

        self.assertIn("Envio OK", buffer.getvalue())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ops@test.local"])

    def test_alumno_no_puede_acceder_programacion_reportes(self):
        alumno = self._user_with_role("alumno_hu048", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.get("/panel/reportes/programacion/")

        self.assertEqual(response.status_code, 403)

    def test_comando_dry_run_no_envia_correo(self):
        """--dry-run muestra estado de la programación sin enviar correo ni actualizar ultimo."""
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_activo",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "1",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_frecuencia",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "diario",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_reporte",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "ejecutivo",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_formato",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "csv",
                "activo": True,
            },
        )
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_destinatarios",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "dryrun@test.local",
                "activo": True,
            },
        )

        buffer = StringIO()
        call_command("enviar_reportes_programados", "--dry-run", stdout=buffer)
        output = buffer.getvalue()

        # No debe enviarse ningún correo
        self.assertEqual(len(mail.outbox), 0)
        # Debe reportar estado en stdout
        self.assertIn("DRY-RUN", output)
        self.assertIn("ejecutivo", output)
        self.assertIn("csv", output)
        self.assertIn("dryrun@test.local", output)
        # No debe actualizar reportes_envio_ultimo
        self.assertFalse(
            ParametroSistema.objects.filter(
                clave="reportes_envio_ultimo"
            ).exclude(valor="").exists()
        )

    def test_comando_sin_force_omite_si_no_activo(self):
        """Sin --force, el comando reporta 'omitido' cuando el envio está desactivado."""
        ParametroSistema.objects.update_or_create(
            clave="reportes_envio_activo",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": "0",
                "activo": True,
            },
        )

        buffer = StringIO()
        call_command("enviar_reportes_programados", stdout=buffer)
        output = buffer.getvalue()

        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("omitido", output.lower())
