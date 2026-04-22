# Validaciones de entradas por modulo

## Objetivo
Estandarizar la captura de datos en todos los cuadros de texto del sistema:
- Mostrar leyenda de captura dentro del campo (placeholder).
- Validar formato al escribir, al perder foco y al enviar.
- Mostrar mensaje claro cuando el valor no cumple la estructura.

## Cobertura global
La validacion cliente se centraliza en:
- `backend/apps/ui/templates/ui/base.html` (IIFE `applyGlobalInputValidation`).

Aplica a:
- `input[type=text]`
- `input[type=email]`
- `input[type=search]`
- `input[type=tel]`
- `textarea`

## Reglas especificas
1. Matricula (`matricula`, `matrícula`)
- Formato: `^[A-Z0-9]{3,32}$`
- Leyenda: Solo letras mayusculas y numeros.

2. Nombre y apellidos (`nombre`, `nombres`, `apellido_paterno`, `apellido_materno`)
- Formato: solo letras y espacios.
- Leyenda: Solo letras y espacios.

3. Usuario (`usuario`, `username`)
- Formato: `^[A-Za-z0-9._-]{4,32}$`
- Leyenda: 4-32 caracteres (letras, numeros, punto, guion, guion bajo).

4. Correo (`correo`, `email`)
- Formato: correo valido.
- Leyenda: ejemplo `usuario@dominio.com`.

5. Telefono (`telefono`, `teléfono`, `celular`, `movil`)
- Formato: `^[0-9+()\-\s]{7,20}$`
- Leyenda: numeros y simbolos `+ ( ) -`.

6. Codigo postal (`cp`, `codigo_postal`)
- Formato: `^[0-9]{5}$`
- Leyenda: 5 digitos.

7. Periodo (`periodo`, `periodo_ref`)
- Formato: `YYYY-MM`.
- Leyenda: ejemplo `2026-03`.

8. Folios y claves (`folio`, `referencia`, `codigo`, `clave`, `slug`)
- Formato: `^[A-Za-z0-9_-]{1,40}$`
- Leyenda: letras, numeros, guion y guion bajo.

9. RFC (`rfc`)
- Formato: `^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$`
- Leyenda: `AAA010101AAA`.

10. CURP (`curp`)
- Formato: CURP de 18 caracteres.
- Leyenda: CURP valida de 18 caracteres.

11. Direccion y texto descriptivo (`direccion`, `calle`, `colonia`, `municipio`, `estado`, `ciudad`, `asunto`, `mensaje`, `descripcion`, `observaciones`, `nota`, `comentario`)
- Formato: letras, numeros y signos basicos.
- Leyenda: texto valido con signos basicos.

## Fallback para cualquier otro cuadro de texto
Si un campo no coincide con reglas especificas:
- Inputs texto: se aplica regla alfanumerica general con signos basicos permitidos.
- Textareas: misma regla general permitiendo saltos de linea.

Esto asegura que todos los cuadros de texto tengan leyenda y validacion minima consistente.

## Validacion de servidor (backend)
Se mantiene validacion backend en:
- `backend/apps/ui/input_validation.py`
- Formularios de `apps/ui/forms.py` y `apps/public_portal/forms.py`

### Tercera pasada (POST directo sin forms)
Tambien se endurecio validacion en vistas que reciben `request.POST` directamente:
- `backend/apps/ui/views_gobierno.py`
- `backend/apps/ui/views_reportes.py`
- `backend/apps/ui/views_school.py`
- `backend/apps/sales/views.py`

Se incorporo validador comun:
- `validate_text_general(...)` en `backend/apps/ui/input_validation.py`

Controles agregados en backend para estos flujos:
- Catalogos maestros (curso, aula, concepto)
- Parametros SMTP y pasarela
- Notas de respaldos
- Favoritos de tablero y operacion de programacion de reportes
- Cierre de acta (periodo/motivo)
- Compras, proveedores, datos fiscales y notas de corte de caja

Nota:
- La validacion de cliente mejora UX y evita errores de captura.
- La validacion backend sigue siendo la fuente final de seguridad y consistencia.
