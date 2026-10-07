"""Every value you have to invent before going live, generated at once, and where each one goes.

    python ops/preparar_produccion.py              # writes .env.produccion (git ignores it) and shows the 2FA QR
    python ops/preparar_produccion.py --qr         # shows the 2FA QR again, from .env.produccion

Run it once, on your own computer. It writes .env.produccion with:
  - the secrets it generates (DATA_KEY, BACKUP_PASSPHRASE, OPERATOR_PASSWORD, OPERATOR_TOTP_SECRET, APP_PASSWORD),
  - the fixed values production needs (MULTI_TENANT, REQUIRE_DATABASE…),
  - empty lines for what only your providers can give you (DATABASE_URL from Neon, STRIPE_* from Stripe…),
grouped by where each one goes: Render, GitHub Secrets or GitHub Variables. Copy them there, keep the file somewhere
safe (a password manager) and delete it from the computer.

It never overwrites an existing .env.produccion: DATA_KEY and BACKUP_PASSPHRASE must never change once in use (the
two-step keys and the backups made with them could no longer be read).
"""

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sales_manager"))

from core.security import new_totp_secret, totp_uri  # noqa: E402

OUT = ROOT / ".env.produccion"
WARNING = "NO SUBAS ESTE ARCHIVO A NINGÚN SITIO. Cópialo a un gestor de contraseñas y bórralo del ordenador."


def generated() -> dict[str, str]:
    """The secrets nobody gives you: long and random, from the operating system's secure generator."""
    return {
        "DATA_KEY": secrets.token_urlsafe(48),
        "BACKUP_PASSPHRASE": secrets.token_urlsafe(48),
        "OPERATOR_PASSWORD": secrets.token_urlsafe(24),
        "OPERATOR_TOTP_SECRET": new_totp_secret(),
        "APP_PASSWORD": secrets.token_urlsafe(24),
    }


def content(values: dict[str, str]) -> str:
    v = values
    return f"""# {WARNING}
# Generado por ops/preparar_produccion.py. Lo vacío lo da cada proveedor (indicado al lado).

# ======================= Render → servicio nirkana → Environment =======================
DATABASE_URL=                      # Neon → Connection string (con ?sslmode=require), región eu-central-1
MULTI_TENANT=true
REQUIRE_DATABASE=1
DATA_KEY={v["DATA_KEY"]}
OPERATOR_PASSWORD={v["OPERATOR_PASSWORD"]}
OPERATOR_TOTP_SECRET={v["OPERATOR_TOTP_SECRET"]}
APP_PASSWORD={v["APP_PASSWORD"]}
OPERATOR_EMAIL=                    # tu email, para los avisos de errores
APP_URL=                           # la dirección pública de la app, p. ej. https://app.nirkana.es
TERMS_URL=https://nirkana.es
STRIPE_SECRET_KEY=                 # Stripe → Developers → API keys (sk_live_…)
STRIPE_PRICE_ID=                   # Stripe → Product catalog → precio de la suscripción (price_…)
STRIPE_WEBHOOK_SECRET=             # Stripe → Webhooks → endpoint APP_URL/stripe/webhook (whsec_…)
SMTP_HOST=                         # p. ej. smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=                     # en Gmail, una contraseña de aplicación
SMTP_FROM=                         # p. ej. NirKanA <nirkana.oficial@gmail.com>

# ======================= GitHub → Settings → Secrets and variables → Actions → Secrets =======================
BACKUP_DATABASES=                  # nube=<el mismo DATABASE_URL>
BACKUP_PASSPHRASE={v["BACKUP_PASSPHRASE"]}
BACKUP_S3_BUCKET=                  # Cloudflare R2 / Backblaze B2: nombre del bucket de la copia externa
BACKUP_S3_ENDPOINT=                # p. ej. https://<cuenta>.r2.cloudflarestorage.com
BACKUP_S3_ACCESS_KEY_ID=
BACKUP_S3_SECRET_ACCESS_KEY=
OPERATOR_EMAIL=                    # el mismo que arriba
SMTP_HOST=                         # los mismos SMTP_* que arriba
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=

# ======================= GitHub → Settings → Secrets and variables → Actions → Variables =======================
PRODUCTION=true                    # con ella, un secreto que falte pone las copias en rojo en vez de saltarlas
"""


def read(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, rest = line.partition("=")
        if sep and not line.startswith("#"):
            values.setdefault(name.strip(), rest.split("#", 1)[0].strip())
    return values


def show_qr(secret: str) -> None:
    """The operator panel's two-step key, as a QR to scan with Google Authenticator or similar."""
    import segno

    uri = totp_uri(secret, "operador")
    print("\nEscanea este código con tu app de autenticación (verificación en dos pasos del panel ?operador):\n")
    segno.make(uri, error="m").terminal(compact=True)
    print(f"\nSi no puedes escanearlo, añade la cuenta a mano con esta clave: {secret}\n")


def main(argv: list[str] | None = None, out: Path = OUT) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qr", action="store_true", help="volver a mostrar el QR de la verificación en dos pasos")
    args = parser.parse_args(argv)
    if args.qr:
        if not out.exists():
            print(f"No existe {out.name}: ejecuta primero «python ops/preparar_produccion.py».")
            return 1
        show_qr(read(out)["OPERATOR_TOTP_SECRET"])
        return 0
    if out.exists():
        print(f"{out.name} ya existe y no se sobrescribe: DATA_KEY y BACKUP_PASSPHRASE no deben cambiar nunca.\n"
              "Para ver otra vez el QR: python ops/preparar_produccion.py --qr")
        return 1
    values = generated()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)  # only you can read it
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content(values))
    print(f"Creado {out} con los secretos generados y la lista de dónde va cada uno.\n{WARNING}")
    show_qr(values["OPERATOR_TOTP_SECRET"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
