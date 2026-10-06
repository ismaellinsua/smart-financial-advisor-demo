"""Online booking: free times follow the business's rules, a slot can't be taken twice, customers cancel with their
own link, reminders go once, and contact details don't outlive the appointment by more than 90 days."""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.booking_mail import calendar_file, send_reminders
from core.notifications import send_due
from core.store_bookings import CONTACT_DAYS, parse_closed_days, parse_ranges
from test_notifications import FakeMailer

NOW = datetime(2026, 10, 5, 9, 0)  # a Monday
MON, TUE, WED = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)
ROOT = str(Path(__file__).resolve().parent.parent)


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hh, mm)


RULES = {"enabled": True, "hours": {0: "10:00-14:00", 1: "10:00-14:00"}, "closed": "", "services": [],
         "duration": 60, "step": 30, "days": 14, "notice_hours": 2}


@pytest.fixture
def diary(make_store):
    """One person's diary (services): appointments never overlap."""
    s = make_store()
    s.load_preset("services", with_demo_sales=False)
    s.save_settings({"business_name": "Peluquería Sol", "demo_mode": "no", "email": "sol@example.com"})
    s.save_booking_rules(RULES)
    return s


@pytest.fixture
def restaurant(make_store):
    s = make_store()
    s.load_preset("restaurant", with_demo_sales=False)
    s.save_settings({"demo_mode": "no"})
    s.save_booking_rules({**RULES, "duration": 90, "capacity": 6, "max_party": 6})
    return s


def test_opening_hours_are_read_and_checked():
    assert parse_ranges("09:00-14:00, 16:30-20:00") == [(at(MON, 9).time(), at(MON, 14).time()),
                                                         (at(MON, 16, 30).time(), at(MON, 20).time())]
    assert parse_ranges("") == []
    for bad in ("9-14", "14:00-09:00", "09:00-14:00, 13:00-15:00", "25:00-26:00"):
        with pytest.raises(ValueError):
            parse_ranges(bad)
    assert parse_closed_days("24/12/2026; 25/12/2026") == {date(2026, 12, 24), date(2026, 12, 25)}
    with pytest.raises(ValueError):
        parse_closed_days("2026-12-24")


def test_free_times_follow_hours_notice_closed_days_and_window(diary):
    # Monday 9:00 with 2 h notice: from 11:00; the last 60-minute appointment starts at 13:00.
    assert [f"{s:%H:%M}" for s in diary.free_slots(MON, now=NOW)] == ["11:00", "11:30", "12:00", "12:30", "13:00"]
    assert len(diary.free_slots(TUE, now=NOW)) == 7
    assert diary.free_slots(WED, now=NOW) == []  # closed on Wednesdays
    assert diary.free_slots(MON + timedelta(days=21), now=NOW) == []  # beyond the 14 days
    assert diary.free_slots(MON - timedelta(days=7), now=NOW) == []  # the past
    diary.save_booking_rules({**RULES, "closed": "06/10/2026"})
    assert diary.free_slots(TUE, now=NOW) == []
    assert TUE not in diary.bookable_days(now=NOW) and MON + timedelta(days=7) in diary.bookable_days(now=NOW)


def test_a_slot_cannot_be_taken_twice_and_the_team_diary_counts(diary):
    first = diary.book_online(at(MON, 11), "Lucía", "600 111 222", now=NOW)
    assert first["status"] == "pendiente" and first["token"]
    assert [f"{s:%H:%M}" for s in diary.free_slots(MON, now=NOW)] == ["12:00", "12:30", "13:00"]
    with pytest.raises(ValueError, match="ocupar"):
        diary.book_online(at(MON, 11, 30), "Pedro", "600 333 444", now=NOW)
    diary.create_appointment(at(MON, 12, 30), 60, customer_name="Cliente de mostrador", created_by="Ana")
    assert diary.free_slots(MON, now=NOW) == []
    with pytest.raises(ValueError, match="no está disponible"):
        diary.book_online(at(MON, 11, 15), "Pedro", "600 333 444", now=NOW)  # not a start time on offer
    with pytest.raises(ValueError, match="no está disponible"):
        diary.book_online(at(MON, 9), "Pedro", "600 333 444", now=NOW)  # inside the notice period


def test_the_public_page_learns_nothing_about_other_customers(diary):
    diary.book_online(at(MON, 11), "Lucía Secreta", "600 111 222", now=NOW)
    slots = diary.free_slots(MON, now=NOW)
    assert all(isinstance(s, datetime) for s in slots)  # only times, no names or phones


