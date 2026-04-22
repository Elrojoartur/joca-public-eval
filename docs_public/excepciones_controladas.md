# Excepciones Controladas (JOCA)

Este documento resume las excepciones que el sistema contempla de forma controlada y su comportamiento esperado para usuario final y auditoria.

## 1) IntegrityError
- Donde aparece: escolar y ventas.
- Causa tipica: duplicidad de datos o violacion de restriccion unica.
- Respuesta del sistema: mensaje en pantalla (`messages.error`) y redireccion segura.
- Referencias:
  - `backend/apps/ui/views_school.py:431`
  - `backend/apps/sales/views.py:477`
  - `backend/apps/sales/views.py:1000`

## 2) ValidationError
- Donde aparece: validadores de dominio, forms y serializers.
- Causa tipica: formato invalido de CURP/RFC, reglas de negocio en formularios.
- Respuesta del sistema: se bloquea guardado y se muestran errores por campo.
- Referencias:
  - `backend/apps/school/validators.py:42`
  - `backend/apps/ui/forms.py:63`
  - `backend/apps/school/api/v1/serializers.py:36`

## 3) Http404
- Donde aparece: portal publico.
- Causa tipica: recurso solicitado inexistente.
- Respuesta del sistema: 404 controlado sin traza interna.
- Referencia:
  - `backend/apps/public_portal/views.py:285`

## 4) ValueError
- Donde aparece: parseo y conversion de datos.
- Causa tipica: valores no convertibles o formato de entrada incorrecto.
- Respuesta del sistema: captura y transformacion a mensaje funcional.
- Referencias:
  - `backend/apps/public_portal/views.py:77`
  - `backend/apps/sales/views.py:472`
  - `backend/apps/school/validators.py:52`

## 5) Exception (fallback)
- Donde aparece: reportes, alumno, gobierno y componentes auxiliares.
- Causa tipica: dependencia externa o falla no prevista.
- Respuesta del sistema: fallback seguro, sin romper la UI, con registro para diagnostico.
- Referencias:
  - `backend/apps/ui/views_reportes.py:337`
  - `backend/apps/ui/views_alumno.py:145`
  - `backend/apps/ui/views_gobierno.py:376`

## Criterio Operativo
- Toda excepcion esperada debe:
  - mostrar mensaje de usuario claro,
  - evitar 500 en flujo normal,
  - registrar evidencia en auditoria/log cuando aplique.
