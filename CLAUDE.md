# CLAUDE.md — django-disposable-email

> Documento de arquitectura y convenciones para Claude Code. El README.md (en
> inglés) es la documentación pública del paquete en PyPI; este fichero es la
> guía interna: por qué está hecho así, cómo está organizado y cómo se trabaja
> en él. No se incluye en el sdist ni en el wheel.

---

## 1. Qué es y por qué existe

Paquete Django que bloquea las direcciones de email desechables o temporales
(mailinator, 10minutemail, guerrillamail…) al registrarse, con integración
completa con django-allauth, incluido el alta con proveedores sociales.

**Decisión de Román (2026-10-09):** el bloqueo de emails desechables es una
funcionalidad GLOBAL de todos los proyectos de la casa, activable o
desactivable por configuración, ya sea por entorno (p. ej. Attentiometer) o
por un flag en base de datos (p. ej. RootedArbiter, en su configuración de
servidor). La regla está en el CLAUDE.md global (`~/.claude/CLAUDE.md`,
sección «Emails desechables»).

**Antecedentes:** había cinco copias divergentes del mismo código en
`apps/accounts/` de cada proyecto:

| Proyecto | Estado de su copia |
|---|---|
| ReciBRO | la más completa en funciones y tests (lista de pip + GitHub, Celery, auditoría), pero los workers web solo leían la lista al importar el módulo |
| Taxiquo | ROTA: nunca cargaba la lista ni la lista negra en los workers web |
| Taska | mínima: solo la lista de pip, sin actualización ni modelos |
| EasyContract | copia de ReciBRO en el adaptador; la lista negra no se cargaba al arrancar |
| Attentiometer | la mejor en ejecución (refresco perezoso por TTL, rechazo de descargas cortas, latido del cron) pero sin lista de pip |

Fallos comunes a TODAS:
- el alta automática con Google, Apple o Microsoft se saltaba la comprobación;
- no se miraban subdominios;
- no había lista blanca;
- no se podía apagar.

Este paquete junta lo mejor de cada una y corrige esos fallos. Las copias
antiguas son deuda que migrar (ver §8), nunca un patrón que copiar.

---

## 2. Decisiones de diseño (no reabrir sin justificación)

| Decisión | Elección | Por qué |
|---|---|---|
| Dónde vive | Paquete propio en PyPI, repo hermano de `django-encrypted-field` | Un arreglo llega a todos los proyectos subiendo la versión; las copias acaban divergiendo |
| Licencia | MIT | Igual que el resto de paquetes de la casa |
| Fuente de la lista | Unión de la lista del paquete PyPI `disposable-email-domains` (siempre) y una descarga diaria de su GitHub | Nunca arranca vacía (fallo de Taxiquo y Attentiometer) y no espera a una nueva versión de pip |
| Almacén de la descarga | La base de datos (modelo `Blocklist`, una fila) | Todos los procesos la ven sin Redis ni reinicios; ningún proyecto necesita una dependencia más |
| Refresco | Perezoso por proceso, con TTL (patrón Attentiometer) | Barato en cada alta; los cambios llegan a todos los workers sin reiniciar y sin consultas a BD en `ready()` |
| Descarga mala | Si falla o trae menos de `MIN_DOMAINS` (1000), se queda la anterior | Patrón Attentiometer: una descarga vacía no puede desproteger el registro |
| Interruptor | `ENABLED`: bool, `"db"` o ruta a una función | Petición expresa de Román: entorno o BD según el proyecto |
| Interruptor roto | Si la función falla o la tabla no existe, el bloqueo sigue ENCENDIDO | Un fallo de configuración nunca abre la puerta |
| Subdominios | `a.b.mailinator.com` se compara también con `b.mailinator.com` y `mailinator.com` | Ninguna copia lo hacía y era el bypass más fácil |
| Reglas a mano | `DomainRule` con acción `block` o `allow`; `allow` gana a todo | Lista negra propia y corrección de falsos positivos de la lista |
| Auditoría | `BlockedAttempt` con el email ENMASCARADO (`jo***@dominio`), dominio, IP, navegador, origen | RGPD: no guardar el email completo (EasyContract lo cifraba; enmascarar evita la dependencia) |
| IP | `REMOTE_ADDR` por defecto; `CLIENT_IP` para delegar en el helper del proyecto | Taxiquo confiaba en `X-Forwarded-For`, falsificable; cada proyecto sabe qué proxy tiene |
| Enganche con allauth | Formularios (mixin) + señal `pre_social_login`; NUNCA el `clean_email` del adaptador | Ver §5 |
| Cuentas que ya existen | No se bloquean: siguen entrando y recuperando la contraseña | Bloquear el reset dejaría fuera a usuarios antiguos o creados por el admin |
| Admin y `createsuperuser` | Nunca bloqueados | No pasan por los formularios de allauth (comportamiento ya testeado en ReciBRO) |
| Celery | Opcional (extra `[celery]`); sin Celery, comando por cron | Hay proyectos con Celery beat y proyectos con cron o RQ |
| Idiomas | Cadenas fuente en inglés; traducción al español incluida | Paquete público; la casa trabaja en español |

