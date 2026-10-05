"""Application pages, one module per area. This module gathers the page functions `app.py` registers."""

from ui.pages_agenda import agenda_config, agenda_enabled, agenda_page
from ui.pages_automations import automations_page
from ui.pages_cash import cash_page
from ui.pages_customers import customers_page
from ui.pages_dashboard import dashboard
from ui.pages_help import help_page
from ui.pages_history import history
from ui.pages_pos import point_of_sale
from ui.pages_products import products_page
from ui.pages_settings import settings_page
from ui.pages_start import demo_banner, onboarding, switch_business_dialog
from ui.pages_team import team_page

__all__ = [
    "agenda_config", "agenda_enabled", "agenda_page", "automations_page", "cash_page", "customers_page", "dashboard",
    "demo_banner", "help_page", "history", "onboarding", "point_of_sale", "products_page", "settings_page",
    "switch_business_dialog", "team_page",
]
