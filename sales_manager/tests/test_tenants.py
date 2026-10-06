"""Several businesses in one database: each in its own schema, with nothing shared between them."""

import threading
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

from conftest import PG_URL
from core import clock

pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def directory():
    import psycopg

    from core.tenants import Directory

    name = f"nk_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    url = urlunsplit(urlsplit(PG_URL)._replace(path=f"/{name}"))
    yield Directory(url)
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def _sell(store):
    store.load_preset("retail", with_demo_sales=False)
    df = store.products()
    pid = int(df.loc[df["sku"] == "CAM-001", "id"].iloc[0])
    return store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")


def test_each_business_sees_only_its_own_data(directory):
    directory.create("cafe-aurora", "Café Aurora")
    directory.create("tienda-sol", "Tienda Sol")
    aurora, sol = directory.store("cafe-aurora"), directory.store("tienda-sol")
    try:
        sale = _sell(aurora)
        aurora.create_user("Ana", "ana", "admin", "Segura2026!")
        assert len(aurora.sales()) == 1 and sol.sales().empty
        assert sol.users().empty and not sol.has_users()
        assert aurora.settings()["business_name"] == "Café Aurora" and sol.settings()["business_name"] == "Tienda Sol"
        sol.create_user("Ana", "ana", "admin", "OtraClave2026!")  # same username, different business
        assert sale["number"] == f"VTA-{clock.now().year}-00001"
        assert _sell(sol)["number"] == sale["number"]  # each business numbers its own tickets
    finally:
        aurora.close()
        sol.close()
    overview = {t["code"]: t for t in directory.overview()}
    assert overview["cafe-aurora"]["sales"] == 1 and overview["cafe-aurora"]["users"] == 1


def test_codes_are_checked(directory):
    for bad in ("ab", "Café", "con espacio", "-guion", "guion-", "a--b", "operador", "x" * 41):
        with pytest.raises(ValueError):
            directory.create(bad, "Negocio")
    directory.create("bar-lucia", "Bar Lucía")
    with pytest.raises(ValueError, match="Ya existe"):
        directory.create("bar-lucia", "Otro")
    assert directory.get("BAR-LUCIA")["name"] == "Bar Lucía"
    assert directory.get("no-existe") is None and directory.get("'; drop table x; --") is None


def test_setup_code_creates_the_first_administrator_once(directory):
    setup = directory.create("bar-lucia", "Bar Lucía")
    assert not directory.check_setup_code("bar-lucia", "MALO1234")
    assert directory.check_setup_code("bar-lucia", setup.lower())
    directory.mark_setup_used("bar-lucia")
    assert not directory.check_setup_code("bar-lucia", setup)
    again = directory.new_setup_code("bar-lucia")
    assert again != setup and directory.check_setup_code("bar-lucia", again)
    assert [r["action"] for r in directory.log()][:3] == ["codigo_instalacion_nuevo", "administrador_creado",
                                                          "negocio_creado"]


def test_a_business_can_be_suspended_and_reactivated(directory):
    directory.create("bar-lucia", "Bar Lucía")
    directory.set_status("bar-lucia", "suspendido")
    assert directory.get("bar-lucia")["status"] == "suspendido"
    directory.set_status("bar-lucia", "activo")
    assert directory.get("bar-lucia")["status"] == "activo"
    with pytest.raises(ValueError):
        directory.set_status("bar-lucia", "borrado")


def test_the_clock_is_per_request_so_businesses_keep_their_own_time_zone():
    seen = {}

    def run(name, zone):
        clock.set_timezone(zone)
        seen[name] = clock.timezone_name()

    threads = [threading.Thread(target=run, args=("madrid", "Europe/Madrid")),
               threading.Thread(target=run, args=("canarias", "Atlantic/Canary"))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert seen == {"madrid": "Europe/Madrid", "canarias": "Atlantic/Canary"}


def test_scheduled_jobs_walk_every_active_business(directory):
    import subprocess
    import sys
    from pathlib import Path

    from core.tenants import businesses_in

    directory.create("cafe-aurora", "Café Aurora")
    directory.create("tienda-sol", "Tienda Sol")
    directory.set_status("tienda-sol", "suspendido")
    url = directory._url
    assert businesses_in(url) == [("cafe-aurora", "n_cafe_aurora")]
    assert businesses_in(PG_URL) == [("", None)]  # a single-business database
    script = Path(__file__).resolve().parents[2] / "ops" / "notify.py"
    env = {"PATH": "/usr/bin:/bin", "NOTIFY_DATABASES": f"nube={url}"}
    dry = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env)
    assert dry.returncode == 0 and "sin configurar" in dry.stdout  # no SMTP: nothing is sent, nothing fails