---

## 3. Estructura

```
django-disposable-email/
  pyproject.toml          # hatchling, layout src/, extras [allauth] y [celery], grupo dev
  README.md               # documentación pública (inglés), la que se ve en PyPI
  CHANGES.md              # Keep a Changelog + SemVer
  LICENSE                 # MIT
  CLAUDE.md               # este fichero (fuera del sdist y del wheel)
  src/disposable_email/
    __init__.py           # __version__ (sin imports de modelos: no romper la carga de apps)
    apps.py               # registra los system checks y conecta la señal social si allauth.socialaccount está instalado
    conf.py               # DEFAULTS y get(name): todos los ajustes bajo settings.DISPOSABLE_EMAIL
    models.py             # Config, DomainRule, Blocklist, BlockedAttempt + normalize_domain()
    checks.py             # NÚCLEO: is_enabled, listas con caché, check_email -> Verdict
    enforce.py            # mensaje, enmascarado, IP, record_blocked (auditoría + señal), enforce()
    validators.py         # validate_not_disposable para cualquier formulario o campo
    updater.py            # descarga, parseo, validación de tamaño, guardado en Blocklist
    tasks.py              # tarea Celery disposable_email.update_blocklist (solo si Celery está instalado)
    signals.py            # señal email_blocked
    system_checks.py      # disposable_email.W001 (formulario allauth sin mixin), E001
    admin.py              # admin de los cuatro modelos
    allauth/
      __init__.py         # explicación del enganche (sin código, para no importar allauth si no se usa)
      forms.py            # DisposableEmailFormMixin + SignupForm, AddEmailForm, ChangeEmailForm
      social_forms.py     # SocialSignupForm (separado: solo importa allauth.socialaccount si se usa)
      receivers.py        # block_disposable_social_signup (receptor de pre_social_login)
    management/commands/update_disposable_domains.py
    migrations/0001_initial.py
    locale/es/LC_MESSAGES/django.po|.mo
  tests/                  # NO es un paquete instalable (ver §9)
    settings.py, urls.py, conftest.py
    test_checks.py        # coincidencias, interruptor, actualización, auditoría, idioma
    test_allauth.py       # formularios reales por HTTP, reset de contraseña, señal social, system check
```

---

## 4. Cómo funciona por dentro

### 4.1 Orden de la decisión (`checks.check_email`)

1. Interruptor apagado → no bloquea (salvo `force=True`, que usa el comando `--check`).
2. Email sin `@` o dominio sin punto → `invalid`. `enforce()` NO lo bloquea: la
   validación de formato es cosa del `EmailField`.
3. Regla `allow` activa (dominio o dominio padre) → permitido.
4. Regla `block` activa → `blocked`.
5. Lista del paquete ∪ última descarga → `disposable`.
6. Si no → permitido.

Devuelve `Verdict(blocked, reason, domain)`. Es verdadero si bloquea.
`is_blocked_email(email) -> (bool, reason)` mantiene la API de las copias
antiguas para facilitar las migraciones.

