# Mecanismos de seguridad del sistema JOCA

Fecha de verificacion: 2026-03-17

## Resumen ejecutivo

- Total de mecanismos identificados y verificados: 10
- Minimo solicitado: 6
- Cumplimiento: SI

## Matriz de mecanismos verificados

| # | Mecanismo | Descripcion | Evidencia tecnica |
|---|---|---|---|
| 1 | Control de acceso por roles en panel privado | Se restringen rutas de `/panel/*` por rol y se responde 403 cuando no cumple permisos. | `backend/apps/authn/middleware.py` (clase `PanelAccessMiddleware`) |
| 2 | Expiracion de sesion por inactividad | Cierra sesion automaticamente si excede tiempo inactivo configurable y fuerza reingreso. | `backend/apps/authn/middleware.py` (clase `IdleTimeoutMiddleware`), `backend/apps/ui/tests.py` |
| 3 | Bloqueo por intentos fallidos (lockout) | El login bloquea por usuario tras reintentos fallidos dentro de ventana de tiempo. | `backend/apps/ui/views_auth.py` (`_mark_failed_attempt`, `_is_locked_out`), `backend/apps/authn/tests.py` |
| 4 | CAPTCHA interno de verificacion humana | Antes de autenticar, exige resolver verificacion de suma y regenera desafio por intento. | `backend/apps/ui/views_auth.py` (`_set_verification`, validacion de `verificacion`), `backend/apps/ui/templates/registration/login.html` |
| 5 | Google reCAPTCHA v2/v3 configurable | Integracion opcional con Google (modo v2/v3, score threshold) con validacion server-side. | `backend/joca/settings.py` (variables `RECAPTCHA_*`), `backend/apps/ui/views_auth.py` (`_verify_recaptcha`) |
| 6 | Proteccion CSRF en formularios | Middleware CSRF activo y formularios POST con token CSRF en templates. | `backend/joca/settings.py` (`CsrfViewMiddleware`), multiples templates `backend/apps/ui/templates/...` con `{% csrf_token %}` |
| 7 | Cabeceras anti-cache para rutas sensibles | Evita reutilizar paginas privadas tras logout/retroceso usando `Cache-Control`, `Pragma`, `Expires`. | `backend/apps/authn/middleware.py` (clase `SecurityNoCacheMiddleware`) |
| 8 | Cierre de sesion con limpieza de tokens | Al salir, elimina `access_token` y `refresh_token` de sesion y hace flush. | `backend/apps/authn/views.py` (`salir`), `backend/apps/authn/tests.py` (`LogoutRevokeTests`) |
| 9 | Politica de contrasenas robusta | Validadores de longitud minima, comunes, numericas y similitud de atributos de usuario. | `backend/joca/settings.py` (`AUTH_PASSWORD_VALIDATORS`) |
| 10 | Hashing robusto de contrasenas | Configura hashers seguros (PBKDF2, PBKDF2SHA1, Scrypt). | `backend/joca/settings.py` (`PASSWORD_HASHERS`) |

## Parametros de seguridad configurables

La politica de seguridad puede variarse sin cambiar codigo, mediante parametros del sistema:

- `security_max_attempts`
- `security_attempt_window_seconds`
- `security_lockout_seconds`
- `security_idle_timeout_seconds`
- `security_password_min_length`
- `security_captcha_enabled`

Evidencia: `backend/apps/governance/services/security_policy.py`.

## Conclusion

El sistema supera el minimo solicitado y contiene al menos 10 mecanismos de seguridad verificables en codigo y pruebas automatizadas.