def test_one_phone_cannot_fill_the_diary(diary):
    diary.book_online(at(TUE, 10), "Lucía", "600111222", now=NOW)
    diary.book_online(at(TUE, 11), "Lucía", "600111222", now=NOW)
    with pytest.raises(ValueError, match="reservas pendientes"):
        diary.book_online(at(TUE, 12), "Lucía", "600111222", now=NOW)
    for bad in ("123", "abc"):
        with pytest.raises(ValueError, match="teléfono"):
            diary.book_online(at(TUE, 13), "Otra", bad, now=NOW)
    with pytest.raises(ValueError, match="email"):
        diary.book_online(at(TUE, 13), "Otra", "600999888", email="sin-arroba", now=NOW)


def test_services_on_offer_are_the_only_choice(diary):
    offered, other = [int(i) for i in diary.products()["id"][:2]]
    diary.save_booking_rules({**RULES, "services": [offered]})
    with pytest.raises(ValueError, match="servicio"):
        diary.book_online(at(TUE, 10), "Lucía", "600111222", product_id=other, now=NOW)
    booking = diary.book_online(at(TUE, 10), "Lucía", "600111222", product_id=offered, now=NOW)
    assert booking["service"] == diary.products().set_index("id").loc[offered, "name"]


def test_customers_cancel_with_their_own_link_only(diary):
    booking = diary.book_online(at(TUE, 10), "Lucía", "600111222", now=NOW)
    stored = diary._frame("SELECT cancel_hash FROM appointments WHERE id = ?", (booking["id"],)).iloc[0, 0]
    assert stored and booking["token"] not in stored  # only its hash is kept
    assert diary.online_booking("otro-token") is None and diary.online_booking("") is None
    assert len(diary.free_slots(TUE, now=NOW)) == 5
    assert diary.cancel_online_booking(booking["token"], now=NOW)["status"] == "cancelada"
    assert len(diary.free_slots(TUE, now=NOW)) == 7  # the time is free again
    with pytest.raises(ValueError):
        diary.cancel_online_booking(booking["token"], now=NOW)
    late = diary.book_online(at(TUE, 12), "Pedro", "600333444", now=NOW)
    with pytest.raises(ValueError, match="empezado"):
        diary.cancel_online_booking(late["token"], now=at(TUE, 12, 5))


def test_closed_unless_the_business_opens_it(diary):
    diary.save_booking_rules({**RULES, "enabled": False})
    with pytest.raises(ValueError, match="no acepta"):
        diary.book_online(at(TUE, 10), "Lucía", "600111222", now=NOW)
    with pytest.raises(ValueError, match="horario"):
        diary.save_booking_rules({**RULES, "hours": {}})


def test_restaurant_counts_diners_not_tables(restaurant):
    restaurant.book_online(at(TUE, 12), "Mesa A", "600000001", people=4, now=NOW)
    restaurant.book_online(at(TUE, 12), "Mesa B", "600000002", people=2, now=NOW)  # 6 of 6 seats
    assert at(TUE, 12) not in restaurant.free_slots(TUE, people=1, now=NOW)
    assert at(TUE, 12, 30) not in restaurant.free_slots(TUE, people=1, now=NOW)  # still eating at 12:30
    with pytest.raises(ValueError, match="ocupar"):
        restaurant.book_online(at(TUE, 12), "Mesa C", "600000003", people=1, now=NOW)
    with pytest.raises(ValueError, match="llama"):
        restaurant.book_online(at(TUE, 10), "Grupo", "600000004", people=7, now=NOW)
    restaurant.create_appointment(at(TUE, 10), 90, customer_name="Por teléfono", allow_overlap=True)  # no size: 2
    assert at(TUE, 10) in restaurant.free_slots(TUE, people=4, now=NOW)
    assert at(TUE, 10) not in restaurant.free_slots(TUE, people=5, now=NOW)


def test_reminders_go_once_the_day_before(diary):
    diary.book_online(at(TUE, 10), "Lucía", "600111222", email="lucia@example.com", now=NOW)
    diary.book_online(at(TUE, 11), "Sin email", "600333444", now=NOW)
    mailer = FakeMailer()
    assert send_reminders(diary, mailer, diary.settings(), at(MON, 7)) == 1
    assert mailer.sent[0][0] == "lucia@example.com" and "Peluquería Sol" in mailer.sent[0][1]
    assert mailer.last["Reply-To"] == "sol@example.com"  # the customer answers the business
    assert send_reminders(diary, mailer, diary.settings(), at(MON, 8)) == 0
    assert send_reminders(diary, FakeMailer(), diary.settings(), at(TUE, 7)) == 0  # not on the day itself


def test_the_daily_job_reminds_without_a_business_email_but_never_in_demo_mode(diary):
    diary.book_online(at(TUE, 10), "Lucía", "600111222", email="lucia@example.com", now=NOW)
    diary.save_settings({"email": "", "demo_mode": "si"})
    assert send_due(diary, FakeMailer(), at(MON, 7)) == []
    diary.save_settings({"demo_mode": "no"})
    assert send_due(diary, FakeMailer(), at(MON, 7)) == ["1 recordatorio(s) de cita"]


