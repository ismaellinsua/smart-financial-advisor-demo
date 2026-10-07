"""Shared per-run context for pages."""

from dataclasses import dataclass, field

import streamlit as st

from core import clock, config
from core.db import Store
from core.presets import CURRENCIES, PRESETS
from core.pricing import format_money, format_money_short

# Filled by app.py so pages can link to each other.
PAGES: dict = {}


def secrets_lookup(name: str):
    """Streamlit secrets; core.config falls back to the environment."""
    return st.secrets.get(name)


def setting(name: str) -> str:
    """A setting listed in core/config.py, from the Secrets or the environment."""
    return config.value(name, secrets_lookup)



def database_url() -> str | None:
    """PostgreSQL URL from Streamlit secrets (`database_url`) or the DATABASE_URL environment variable."""
    return setting("database_url") or None


def multi_tenant() -> bool:
    """One app and one database for several businesses (secret `multi_tenant = true`), each chosen in the address
    with ?negocio=code. Off by default: a single-business deployment works as always."""
    return config.flag("multi_tenant", secrets_lookup) and bool(database_url())


@st.cache_resource(show_spinner=False)
def get_directory():
    from core.tenants import Directory

    return Directory(database_url())


def tenant_code() -> str:
    """The business this session is serving (multi-business mode only)."""
    return st.session_state.get("tenant", "")


class MissingDatabase(RuntimeError):
    """A server whose disk is wiped on every deploy (the container) must keep the data in an external database."""


def require_external_database() -> bool:
    return config.flag("require_database")  # the server's environment only, never a business's secret


@st.cache_resource(show_spinner="Conectando con la base de datos…")
def _single_store() -> Store:
    url = database_url()
    if not url and require_external_database():
        raise MissingDatabase("DATABASE_URL no está definida")
    return Store(url) if url else Store()


def _release(store: Store) -> None:
    store.close()  # the pool it shares stays open while any other business or the directory uses it


@st.cache_resource(show_spinner="Conectando con tu negocio…", on_release=_release,
                   max_entries=config.integer("tenant_cache_size", low=10, high=100_000))
def _tenant_store(code: str) -> Store:
    return get_directory().store(code)


def get_store() -> Store:
    if multi_tenant():
        code = tenant_code()
        if not code:
            raise RuntimeError("No hay ningún negocio elegido en esta sesión.")
        return _tenant_store(code)
    return _single_store()


@dataclass
class Ctx:
    store: Store
    settings: dict
    preset: dict
    symbol: str
    user: dict | None = None
    locations: list = field(default_factory=list)  # active locations; empty for a business with one place

    @property
    def role(self) -> str:
        # No signed-in user means the least privileged role, never the most.
        return self.user["role"] if self.user else "empleado"

    @property
    def who(self) -> str:
        """Name that signs sales, invoices and closings; also used in the audit log."""
        return self.user["name"] if self.user else ""

    @property
    def username(self) -> str:
        return self.user["username"] if self.user else ""

    def can(self, needed: str) -> bool:
        return Store.can(self.role, needed)

    @property
    def read_only(self) -> bool:
        """The business's subscription is not active: it may look up and download, never change anything."""
        access = st.session_state.get("billing_access")
        return access is not None and access.level == "readonly"

    def can_change(self, needed: str) -> bool:
        """`can`, and the business may still record things (see read_only)."""
        return self.can(needed) and not self.read_only

    def money(self, value: float) -> str:
        return format_money(float(value), self.symbol)

    def money_short(self, value: float) -> str:
        return format_money_short(float(value), self.symbol)

    @property
    def multi_location(self) -> bool:
        """Several places open: show where things happen and let people choose."""
        return len(self.locations) >= 2

    @property
    def fixed_location(self) -> int | None:
        """The location this person is pinned to, if any (and still open)."""
        pinned = (self.user or {}).get("location_id")
        return pinned if any(loc["id"] == pinned for loc in self.locations) else None

    @property
    def location_id(self) -> int | None:
        """Where this session sells, counts cash and moves stock; None for a business with one place."""
        if not self.locations:
            return None
        chosen = self.fixed_location or st.session_state.get("location")
        return chosen if any(loc["id"] == chosen for loc in self.locations) else self.locations[0]["id"]

    @property
    def location_name(self) -> str:
        return next((loc["name"] for loc in self.locations if loc["id"] == self.location_id), "")

    def products_here(self):
        """Active catalogue with `stock` as the units at this session's location (the total with one place)."""
        products = self.store.products()
        if self.locations and self.store.multi_location():
            here = self.store.stock_at(self.location_id)
            products["stock"] = products["id"].map(here).fillna(0).astype(int)
        return products

    def ticket_settings(self, location_id: int | None = None) -> dict:
        """Business data for a ticket, with the location it was sold at (its address and phone) when there are
        several."""
        loc = next((x for x in self.store.locations(include_inactive=True) if x["id"] == location_id), None)
        if not self.multi_location or loc is None:
            return self.settings
        return {**self.settings, "location_line": " · ".join(x for x in (loc["name"], loc["address"], loc["phone"])
                                                               if x)}

    @property
    def tax_rate(self) -> float:
        return float(self.settings.get("tax_rate") or 0)


def ctx() -> Ctx:
    store = get_store()
    settings = store.settings()
    clock.set_timezone(settings.get("timezone"))  # every date and time the app shows or saves
    return Ctx(
        store=store,
        settings=settings,
        preset=PRESETS.get(settings["business_type"], PRESETS["retail"]),
        symbol=CURRENCIES.get(settings["currency"], "€"),
        user=st.session_state.get("user"),
        locations=store.locations(),
    )


def _log_export(file_name: str) -> None:
    c = ctx()
    c.store.audit(c.username, "exportacion", file_name)


def logged_download(where, label: str, data, file_name: str, *args, **kwargs):
    """A download of business data that leaves a line in the activity log (who took what, and when)."""
    return where.download_button(label, data, file_name, *args, on_click=_log_export, args=(file_name,), **kwargs)


def stripe_client():
    """The service's Stripe account, or None while billing is off (single business, or no Stripe secrets)."""
    from core.billing import Stripe

    key, price = setting("stripe_secret_key"), setting("stripe_price_id")
    if not (multi_tenant() and key and price):
        return None
    return Stripe(key, price)


def trial_days() -> int:
    return config.integer("trial_days", secrets_lookup, 0, 365)