### 4.2 Cachés por proceso (todas en `checks._state`, protegidas por un `RLock`)

| Qué | Se relee cada | Se invalida al momento |
|---|---|---|
| Interruptor (`"db"` o función) | `ENABLED_CACHE_SECONDS` (60) | `Config.save()` en ese proceso |
| Lista del paquete | nunca (no cambia en ejecución) | — |
| Descarga (`Blocklist`) | `REFRESH_SECONDS` (3600) | `update_blocklist()` en ese proceso |
| Reglas (`DomainRule`) | `RULES_REFRESH_SECONDS` (300) | `DomainRule.save()/delete()` en ese proceso |

Los demás procesos se enteran al caducar su TTL. Los errores de BD (tabla aún
sin migrar) no rompen nada: se usa lo que haya en caché o una lista vacía, y el
interruptor queda encendido. `reset_caches()` lo borra todo (tests y
guardados).

### 4.3 Normalización (`models.normalize_domain`)

Minúsculas, sin espacios, sin punto final, quitando lo que haya antes de una
`@` y en IDNA (punycode). Se aplica al guardar reglas, al parsear descargas y
al comprobar emails.

### 4.4 Actualización (`updater.update_blocklist`)

Descarga cada URL de `SOURCES` (timeout `TIMEOUT`) y parsea una línea por
dominio: se ignoran los comentarios `#` y las líneas sin punto o con espacios.
Si una fuente falla o trae menos de `MIN_DOMAINS`, lanza `UpdateError` y NO
toca la lista guardada. Si todo va bien, guarda la unión de las fuentes (no la
del paquete, que se suma al leer) en `Blocklist` pk=1 y devuelve
`UpdateResult(count, added, removed)`.

Hay dos formas de lanzarla:
- tarea Celery `disposable_email.update_blocklist`, con 3 reintentos cada 10 minutos;
- comando `update_disposable_domains`, con las opciones `--stats` y `--check email`.

### 4.5 Bloqueo (`enforce.enforce`)

Si el veredicto bloquea, `record_blocked()` hace tres cosas, y ninguna puede
romper un alta:
1. escribe un log WARNING sin el email;
2. crea un `BlockedAttempt` si `LOG_ATTEMPTS` está activo;
3. envía la señal `email_blocked`.

Después lanza `ValidationError(message(), code="disposable_email")`.
`MESSAGE` permite cambiar el texto. Si es `None`, se usa el texto del paquete,
traducido.

---

## 5. Integración con allauth (lo más delicado)

**Por qué NO el `clean_email` del adaptador** (donde lo ponían Taxiquo, Taska,
EasyContract y Attentiometer). En allauth 65, `DefaultAccountAdapter.clean_email`
se llama también desde:
- `ResetPasswordForm` y `RequestLoginCodeForm`: bloquear ahí deja sin reset a
  las cuentas antiguas con esas direcciones;
- `account.internal.emailkit.valid_email_or_none`, que usa el proveedor social
  para leer el email: ahí la `ValidationError` se traga en silencio y el email
  se convierte en «sin email», sin aviso ni auditoría.

**Lo que se hace en su lugar:**

1. **Formularios.** `DisposableEmailFormMixin` va PRIMERO en las bases de:
   - signup;
   - add_email;
   - change_email;
   - el signup social.

   Su `clean_email` llama a `super()` y después a `enforce()`.
   `disposable_email_source` etiqueta el origen en la auditoría. La petición
   sale de `form.request` o de `allauth.core.context.request`.
2. **Altas sociales.** El receptor `block_disposable_social_signup` está
   conectado a la señal `allauth.socialaccount.signals.pre_social_login` en
   `apps.ready()` (`dispatch_uid="disposable_email.social_signup"`).
   - allauth lanza esa señal después de `sociallogin.lookup()`, así que
     `sociallogin.is_existing` ya indica si la cuenta existe (también si se
     enlaza por email).
   - Solo actúa con cuentas NUEVAS. Mira `sociallogin.user.email` o, si viene
     vacío, `email_addresses`.
   - Si bloquea: deja un `messages.error` y lanza
     `ImmediateHttpResponse(redirect(SOCIAL_REDIRECT_URL))`, que
     `complete_login` captura.
   - Cubre `SOCIALACCOUNT_AUTO_SIGNUP=True`, que se salta los formularios.
   - No hace falta tocar el adaptador social del proyecto, así que no hay
     problemas de MRO con adaptadores que no llaman a `super()`.
