# JOCA — Sistema Web de Gestión Escolar y Ventas

Sistema de información web desarrollado para el **Centro de Capacitación en Electrónica y Nuevas Tecnologías (CCENT)**, que integra la gestión de procesos escolares y comerciales en una sola plataforma.

---

## Índice

- [Problema que resuelve](#problema-que-resuelve)
- [Stack tecnológico](#stack-tecnológico)
- [Módulos principales](#módulos-principales)
- [Arquitectura general](#arquitectura-general)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Ejecución local](#ejecución-local)
- [Tests](#tests)
- [Documentación](#documentación)


---

## Problema que resuelve

CCENT operaba sus procesos de inscripción, control escolar, ventas y atención al cliente de forma manual y con herramientas desarticuladas. El sistema JOCA centraliza y digitaliza:

- Registro y gestión de alumnos, grupos e inscripciones académicas
- Control de calificaciones, boletas y actas de cierre de periodo
- Punto de venta (POS), estado de cuenta, corte de caja y catálogo comercial
- Portal público con información de cursos, horarios, avisos, FAQs y formulario de contacto
- Panel de gobierno: administración de usuarios, roles, parámetros del sistema y bitácora de auditoría

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Lenguaje backend | Python 3.12 |
| Framework web | Django 5.x |
| Base de datos | PostgreSQL 16 |
| API REST | Django REST Framework (DRF) |
| Frontend | HTML5 + Bootstrap 5 + CSS personalizado |
| Autenticación | Django Auth + sesiones con tokens + bloqueo por intentos |
| Contenedores | Docker + Docker Compose |
| Email | SMTP configurable (consola en dev, Gmail/SMTP externo en producción) |
| Captcha | Google reCAPTCHA v2 (configurable, keys de prueba para dev) |

---

## Módulos principales

| Módulo | Ruta | Descripción |
|---|---|---|
| `accounts` | `backend/apps/accounts/` | Modelo de usuario, roles y permisos personalizados |
| `authn` | `backend/apps/authn/` | Autenticación, sesiones seguras, bloqueo por intentos fallidos |
| `school` | `backend/apps/school/` | Alumnos, docentes, grupos, inscripciones, calificaciones y actas de cierre |
| `sales` | `backend/apps/sales/` | POS, ventas, cuentas, corte de caja, inventario y proveedores |
| `public_portal` | `backend/apps/public_portal/` | Portal público: cursos, avisos, FAQs, contacto con captcha |
| `governance` | `backend/apps/governance/` | Parámetros del sistema, políticas de seguridad, auditoría y respaldos |
| `reports` | `backend/apps/reports/` | Reportes ejecutivos, académicos y comerciales |
| `ui` | `backend/apps/ui/` | Templates globales, validación de entradas, context processors, assets |

---

## Arquitectura general

```
┌──────────────────────────────────────────────────────────────────┐
│                        Cliente (Browser)                         │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP / HTTPS
┌──────────────────────────────▼───────────────────────────────────┐
│                  Django Application  (backend/)                  │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  authn   │  │  school  │  │  sales   │  │   governance     │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
│  ┌──────────────────────────────────────────────────────────── ┐ │
│  │         ui / templates / static / accounts / reports        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     REST API  /api/v1/                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                        PostgreSQL 16                             │
└──────────────────────────────────────────────────────────────────┘
```

El patrón de diseño por módulo sigue una estructura de **dominio + servicios + API**:

```
apps/<modulo>/
├── models.py          # Modelos de datos
├── views.py           # Vistas (o views_*.py por subdominio)
├── forms.py           # Formularios con validación
├── admin.py           # Integración Django Admin
├── domain/            # Lógica de negocio desacoplada
│   └── <subdominio>/
│       └── __init__.py
├── services/          # Servicios auxiliares reutilizables
├── api/v1/            # Endpoints REST
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── migrations/        # Historial de cambios del esquema
└── test_hu*.py        # Tests por Historia de Usuario
```

---

## Estructura del repositorio

```
joca-public-eval/
├── README.md                        # Este archivo
├── .env.example                     # Plantilla de variables de entorno
├── .gitignore
├── requirements.txt                 # Dependencias Python (mirror de backend/)
├── Makefile                         # Comandos de desarrollo frecuentes
├── docker-compose.yml               # Infraestructura principal
├── docker-compose.dev.yml           # Perfil de desarrollo
├── docker-compose.prod.yml          # Perfil de producción
├── scripts/
│   └── dev_local_pg.sh              # Script de inicio local con PostgreSQL
├── docs_public/                     # Documentación técnica pública
│   ├── reglas_negocio.md
│   ├── mapa_navegabilidad_49hu.md
│   ├── mecanismos_seguridad_sistema.md
│   ├── matriz_acceso_panel.md
│   ├── trazabilidad_hu_iteracion_01.md
│   ├── db/
│   │   ├── 00_crear_db.sql          # Script de creación de base de datos
│   │   └── ddl_3fn_pgadmin.sql      # Esquema completo en 3FN
│   └── rules/
│       └── business_rules.yml       # Reglas de negocio en formato YAML
├── LICENSE
└── backend/
    ├── manage.py                    # Punto de entrada Django
    ├── requirements.txt             # Dependencias Python
    ├── Dockerfile
    ├── logs/
    │   └── .gitkeep
    ├── templates/                   # Templates globales (errores, registro)
    │   ├── admin/
    │   ├── errors/
    │   ├── public_portal/
    │   └── registration/
    ├── joca/                        # Configuración del proyecto Django
    │   ├── settings.py
    │   ├── urls.py
    │   ├── views.py
    │   ├── wsgi.py
    │   ├── asgi.py
    │   └── api/v1/
    └── apps/
        ├── accounts/
        ├── authn/
        ├── governance/
        ├── public_portal/
        ├── sales/
        ├── school/
        ├── reports/
        └── ui/
            ├── static/              # CSS, imágenes, assets
            └── templates/          # Templates del panel y portal
```

---

## Ejecución local

### Requisitos previos

- Python 3.12+
- PostgreSQL 16 (o Docker Desktop / Docker Engine)

### Con Docker Compose (recomendado)

```bash
# 1. Clonar el repositorio
git clone https://github.com/<usuario>/joca-public-eval.git
cd joca-public-eval

# 2. Crear el archivo de entorno a partir de la plantilla
cp .env.example .env
# Editar .env: definir POSTGRES_PASSWORD, DJANGO_SECRET_KEY y EMAIL_HOST_USER

# 3. Levantar servicios (base de datos + aplicación)
docker compose up --build

# 4. En otra terminal: aplicar migraciones
docker compose exec web python manage.py migrate

# 5. Crear superusuario inicial
docker compose exec web python manage.py createsuperuser

# 6. Acceder
#    Portal público:   http://localhost:8000/
#    Panel de acceso:  http://localhost:8000/acceso/
#    Admin Django:     http://localhost:8000/admin/
```

### Sin Docker (entorno virtual)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Asegurarse de tener PostgreSQL corriendo y .env configurado
python manage.py migrate
python manage.py runserver
```

### Datos de prueba (opcional)

```bash
# Seed con datos demo del CCENT
docker compose exec web python manage.py seed_ccent
docker compose exec web python manage.py seed_school
```

---

## Tests

El proyecto incluye **39 archivos de prueba** que cubren las 49 Historias de Usuario del MVP, organizados por módulo y numerados (`test_hu022.py`, `test_hu036.py`, etc.).

```bash
# Ejecutar todos los tests
cd backend
python manage.py test apps

# Ejecutar tests de un módulo específico
python manage.py test apps.school
python manage.py test apps.authn
```

| Módulo | Archivos de test |
|---|---|
| `accounts` | `test_hu021.py`, `tests.py` |
| `authn` | `test_session_middleware.py`, `tests.py` |
| `governance` | `test_hu036..042.py`, `tests.py` |
| `school` | `test_hu022..029.py`, `tests.py` |
| `ui` | `test_hu043..049.py`, `test_cross_modulo_trazabilidad.py`, `tests.py` |
| `public_portal` | `test_hu005.py`, `tests.py` |

---

## Documentación

| Documento | Descripción |
|---|---|
| [`docs_public/reglas_negocio.md`](docs_public/reglas_negocio.md) | Reglas de negocio normalizadas (BR-###) |
| [`docs_public/mapa_navegabilidad_49hu.md`](docs_public/mapa_navegabilidad_49hu.md) | Rutas del sistema y permisos por rol |
| [`docs_public/mecanismos_seguridad_sistema.md`](docs_public/mecanismos_seguridad_sistema.md) | Mecanismos de seguridad implementados |
| [`docs_public/matriz_acceso_panel.md`](docs_public/matriz_acceso_panel.md) | Matriz de acceso por módulo y rol |
| [`docs_public/trazabilidad_hu_iteracion_01.md`](docs_public/trazabilidad_hu_iteracion_01.md) | Trazabilidad de las 49 Historias de Usuario |
| [`docs_public/db/ddl_3fn_pgadmin.sql`](docs_public/db/ddl_3fn_pgadmin.sql) | Esquema de base de datos en 3FN |
| [`docs_public/rules/business_rules.yml`](docs_public/rules/business_rules.yml) | Reglas de negocio en YAML |



---

*Proyecto desarrollado como trabajo terminal. CCENT — 2026.*
