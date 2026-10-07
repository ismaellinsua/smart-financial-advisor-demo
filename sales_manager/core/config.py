"""Every setting NirKanA reads, in one place: its name, what it is for and its default.

The app reads each one from Streamlit's Secrets (lower-case name) and, failing that, from an environment variable
(the same name in upper case), which is how the container and Render are configured. The scripts in ops/ read only
the environment. `.env.example` at the repository root is generated from this list (`python -m core.config`) and a
test keeps the two in step, so no setting goes undocumented.
"""

import os
from dataclasses import dataclass
from collections.abc import Callable

TRUE = ("1", "true", "si", "sí", "yes")


@dataclass(frozen=True)
class Setting:
    description: str
    default: str = ""
    secret: bool = False  # never shown, logged or committed
    used_by: str = "app"  # "app", "ops" (scripts and scheduled jobs) or "test"


SETTINGS: dict[str, Setting] = {
    # ---------------------------------------------------------------- storage
    "database_url": Setting("PostgreSQL (p. ej. Neon) donde viven los datos. Sin ella, un archivo SQLite local.",
                            secret=True),
    "require_database": Setting("1 en servidores cuyo disco se borra al desplegar: sin database_url no arrancan."),
    "db_pool_size": Setting("Conexiones por base de datos que mantiene cada servidor (1-50).", "5"),
    "trusted_proxies": Setting("Redes de proxies propios con IP pública (separadas por comas), además de las privadas, "
                               "para saber la IP real de cada visitante."),
    "log_level": Setting("Detalle del registro del servidor: DEBUG, INFO, WARNING o ERROR.", "INFO"),
    # ---------------------------------------------------------------- access
    "app_password": Setting("Prueba de propiedad al crear el primer administrador en una app publicada.", secret=True),
    "multi_tenant": Setting("true para servir varios negocios desde una app y una base de datos."),
    "data_key": Setting("Clave larga y aleatoria con la que se cifran en la base de datos las claves de verificación "
                        "en dos pasos. Guárdala aparte: si se pierde, hay que volver a activar la verificación.",
                        secret=True),
    "operator_password": Setting("Contraseña del panel ?operador (modo varios negocios).", secret=True),
    "operator_totp_secret": Setting("Clave de verificación en dos pasos del panel ?operador.", secret=True),
    # ---------------------------------------------------------------- email
    "smtp_host": Setting("Servidor SMTP para avisos, recordatorios y recuperar la contraseña."),
    "smtp_port": Setting("Puerto SMTP (587 con STARTTLS).", "587"),
    "smtp_user": Setting("Usuario SMTP."),
    "smtp_password": Setting("Contraseña SMTP (en Gmail, una contraseña de aplicación).", secret=True),
    "smtp_from": Setting("Remitente visible, p. ej. «NirKanA <nirkana.oficial@gmail.com>»."),
    # ---------------------------------------------------------------- billing
    "stripe_secret_key": Setting("Clave secreta de Stripe; sin ella y stripe_price_id no se cobra a nadie.",
                                 secret=True),
    "stripe_price_id": Setting("Precio (price_…) de la suscripción en Stripe."),
    "stripe_webhook_secret": Setting("Secreto de firma del webhook de Stripe (whsec_…).", secret=True),
    "stripe_api_base": Setting("API de Stripe; solo se cambia para probar con stripe-mock.",
                               "https://api.stripe.com/v1"),
    "trial_days": Setting("Días de prueba gratis de un negocio nuevo (0-365).", "30"),
    "app_url": Setting("Dirección pública de la app, para volver de Stripe Checkout."),
    "terms_url": Setting("Web donde están publicadas las condiciones y el contrato de encargado (p. ej. "
                         "https://nirkana.es). Con ella, cada negocio los acepta antes de usar la app."),
    "webhook_port": Setting("Puerto interno del servicio de webhooks.", "8502"),
    "sessions_port": Setting("Puerto interno del servicio que escribe la cookie de sesión HttpOnly.", "8503"),
    # ---------------------------------------------------------------- ops
    "backup_databases": Setting("Bases de datos a copiar, una por línea: nombre=postgresql://…", secret=True,
                                used_by="ops"),
    "backup_passphrase": Setting("Frase con la que se cifran las copias de seguridad.", secret=True, used_by="ops"),
    "restore_url": Setting("PostgreSQL de pruebas donde ensayar la restauración de una copia.", secret=True,
                           used_by="ops"),
    "restore_target_url": Setting("Base de datos vacía donde restaurar una copia completa (ops/backup.py --restore).",
                                  secret=True, used_by="ops"),
    "notify_databases": Setting("Bases de datos a las que enviar avisos (por defecto, las de las copias).",
                                secret=True, used_by="ops"),
    "operator_email": Setting("Email del operador para avisos de caídas y resúmenes.", used_by="ops"),
    "uptime_urls": Setting("Direcciones a vigilar, una por línea.", used_by="ops"),
    "capturas_solo": Setting("Rehacer solo una parte de las capturas (p. ej. autonomo).", used_by="ops"),
    # ---------------------------------------------------------------- tests
    "test_database_url": Setting("PostgreSQL desechable para las pruebas.", secret=True, used_by="test"),
    "e2e_chromium": Setting("Chromium para las pruebas en navegador y las capturas.", used_by="test"),
    "stripe_mock_url": Setting("stripe-mock local para comprobar las llamadas a Stripe.", used_by="test"),
}

Lookup = Callable[[str], object]


def value(name: str, lookup: Lookup | None = None) -> str:
    """The setting from `lookup` (e.g. Streamlit secrets), else the environment, else its default."""
    setting = SETTINGS[name]  # a typo fails loudly instead of silently reading nothing
    found = None
    if lookup is not None:
        try:
            found = lookup(name)
        except Exception:  # no secrets file
            found = None
    return str(found or os.environ.get(name.upper(), "") or setting.default).strip()


def flag(name: str, lookup: Lookup | None = None) -> bool:
    return value(name, lookup).lower() in TRUE


def integer(name: str, lookup: Lookup | None = None, low: int = 0, high: int = 10**9) -> int:
    """Within [low, high]; the default when the value is not a number."""
    try:
        number = int(value(name, lookup))
    except ValueError:
        number = int(SETTINGS[name].default)
    return max(low, min(number, high))


def example() -> str:
    """The contents of .env.example."""
    lines = ["# Every setting NirKanA reads (generated by `python -m core.config` from sales_manager/core/config.py).",
             "# In Streamlit Secrets use the lower-case name; as environment variables, the upper-case one.",
             "# Never commit real values: copy this file to .env, which git ignores.", ""]
    groups = {"app": "La app", "ops": "Copias, avisos y vigilancia (ops/)", "test": "Pruebas"}
    for group, title in groups.items():
        lines.append(f"# ---- {title}")
        for name, setting in SETTINGS.items():
            if setting.used_by == group:
                lines.append(f"# {setting.description}" + (" (secreto)" if setting.secret else ""))
                lines.append(f"{name.upper()}={'' if setting.secret else setting.default}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(example(), end="")
