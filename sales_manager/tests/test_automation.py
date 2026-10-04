"""Tests for core/automation.py - KPIs, stock alerts, reorder and customer insights."""

import pytest
from datetime import datetime, timedelta
import pandas as pd

from core.automation import (
    period_bounds, kpis, low_stock, reorder_suggestions, inactive_customers,
    followup_message, customer_ranking, insights
)


class TestPeriodBounds:
    def test_period_bounds_windows(self):
        """Period bounds returns correct date windows."""
        now = datetime(2026, 1, 15, 14, 30, 0)
        start, end, prev_start = period_bounds(7, now)

        # Verify structure: prev_start -> start -> end
        assert prev_start < start < end
        assert (start - prev_start).days == 7


class TestKPIs:
    @pytest.fixture
    def sample_data(self):
        """Sample sales and line data for KPI tests."""
        now = datetime(2026, 1, 15)
        start, end, prev_start = period_bounds(7, now)

        cur_sales = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'status': ['completada'] * 5,
            'total': [100.0] * 5,
            'created_at': [start + timedelta(hours=i) for i in range(5)]
        })

        prev_sales = pd.DataFrame({
            'id': [10, 11, 12, 13],
            'status': ['completada'] * 4,
            'total': [80.0] * 4,
            'created_at': [prev_start + timedelta(hours=i) for i in range(4)]
        })

        sales = pd.concat([cur_sales, prev_sales], ignore_index=True)

        cur_lines = pd.DataFrame({
            'created_at': [start + timedelta(hours=i) for i in range(5)],
            'revenue': [100.0] * 5,
            'margin': [30.0] * 5
        })

        prev_lines = pd.DataFrame({
            'created_at': [prev_start + timedelta(hours=i) for i in range(4)],
            'revenue': [80.0] * 4,
            'margin': [24.0] * 4
        })

        lines = pd.concat([cur_lines, prev_lines], ignore_index=True)

        return sales, lines, start, end, prev_start

    def test_kpis_revenue(self, sample_data):
        """KPIs correctly sum revenue."""
        sales, lines, start, end, prev_start = sample_data
        result = kpis(sales, lines, start, end, prev_start)

        assert result['revenue'] == 500.0
        assert result['count'] == 5
        assert result['ticket'] == 100.0

    def test_kpis_margin(self, sample_data):
        """Margin percentage calculated correctly."""
        sales, lines, start, end, prev_start = sample_data
        result = kpis(sales, lines, start, end, prev_start)

        assert result['margin_pct'] == 30.0

    def test_kpis_delta_calculations(self, sample_data):
        """Revenue and count deltas show growth."""
        sales, lines, start, end, prev_start = sample_data
        result = kpis(sales, lines, start, end, prev_start)

        assert result['revenue_delta'] == pytest.approx(56.25, 0.1)
        assert result['count_delta'] == pytest.approx(25.0, 0.1)

    def test_kpis_with_refunds(self, sample_data):
        """Revenue after refunds."""
        sales, lines, start, end, prev_start = sample_data

        refunds = pd.DataFrame({
            'total': [50.0],
            'created_at': [start + timedelta(hours=1)]
        })

        result = kpis(sales, lines, start, end, prev_start, refunds)
        assert result['revenue'] == 450.0

    def test_kpis_no_sales(self):
        """KPIs with no sales return zeros."""
        now = datetime(2026, 1, 15)
        start, end, prev_start = period_bounds(7, now)

        sales = pd.DataFrame({
            'status': [],
            'total': [],
            'created_at': []
        })

        lines = pd.DataFrame({
            'created_at': [],
            'revenue': [],
            'margin': []
        })

        result = kpis(sales, lines, start, end, prev_start)
        assert result['revenue'] == 0
        assert result['count'] == 0
        assert result['revenue_delta'] is None


class TestLowStock:
    def test_low_stock_detection(self):
        """Products below minimum stock are flagged."""
        products = pd.DataFrame({
            'id': [1, 2, 3, 4],
            'name': ['Pan', 'Café', 'Leche', 'Huevos'],
            'stock': [5, 0, 10, 2],
            'min_stock': [10, 5, 5, 5],
            'track_stock': [1, 1, 1, 1],
            'active': [1, 1, 1, 1]
        })

        result = low_stock(products)
        assert len(result) == 3
        assert list(result['name']) == ['Café', 'Huevos', 'Pan']

    def test_low_stock_ignores_inactive(self):
        """Inactive products are not flagged."""
        products = pd.DataFrame({
            'id': [1, 2],
            'name': ['Active', 'Inactive'],
            'stock': [0, 0],
            'min_stock': [5, 5],
            'track_stock': [1, 1],
            'active': [1, 0]
        })

        result = low_stock(products)
        assert len(result) == 1
        assert result.iloc[0]['name'] == 'Active'

    def test_low_stock_ignores_untracked(self):
        """Products with track_stock=0 are ignored."""
        products = pd.DataFrame({
            'id': [1, 2],
            'name': ['Tracked', 'Untracked'],
            'stock': [0, 0],
            'min_stock': [5, 5],
            'track_stock': [1, 0],
            'active': [1, 1]
        })

        result = low_stock(products)
        assert len(result) == 1