def test_operator_sign_in_throttle_is_shared_and_hashed(directory):
    from core import throttle
    from core.tenants import DIRECTORY_SCHEMA, Directory

    other = Directory(directory._url)  # another server
    t0 = 1_800_000_000
    for i in range(throttle.MAX_FAILURES):
        (directory if i % 2 else other).throttle_failed("operador:1.2.3.4", now=t0 + i)
    assert directory.throttle_blocked_minutes("operador:1.2.3.4", now=t0 + 5) == throttle.FIRST_BLOCK_MINUTES
    assert other.throttle_blocked_minutes("operador:5.6.7.8", now=t0 + 5) == 0
    with directory._connect() as conn:
        keys = [r["key"] for r in conn.execute(f"SELECT key FROM {DIRECTORY_SCHEMA}.login_throttle").fetchall()]
    assert keys == [throttle.key_hash("operador:1.2.3.4")]
    other.throttle_succeeded("operador:1.2.3.4")
    assert directory.throttle_blocked_minutes("operador:1.2.3.4", now=t0 + 5) == 0


def test_directory_and_businesses_share_one_pool(directory):
    from core import engines

    directory.create("cafe-aurora", "Café Aurora")
    store = directory.store("cafe-aurora")
    assert store.db._pool is engines._POOLS[directory._pool_key][0]


def test_every_business_is_migrated_before_the_app_starts(directory):
    import subprocess
    import sys
    from pathlib import Path

    from core.db import VERSIONED_MIGRATIONS
    from core.tenants import migrate_all

    directory.create("cafe-aurora", "Café Aurora")
    directory.create("tienda-sol", "Tienda Sol")
    latest = max(v for v, *_ in VERSIONED_MIGRATIONS)
    assert migrate_all(directory._url) == [("cafe-aurora", latest), ("tienda-sol", latest)]

    script = Path(__file__).resolve().parents[2] / "ops" / "deploy" / "migrate.py"
    ran = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120,
                         env={"DATABASE_URL": directory._url, "PATH": "/usr/bin:/bin"})
    assert ran.returncode == 0 and "migrated business=tienda-sol" in ran.stderr
    broken = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120,
                            env={"DATABASE_URL": "postgresql://nadie:nada@127.0.0.1:1/ninguna", "PATH": "/usr/bin:/bin"})
    assert broken.returncode == 1 and "migrate_failed" in broken.stderr


def test_an_operator_code_opens_the_panel_once_on_every_server(directory):
    from core.tenants import Directory

    other = Directory(directory._url)  # another server, or the same one after a restart
    assert directory.claim_operator_step(1000)
    assert not other.claim_operator_step(1000)  # the same code, again
    assert not other.claim_operator_step(999)  # an older one
    assert other.claim_operator_step(1001)


def test_operator_overview_takes_three_queries_whatever_the_number_of_businesses(directory, monkeypatch):
    import psycopg

    for i in range(6):
        directory.create(f"negocio-{i}", f"Negocio {i}")
    _sell(directory.store("negocio-3"))
    calls = []
    original = psycopg.Connection.execute
    monkeypatch.setattr(psycopg.Connection, "execute",
                        lambda self, query, params=None, **kw: calls.append(query) or original(self, query, params, **kw))
    overview = {t["code"]: t for t in directory.overview()}
    calls = [q for q in calls if str(q).strip()]  # the pool's own connection check sends an empty query
    assert len(calls) == 3, calls
    assert overview["negocio-3"]["sales"] == 1 and overview["negocio-3"]["last_sale"]
    assert overview["negocio-0"]["sales"] == 0 and overview["negocio-0"]["users"] == 0