3. **System check `disposable_email.W001`.**
   - Avisa por cada formulario de `ACCOUNT_FORMS` (signup, add_email,
     change_email) o de `SOCIALACCOUNT_FORMS` (signup) que no herede del mixin.
   - No configurarlo cuenta como no enganchado, porque el formulario por
     defecto de allauth no bloquea.
   - Se desactiva con `CHECK_ALLAUTH_WIRING=False`.
   - En la integración de un proyecto, `manage.py check` sin avisos es la
     prueba de que está bien montado.

Fuera de allauth (invitaciones, contactos, formularios propios):
`validate_not_disposable`, o `check_email` directamente.

---

## 6. Ajustes (`settings.DISPOSABLE_EMAIL`, todos opcionales)

| Clave | Por defecto | Uso |
|---|---|---|
| `ENABLED` | `True` | `True`/`False` (entorno), `"db"` (modelo `Config`, admin) o `"ruta.a.funcion"` que devuelve bool |
| `ENABLED_CACHE_SECONDS` | `60` | caché del interruptor `"db"` o función |
| `SOURCES` | lista de GitHub | URLs de texto plano, un dominio por línea |
| `INCLUDE_PACKAGE_LIST` | `True` | sumar la lista del paquete `disposable-email-domains` |
| `MIN_DOMAINS` | `1000` | por debajo, se rechaza la descarga |
| `TIMEOUT` | `30` | segundos por descarga |
| `REFRESH_SECONDS` | `3600` | relectura de la descarga en cada proceso |
| `RULES_REFRESH_SECONDS` | `300` | relectura de las reglas en cada proceso |
| `LOG_ATTEMPTS` | `True` | guardar `BlockedAttempt` |
| `CLIENT_IP` | `None` | `"ruta"` a `callable(request) -> IP`; por defecto `REMOTE_ADDR` |
| `MESSAGE` | `None` | texto propio (admite `gettext_lazy`); `None` = el del paquete traducido |
| `CHECK_SOCIAL_SIGNUP` | `True` | bloquear altas sociales nuevas |
| `SOCIAL_REDIRECT_URL` | `"account_login"` | adónde vuelve un alta social bloqueada |
| `CHECK_ALLAUTH_WIRING` | `True` | ejecutar `disposable_email.W001` |

Una clave desconocida en `conf.get()` lanza `KeyError`. Así una errata en el
código del paquete no pasa inadvertida (las claves de más en los settings del
proyecto se ignoran).

---

## 7. Integrarlo en un proyecto (checklist)

1. Dependencia `django-disposable-email[allauth,celery]>=1.0.0`, o sin
   `celery` si el proyecto no lo usa.
   - Se instala desde PyPI (publicado el 2026-10-09). No usar una fuente
     `path = "../django-disposable-email"` salvo para probar un cambio local
     del paquete, y quitarla antes de desplegar: Coolify y Docker no ven `../`.
2. Añadir `"disposable_email"` a `INSTALLED_APPS`.
3. `DISPOSABLE_EMAIL = {"ENABLED": ...}` según el proyecto:
   - entorno: `env.bool("DISPOSABLE_EMAIL_ENABLED", default=True)`, y la
     variable en `.env.example`;
   - admin: `"db"`;
   - configuración propia: ruta a una función. En RootedArbiter, una función
     que lea `SERVERConfiguration` (singleton `pk=1`, ver
     `core/tools.py:get_server_configuration`) y devuelva el campo nuevo.
4. `CLIENT_IP` apuntando al helper de IP del proyecto si hay proxy delante
   (ScenariumIT: `accounts.audit.get_client_ip`).