class TestReorderSuggestions:
    def test_reorder_suggestions_basic(self):
        """Suggest quantities based on lead time and demand."""
        now = datetime(2026, 1, 15)

        products = pd.DataFrame({
            'id': [1],
            'sku': ['BREAD'],
            'name': ['Pan integral'],
            'stock': [10],
            'cost': [2.0],
            'min_stock': [5],
            'track_stock': [1],
            'active': [1]
        })

        lines = pd.DataFrame({
            'product_id': [1] * 150,
            'quantity': [1] * 150,
            'created_at': [
                now - timedelta(days=30-i//5) for i in range(150)
            ]
        })

        result = reorder_suggestions(products, lines, lead_days=14, window_days=30, now=now)

        assert len(result) == 1
        assert result.iloc[0]['suggested_qty'] == 65
        assert result.iloc[0]['daily_demand'] == 5.0
        assert result.iloc[0]['estimated_cost'] == 130.0

    def test_reorder_suggestions_no_demand(self):
        """Products with no sales don't get reorder suggestions."""
        products = pd.DataFrame({
            'id': [1],
            'sku': ['RARE'],
            'name': ['Raro'],
            'stock': [100],
            'cost': [10.0],
            'min_stock': [5],
            'track_stock': [1],
            'active': [1]
        })

        lines = pd.DataFrame({
            'product_id': [],
            'quantity': [],
            'created_at': []
        })

        result = reorder_suggestions(products, lines)
        assert len(result) == 0

    def test_reorder_suggestions_sufficient_stock(self):
        """Products with sufficient stock don't get suggestions."""
        now = datetime(2026, 1, 15)

        products = pd.DataFrame({
            'id': [1],
            'sku': ['ITEM'],
            'name': ['Item'],
            'stock': [1000],
            'cost': [5.0],
            'min_stock': [10],
            'track_stock': [1],
            'active': [1]
        })

        lines = pd.DataFrame({
            'product_id': [1] * 30,
            'quantity': [1] * 30,
            'created_at': [now - timedelta(days=30-i) for i in range(30)]
        })

        result = reorder_suggestions(products, lines)
        assert len(result) == 0


class TestInactiveCustomers:
    def test_inactive_customers_detection(self):
        """Identify customers with no purchase in 60+ days."""
        now = datetime(2026, 1, 15)

        customers = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Juan', 'María', 'Pedro'],
            'email': ['juan@ex.com', 'maria@ex.com', 'pedro@ex.com'],
            'phone': ['600', '601', '602']
        })

        sales = pd.DataFrame({
            'customer_id': [1, 1, 2, 3],
            'status': ['completada', 'completada', 'completada', 'completada'],
            'total': [50, 50, 100, 100],
            'created_at': [
                now - timedelta(days=10),
                now - timedelta(days=5),
                now - timedelta(days=70),
                now - timedelta(days=100)
            ]
        })

        result = inactive_customers(customers, sales, days=60, now=now)

        assert len(result) == 2
        assert set(result['name']) == {'María', 'Pedro'}

    def test_inactive_customers_no_purchases(self):
        """Customers with no purchases ever are not returned."""
        customers = pd.DataFrame({
            'id': [1, 2],
            'name': ['Alice', 'Bob'],
            'email': ['a@ex.com', 'b@ex.com'],
            'phone': ['600', '601']
        })

        sales = pd.DataFrame({
            'customer_id': [],
            'status': [],
            'total': [],
            'created_at': []
        })

        result = inactive_customers(customers, sales)
        assert len(result) == 0

    def test_inactive_customers_sorted_by_value(self):
        """Results are sorted by lifetime value (highest first)."""
        now = datetime(2026, 1, 15)

        customers = pd.DataFrame({
            'id': [1, 2],
            'name': ['VIP', 'Regular'],
            'email': ['vip@ex.com', 'reg@ex.com'],
            'phone': ['600', '601']
        })

        sales = pd.DataFrame({
            'customer_id': [1, 1, 2],
            'status': ['completada'] * 3,
            'total': [1000, 500, 100],
            'created_at': [
                now - timedelta(days=80),
                now - timedelta(days=80),
                now - timedelta(days=80)
            ]
        })

        result = inactive_customers(customers, sales, days=60, now=now)
        assert result.iloc[0]['name'] == 'VIP'


class TestFollowupMessage:
    def test_followup_message_format(self):
        """Message is personalized with customer name and business."""
        msg = followup_message('Juan Pérez', 'Panadería Sol')

        assert 'Juan' in msg
        assert 'Panadería Sol' in msg
        assert '10 %' in msg
        assert msg.startswith('Hola Juan')

    def test_followup_message_single_name(self):
        """Works with single-word names."""
        msg = followup_message('Carlos', 'Bar Azul')
        assert msg.startswith('Hola Carlos')

    def test_followup_message_empty_name(self):
        """Handles empty names gracefully."""
        msg = followup_message('', 'Tienda X')
        assert 'Hola' in msg
        assert 'Tienda X' in msg


