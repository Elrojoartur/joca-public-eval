.PHONY: help mailhog-up mailhog-down test-email setup-email-dev setup-email-vps

help:
	@echo "JOCA - Sistema de Gestión Escolar"
	@echo "=================================="
	@echo ""
	@echo "Email Testing (HU-005):"
	@echo "  make mailhog-up          - Levantar MailHog en Docker"
	@echo "  make mailhog-down        - Bajar MailHog"
	@echo "  make test-email	         - Enviar email de prueba"
	@echo "  make setup-email-dev     - Configurar para desarrollo (MailHog)"
	@echo "  make setup-email-vps     - Script para configuración VPS"
	@echo ""
	@echo "Testing:"
	@echo "  make test                - Correr todas las pruebas"
	@echo "  make test-hu005          - Pruebas HU-005 (contacto)"

# MailHog
mailhog-up:
	@echo "🚀 Levantando MailHog en Docker..."
	docker-compose -f docker-mailhog.yml up -d
	@echo "✅ MailHog disponible en: http://localhost:8025"
	@echo "📧 SMTP: localhost:1025"

mailhog-down:
	@echo "🛑 Bajando MailHog..."
	docker-compose -f docker-mailhog.yml down

# Email Testing
test-email:
	@echo "🧪 Enviando email de prueba..."
	cd backend && python manage.py shell << 'EOF'
from django.core.mail import send_mail
from django.conf import settings

send_mail(
    subject='[JOCA] Prueba de Email',
    message='Este es un email de prueba de la configuración SMTP.\n\nSi ves este mensaje, ¡todo funciona!',
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=['test@joca.local'],
    fail_silently=False
)
print("✅ Email de prueba enviado")
print(f"   De: {settings.DEFAULT_FROM_EMAIL}")
print(f"   Para: test@joca.local")
print(f"   Backend: {settings.EMAIL_BACKEND}")
EOF

setup-email-dev:
	@echo "⚙️  Configurando para desarrollo (MailHog)..."
	@echo "EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend" >> .env
	@echo "EMAIL_HOST=localhost" >> .env
	@echo "EMAIL_PORT=1025" >> .env
	@echo "EMAIL_USE_TLS=False" >> .env
	@echo "EMAIL_USE_SSL=False" >> .env
	@echo "✅ Configuración para MailHog agregada a .env"
	@echo ""
	@echo "Próximos pasos:"
	@echo "  1. make mailhog-up"
	@echo "  2. python backend/manage.py runserver"
	@echo "  3. Ir a http://localhost:8000/portal/contacto/"
	@echo "  4. Ver emails en http://localhost:8025"

setup-email-vps:
	@echo "📋 Script de configuración para VPS disponible en:"
	@echo "   ./setup_email_vps.sh"
	@echo ""
	@echo "Uso:"
	@echo "   bash setup_email_vps.sh"
	@echo ""
	@echo "Documentación en:"
	@echo "   docs/configuracion_email_hu005.md"

# Testing
test:
	cd backend && python manage.py test

test-hu005:
	@echo "🧪 Corriendo pruebas de caja negra HU-005..."
	cd backend && python manage.py test apps.public_portal.test_hu005 -v 2

.DEFAULT_GOAL := help