5. Formularios de allauth: el mixin primero en los propios, o los del paquete.
   Después, `manage.py check` sin `disposable_email.W001`.
6. Actualización diaria:
   - con Celery beat: entrada `{"task": "disposable_email.update_blocklist",
     "schedule": 86400.0}`, y `"disposable_email"` en `autodiscover_tasks` si
     el proyecto pasa una lista explícita (patrón de la casa);
   - sin Celery: cron con `manage.py update_disposable_domains` y su latido.

   En los dos casos, la vigilancia obligatoria del beat o del cron (CLAUDE.md global).
7. `migrate` y una primera descarga: `manage.py update_disposable_domains`.
8. Tests en el proyecto:
   - alta bloqueada con su auditoría;
   - subdominio;
   - interruptor apagado;
   - añadir email;
   - reset de contraseña de una cuenta antigua;
   - alta social por la señal;
   - system check limpio;
   - tarea programada.

   Referencia: `scenariumit/accounts/tests/test_disposable_email.py`.

Integrado (2026-10-09, sin commitear en cada proyecto hasta que Román lo revise):
**ScenariumIT**, **Taska**, **ReciBRO**, **EasyContract**, **Taxiquo** y
**Attentiometer** (interruptor por entorno), **RootedArbiter** (función que lee
`SERVERConfiguration.disposable_email_block_enabled`; cron por HTTP, sin Celery).
En RootedArbiter el bloqueo está DESACTIVADO por defecto y se activa a mano en
`/main/admin/status` (Román, 2026-10-10); es la única excepción al «encendido
por defecto» del paquete. Motivo: su sector cliente es muy sensible con la
privacidad y mucha gente usa direcciones desechables o de reenvío a propósito.
Pero el email PROFESIONAL de los registros a actividades se valida SIEMPRE,
con el interruptor apagado y aunque ya conste (`check_email(force=True)` +
`record_blocked` en `core/disposable_email_guard.py`).

---

## 8. Migrar un proyecto con copia antigua

1. Integrar el paquete (§7).
2. Data migration en el proyecto: cada `BlacklistedDomain` activo pasa a
   `disposable_email.DomainRule(domain, action="block", reason)`. La
   migración debe depender de `("disposable_email", "0001_initial")`.
   `BlockedEmailAttempt` se puede dejar como histórico o borrarse según la
   retención del proyecto. No copiar emails completos a `BlockedAttempt`.
3. Quitar la comprobación del `clean_email` del adaptador y la llamada de la
   vista de invitaciones, que pasa a usar `validate_not_disposable`
   (invitaciones de ReciBRO, `membership_invite_create`).
4. Quitar la tarea y la entrada de beat o cron antiguas, y el módulo
   `disposable_emails.py` / `disposable.py` con sus modelos: una migración que
   los borre, revisada a mano.
5. Retirar la dependencia `disposable-email-domains` si solo la usaba la copia
   (llega como dependencia del paquete).

Avisos por proyecto:
- **Taxiquo:** su bloqueo nunca funcionó, así que puede haber cuentas
  desechables ya creadas. No se tocan; como mucho, revisarlas a mano.
- **Taska:** comprueba en `clean_email` que el email coincide con una
  invitación pendiente cuando el registro está cerrado. Esa lógica es suya y
  se queda en su adaptador.
- **Attentiometer:** su cron tiene latido con `apps.ops.services.record_run`.
  Mantenerlo en la orden nueva.

---

## 9. Desarrollo, tests y publicación

```bash
cd ~/PycharmProjects/django-disposable-email
uv run pytest                     # 31 tests (sqlite en memoria, allauth y celery del grupo dev)

# Matriz mínima antes de publicar (versiones declaradas):
uv run --isolated --python 3.12 --with "django>=4.2,<5.0" --with "django-allauth==65.18.0" \
  --with pytest --with pytest-django --with celery --with-editable . pytest -q
uv run --isolated --python 3.12 --with "django>=5.2,<5.3" --with "django-allauth==65.18.0" \
  --with pytest --with pytest-django --with celery --with-editable . pytest -q
```