class TestCustomerRanking:
    def test_customer_ranking_by_lifetime_value(self):
        """Customers ranked by total purchases."""
        customers = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Juan', 'María', 'Pedro']
        })

        sales = pd.DataFrame({
            'customer_id': [1, 1, 2, 3, 3, 3],
            'id': [1, 2, 3, 4, 5, 6],  # Required for agg
            'status': ['completada'] * 6,
            'total': [100, 100, 500, 50, 50, 50],
            'created_at': ['2026-01-01'] * 6
        })

        result = customer_ranking(customers, sales)

        # Maria (E500) should be first
        assert result.iloc[0]['name'] == 'María'
        assert result.iloc[0]['purchases'] == 1
        assert result.iloc[0]['lifetime_value'] == 500.0

    def test_customer_ranking_no_purchases(self):
        """Customers with no purchases get zero values."""
        customers = pd.DataFrame({
            'id': [1, 2],
            'name': ['With Sales', 'No Sales']
        })

        sales = pd.DataFrame({
            'customer_id': [1],
            'id': [1],
            'status': ['completada'],
            'total': [100],
            'created_at': ['2026-01-01']
        })

        result = customer_ranking(customers, sales)

        assert result[result['name'] == 'No Sales'].iloc[0]['purchases'] == 0
        assert result[result['name'] == 'No Sales'].iloc[0]['lifetime_value'] == 0.0


class TestInsights:
    def test_insights_no_sales(self):
        """Empty insights when no sales."""
        products = pd.DataFrame({'id': [], 'name': [], 'price': [], 'cost': [], 'active': []})
        lines = pd.DataFrame({'product_id': [], 'name': [], 'revenue': [], 'margin': [], 'created_at': []})

        result = insights(products, lines)
        assert len(result) == 1
        assert result[0][0] == 'info'

    def test_insights_top_product(self):
        """Identify best-selling product."""
        now = datetime(2026, 1, 15)

        products = pd.DataFrame({
            'id': [1, 2],
            'name': ['Pan', 'Café'],
            'price': [2, 5],
            'cost': [1, 2],
            'active': [1, 1]
        })

        lines = pd.DataFrame({
            'product_id': [1, 1, 1, 2],
            'name': ['Pan', 'Pan', 'Pan', 'Café'],
            'revenue': [100, 100, 100, 50],
            'margin': [50, 50, 50, 25],
            'created_at': [now, now, now, now]
        })

        result = insights(products, lines)

        star = [r for r in result if 'estrella' in r[1]][0]
        assert 'Pan' in star[1]

    def test_insights_concentration_warning(self):
        """Warn if one product >50% of revenue."""
        now = datetime(2026, 1, 15)

        products = pd.DataFrame({
            'id': [1, 2],
            'name': ['Cash Cow', 'Other'],
            'price': [10, 1],
            'cost': [5, 0.5],
            'active': [1, 1]
        })

        lines = pd.DataFrame({
            'product_id': [1, 1, 2],
            'name': ['Cash Cow', 'Cash Cow', 'Other'],
            'revenue': [1000, 500, 100],
            'margin': [2500, 2500, 50],
            'created_at': [now, now, now]
        })

        result = insights(products, lines)

        warning = [r for r in result if r[0] == 'warning' and 'dependen' in r[1]]
        assert len(warning) > 0

    def test_insights_low_margin_products(self):
        """Warn about products with <25% margin."""
        now = datetime(2026, 1, 15)

        products = pd.DataFrame({
            'id': [1, 2],
            'name': ['Low Margin', 'Good Margin'],
            'price': [100, 100],
            'cost': [90, 25],
            'active': [1, 1]
        })

        lines = pd.DataFrame({
            'product_id': [1],
            'name': ['Low Margin'],
            'revenue': [100],
            'margin': [10],
            'created_at': [now]
        })

        result = insights(products, lines)

        margin_warnings = [r for r in result if 'margen' in r[1].lower()]
        assert any('Low Margin' in r[1] for r in margin_warnings)

    def test_insights_best_day_of_week(self):
        """Identify best performing day."""
        products = pd.DataFrame({'id': [1], 'name': ['Item'], 'price': [10], 'cost': [5], 'active': [1]})

        lines = pd.DataFrame({
            'product_id': [1] * 10,
            'name': ['Item'] * 10,
            'revenue': [50] * 3 + [100] * 3 + [50] * 4,
            'margin': [25] * 10,
            'created_at': [
                datetime(2026, 1, 13, 12),
                datetime(2026, 1, 13, 14),
                datetime(2026, 1, 13, 16),
                datetime(2026, 1, 14, 10),
                datetime(2026, 1, 14, 12),
                datetime(2026, 1, 14, 14),
                datetime(2026, 1, 15, 10),
                datetime(2026, 1, 15, 12),
                datetime(2026, 1, 15, 14),
                datetime(2026, 1, 15, 16),
            ]
        })

        result = insights(products, lines)

        day_insight = [r for r in result if 'mejor día' in r[1]][0]
        assert 'miércoles' in day_insight[1]