def test_contact_details_are_erased_after_the_retention_period(diary):
    booking = diary.book_online(at(TUE, 10), "Lucía", "600111222", email="lucia@example.com", now=NOW)
    assert diary.forget_booking_contacts(at(TUE, 10) + timedelta(days=CONTACT_DAYS - 1)) == 0
    assert diary.forget_booking_contacts(at(TUE, 10) + timedelta(days=CONTACT_DAYS + 1)) == 1
    row = diary._frame("SELECT phone, email, cancel_hash, customer_name FROM appointments WHERE id = ?",
                       (booking["id"],)).iloc[0]
    assert (row["phone"], row["email"], row["cancel_hash"]) == ("", "", "") and row["customer_name"] == "Lucía"


def test_calendar_file_is_in_the_business_time_zone(diary):
    booking = diary.book_online(at(TUE, 10), "Lucía", "600111222", now=NOW)
    ics = calendar_file(booking, {**diary.settings(), "address": "Calle Mayor, 1"}).decode()
    assert "DTSTART;TZID=Europe/Madrid:20261006T100000" in ics and "DTEND;TZID=Europe/Madrid:20261006T110000" in ics
    assert "LOCATION:Calle Mayor\\, 1" in ics and ics.endswith("END:VCALENDAR\r\n")


PAGE = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
from core.db import Store
from ui import booking
store = Store({db!r})
booking.public_page(store, store.settings())
"""


def test_public_page_books_and_cancels(module_targets):
    from core.db import Store

    target = module_targets.new()
    store = Store(target)
    store.load_preset("services", with_demo_sales=False)
    store.save_settings({"business_name": "Peluquería Sol", "demo_mode": "no"})
    store.close()
    page = AppTest.from_string(PAGE.format(root=ROOT, db=target), default_timeout=30)
    page.query_params["reservar"] = ""
    page.run()
    assert not page.exception and "no tiene reservas online" in page.info[0].value

    store = Store(target)
    store.save_booking_rules({**RULES, "hours": {d: "08:00-22:00" for d in range(7)}, "notice_hours": 0})
    store.close()
    page.run()
    page.pills[0].set_value(page.pills[0].options[0]).run()
    fields = {t.label: t for t in page.text_input}
    fields["Nombre"].input("Lucía")
    fields["Teléfono"].input("600111222")
    page.button[0].click().run()  # without accepting the data notice
    assert "aceptar" in page.error[0].value
    page.checkbox[0].check()
    page.button[0].click().run()
    assert not page.exception, page.exception
    assert "Reserva confirmada" in page.success[0].value
    link = page.code[0].value
    assert "reservar&cancelar=" in link

    cancel = AppTest.from_string(PAGE.format(root=ROOT, db=target), default_timeout=30)
    cancel.query_params["reservar"] = ""
    cancel.query_params["cancelar"] = link.split("cancelar=")[1]
    cancel.run()
    assert "Lucía" in cancel.markdown[-1].value or any("Lucía" in m.value for m in cancel.markdown)
    cancel.button[0].click().run()
    assert not cancel.exception and "cancelada" in cancel.info[0].value


def test_public_booking_cannot_be_used_to_spam(diary):
    """Names with links are refused, an email holds at most two pending bookings, and the whole business takes at
    most MAX_ONLINE_PER_HOUR online bookings an hour."""
    from core import store_bookings

    diary.save_booking_rules({**RULES, "hours": {d: "08:00-22:00" for d in range(7)}, "step": 15, "duration": 15})
    slots = [s for d in diary.bookable_days(NOW) for s in diary.free_slots(d, now=NOW)]
    with pytest.raises(ValueError, match="sin enlaces"):
        diary.book_online(slots[0], "Gana dinero en http://estafa.example", "600111222", now=NOW)
    with pytest.raises(ValueError, match="sin enlaces"):
        diary.book_online(slots[0], "visita ejemplo.com", "600111222", now=NOW)
    for i in range(2):
        diary.book_online(slots[i], "Ana", f"60011122{i}", email="victima@example.com", now=NOW)
    with pytest.raises(ValueError, match="este email"):
        diary.book_online(slots[2], "Ana", "600111229", email="VICTIMA@example.com", now=NOW)
    for i in range(store_bookings.MAX_ONLINE_PER_HOUR - 2):
        diary.book_online(slots[3 + i], "Cliente", f"6{i:08d}", now=NOW)
    with pytest.raises(ValueError, match="más reservas online"):
        diary.book_online(slots[40], "Otra", "699999999", now=NOW)
    later = NOW + timedelta(hours=1, minutes=1)  # the next hour opens again
    free = [s for d in diary.bookable_days(later) for s in diary.free_slots(d, now=later)]
    diary.book_online(free[-1], "Otra", "699999999", now=later)
