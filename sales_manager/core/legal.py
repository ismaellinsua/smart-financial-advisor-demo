"""The terms each business accepts to use the service: the conditions of the service and the data processing
agreement (contrato de encargado del tratamiento, RGPD art. 28). Their text lives in legal/ and is published on the
website with ops/legal.py; this is the version a business accepts and where to read it."""

# Change it whenever either text changes in substance: every business's administrator accepts the new one.
TERMS_VERSION = "2026-10-07"
DOCUMENTS = {"condiciones": "Condiciones del servicio", "encargado": "Contrato de encargado del tratamiento"}


def document_url(base: str, name: str) -> str:
    return f"{base.rstrip('/')}/{name}.html"
