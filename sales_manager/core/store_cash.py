"""Day summary and cash closing per location. Mixed into `Store`."""

import json
from decimal import Decimal
from datetime import date, datetime, time, timedelta

import pandas as pd

from . import clock
from .security import clean_text


class CashMixin:
    # -------------------------------------------------------------- cash closing
    def day_summary(self, day: date, location_id: int | None = None) -> dict:
        """Completed sales of one day, broken down by how they were paid (mixed payments split per method).
        `location_id`: only that location's till (with several locations)."""
        start = datetime.combine(day, time.min)
        where = " AND s.location_id = ?" if location_id is not None else ""
        with self.db.tx() as cur:
            rows = cur.execute(
                "SELECT s.id, s.status, p.method, p.amount FROM sales s LEFT JOIN sale_payments p ON p.sale_id = s.id "
                "WHERE s.created_at >= ? AND s.created_at < ?" + where,
                (start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds"),
                 *(() if location_id is None else (int(location_id),))),
            ).fetchall()
        breakdown: dict[str, dict] = {}
        completed, cancelled = set(), set()
        for r in rows:
            if r["status"] != "completada":
                cancelled.add(r["id"])
                continue
            completed.add(r["id"])
            if r["method"] is None:
                continue
            entry = breakdown.setdefault(r["method"], {"count": 0, "total": 0.0})
            entry["count"] += 1
            entry["total"] = round(entry["total"] + float(r["amount"]), 2)
        refunds = self.refunds_by_method(day, location_id)
        for method, amount in refunds.items():
            entry = breakdown.setdefault(method, {"count": 0, "total": 0.0})
            entry["refunded"] = amount
            entry["total"] = round(entry["total"] - amount, 2)  # net of what was handed back
        return {
            "breakdown": breakdown,
            "count": len(completed),
            "total": round(sum(e["total"] for e in breakdown.values()), 2),
            "cash": breakdown.get("Efectivo", {}).get("total", 0.0),
            "cancelled": len(cancelled),
            "refunded": round(sum(refunds.values()), 2),
        }

    def close_cash(
        self, day: date, opening_float: float, counted_cash: float, notes: str = "", when: datetime | None = None,
        closed_by: str = "", location_id: int | None = None,
    ) -> dict:
        """Record the end-of-day cash count. Expected cash = opening float + cash sales of the day."""
        if opening_float < 0 or counted_cash < 0:
            raise ValueError("Los importes no pueden ser negativos.")
        notes = clean_text(notes, "Notas", "notes")
        with self.db.tx() as cur:
            location_id = self._location_or_main(cur, location_id)
        summary = self.day_summary(day, location_id)
        expected = round(float(opening_float) + summary["cash"], 2)
        try:
            with self.db.tx() as cur:
                cur.execute(
                    "INSERT INTO cash_closings(day, opening_float, cash_sales, expected_cash, counted_cash, "
                    "difference, total_sales, sales_count, breakdown, notes, closed_at, closed_by, location_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (day.isoformat(), float(opening_float), summary["cash"], expected, float(counted_cash),
                     round(float(counted_cash) - expected, 2), summary["total"], summary["count"],
                     json.dumps(summary["breakdown"], ensure_ascii=False), notes,
                     (when or clock.now()).isoformat(timespec="seconds"), closed_by, location_id),
                )
        except self.db.integrity_errors as exc:
            raise ValueError("La caja de ese día ya está cerrada. Reábrela si necesitas repetir el cierre.") from exc
        return self.cash_closing(day, location_id)

    @staticmethod
    def _closing_where(location_id) -> tuple[str, tuple]:
        return ("location_id IS NULL", ()) if location_id is None else ("location_id = ?", (int(location_id),))

    def cash_closing(self, day: date, location_id: int | None = None) -> dict | None:
        with self.db.tx() as cur:
            where, args = self._closing_where(self._location_or_main(cur, location_id))
            row = cur.execute(f"SELECT * FROM cash_closings WHERE day = ? AND {where}",
                              (day.isoformat(), *args)).fetchone()
        if row:
            row = {**row, "breakdown": json.loads(row["breakdown"] or "{}")}
        return row

    def reopen_cash(self, day: date, location_id: int | None = None, by: str = "") -> None:
        """Reopen a closed day. The closing is copied whole to `cash_reopenings` first: what was counted, the
        difference and who closed it stay on record, and closing again later adds a new one."""
        with self.db.tx() as cur:
            where, args = self._closing_where(self._location_or_main(cur, location_id))
            row = cur.execute(f"SELECT * FROM cash_closings WHERE day = ? AND {where}" + self.db.for_update,
                              (day.isoformat(), *args)).fetchone()
            if row is None:
                return
            cur.execute("INSERT INTO cash_reopenings(day, location_id, closing, reopened_by, reopened_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (row["day"], row["location_id"], json.dumps({k: (float(v) if isinstance(v, Decimal) else v)
                                                                     for k, v in row.items()}, ensure_ascii=False),
                         str(by)[:60], clock.now().isoformat(timespec="seconds")))
            cur.execute("DELETE FROM cash_closings WHERE id = ?", (row["id"],))

    def cash_reopenings(self, location_id: int | None = None) -> pd.DataFrame:
        """Closings that were reopened, newest first, with what had been counted."""
        where, args = ("", ()) if location_id is None else (" WHERE location_id = ?", (int(location_id),))
        df = self._frame(f"SELECT day, closing, reopened_by, reopened_at FROM cash_reopenings{where} "
                         "ORDER BY id DESC", args)
        if not df.empty:
            closing = df["closing"].map(json.loads)
            df["counted_cash"] = closing.map(lambda c: float(c.get("counted_cash") or 0))
            df["difference"] = closing.map(lambda c: float(c.get("difference") or 0))
            df["closed_by"] = closing.map(lambda c: c.get("closed_by", ""))
        return df.drop(columns=["closing"])

    def cash_closings(self, location_id: int | None = None) -> pd.DataFrame:
        where, args = ("", ()) if location_id is None else (" WHERE location_id = ?", (int(location_id),))
        df = self._frame(
            "SELECT day, total_sales, sales_count, expected_cash, counted_cash, difference, closed_at "
            f"FROM cash_closings{where} ORDER BY day DESC", args
        )
        for col in ("total_sales", "expected_cash", "counted_cash", "difference"):
            df[col] = df[col].astype(float)
        return df