Si en el shell está activo el venv de otro proyecto, `uv` avisa
(`VIRTUAL_ENV … will be ignored`). Es inofensivo; se puede anteponer
`VIRTUAL_ENV=`.

- **Migraciones:**
  `uv run django-admin makemigrations disposable_email --settings=tests.settings --pythonpath=.`
  Revisarlas siempre a mano. Las que ya se han publicado no se editan nunca.
- **Traducciones:** desde `src/disposable_email/`, ejecutar
  `uv run --project ../.. django-admin makemessages -l es --settings=tests.settings --pythonpath=../..`,
  completar el `.po` y compilar con
  `msgfmt -c -o locale/es/LC_MESSAGES/django.mo locale/es/LC_MESSAGES/django.po`.
  El `.mo` viaja en el wheel.
- **Empaquetado:**
  - `uv build`;
  - comprobar que el wheel SOLO contiene `disposable_email/` (con locale y
    migrations) y `*.dist-info`, NUNCA un paquete `tests` de primer nivel.
    Es el fallo de `django-encrypted-field` 1.1.0/1.1.1, que rompía los tests
    de los proyectos que lo instalaban;
  - el layout `src/` y `packages = ["src/disposable_email"]` lo evitan; el
    sdist incluye `tests/` a propósito, y solo él.
- **Versionado:**
  - SemVer, con la versión en `pyproject.toml` y en `__init__.__version__`
    (en los dos sitios);
  - entrada en `CHANGES.md` con fecha.
- **Publicación:** la hace SIEMPRE Román, con `uv build && uv publish`. Lo
  mismo para el repo en GitHub (`github.com/juliusdeane/django-disposable-email`,
  pendiente de crear) y para etiquetas y commits: Claude no hace ninguna
  operación git de escritura (regla global).

---

## 10. Convenciones

- Código, cadenas fuente, README y CHANGES en inglés (paquete público). Este
  CLAUDE.md, en español.
- Sin emojis.
- Nada en `__init__.py` que importe modelos o allauth.
- Todo lo de allauth vive en `disposable_email.allauth`, y solo se importa si
  allauth está instalado. `system_checks` lo importa de forma perezosa,
  dentro de la comprobación de `apps.is_installed`.
- Fallar cerrado: ante la duda (BD caída, interruptor roto), se sigue
  bloqueando. Pero NUNCA se rompe un alta por un fallo de auditoría, de señal
  o de log.
- No guardar ni registrar en logs el email completo: siempre enmascarado o
  solo el dominio.
- Toda funcionalidad nueva llega con tests, contra allauth real por HTTP
  cuando toque formularios, y con su entrada en README, CHANGES y aquí.

---

## 11. Pendiente / ideas

- ~~Publicar 1.0.0 en PyPI~~ HECHO (2026-10-09, la publicó Román;
  ScenariumIT ya lo instala desde PyPI). Falta crear el repo en GitHub
  (`github.com/juliusdeane/django-disposable-email`); los enlaces de PyPI
  apuntan ahí.
- ~~Migrar ReciBRO, Taxiquo, Taska, EasyContract y Attentiometer e integrarlo
  en RootedArbiter~~ HECHO el 2026-10-09 (§7).
- allauth headless: Taxiquo expone `allauth.headless` y sus endpoints de alta
  y gestión de email no pasan por `ACCOUNT_FORMS`, así que el mixin no actúa;
  la señal social sí, pero responde con un 302 en vez de un error JSON.
  Candidato a 1.1.0.
- `enforce(..., force=True)` para validaciones obligatorias que ignoran el
  interruptor (hoy RootedArbiter lo monta a mano con `check_email(force=True)`
  y `record_blocked`). Candidato a 1.1.0.
- Posibles mejoras, a decidir con Román (ninguna implementada):
  - comprobación MX opcional, para dominios nuevos que aún no están en la lista;
  - más fuentes de listas;
  - acción del admin «actualizar lista ahora»;
  - purga de `BlockedAttempt` por antigüedad (retención RGPD configurable);
  - soporte de allauth headless (API), sin probar todavía.
