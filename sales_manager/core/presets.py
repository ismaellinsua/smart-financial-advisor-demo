"""Business presets: each one adapts vocabulary, taxes, categories and a sample catalog."""

PRESETS = {
    "retail": {
        "suppliers": [("Textiles Norte S.L.", "pedidos@textilesnorte.example.com", "B11111111"),
                      ("Complementos Sur", "ventas@complementossur.example.com", "B22222222")],
        "fixed_costs": [("Alquiler", "Alquiler del local", 900, 1), ("Nóminas", "Nómina dependienta", 1650, 28),
                        ("Suministros", "Luz e internet", 140, 10), ("Seguros", "Seguro del local", 45, 5)],
        "promotions": [
            {"name": "3x2 en accesorios", "kind": "nxm", "buy": 3, "pay": 2, "scope": "categoria",
             "target": "Accesorios"},
            {"name": "Viernes de moda −10 %", "kind": "porcentaje", "value": 10, "scope": "categoria",
             "target": "Ropa", "days": "4"},
        ],
        "label": "Pequeño comercio / Tienda",
        "demo_name": "Moda Lúa",
        "description": "Ropa, regalos, alimentación, ferretería… Productos con control de stock.",
        "item_label": "Producto",
        "item_label_plural": "Productos",
        "tax_rate": 21.0,
        "target_margin": 45,  # usual gross margin on price, for price suggestions
        "categories": ["Ropa", "Calzado", "Accesorios", "Hogar"],
        "track_stock": True,
        "catalog": [
            # sku, name, category, price, cost, stock, min_stock
            ("CAM-001", "Camisa de lino", "Ropa", 39.90, 16.00, 25, 8),
            ("PAN-002", "Pantalón chino", "Ropa", 49.90, 21.00, 18, 6),
            ("ZAP-003", "Zapatilla urbana", "Calzado", 79.00, 35.00, 12, 5),
            ("BOL-004", "Bolso de piel", "Accesorios", 120.00, 52.00, 2, 3),
            ("CIN-005", "Cinturón clásico", "Accesorios", 24.50, 8.50, 30, 10),
            ("VEL-006", "Vela aromática", "Hogar", 14.90, 4.20, 40, 12),
        ],
    },
    "restaurant": {
        "suppliers": [("Distribuciones Gastro S.L.", "pedidos@gastro.example.com", "B33333333"),
                      ("Bodegas del Valle", "comercial@bodegasvalle.example.com", "B44444444")],
        "fixed_costs": [("Alquiler", "Alquiler del local", 950, 1), ("Nóminas", "Nóminas de sala y cocina", 3200, 28),
                        ("Suministros", "Luz, agua y gas", 380, 10), ("Seguros", "Seguro de responsabilidad", 60, 5)],
        # A café serves many small tickets a day.
        "demo_sales_per_day": (10, 20),
        "promotions": [
            {"name": "Happy hour bebidas −30 %", "kind": "porcentaje", "value": 30, "scope": "categoria",
             "target": "Bebidas", "start_time": "18:00", "end_time": "20:00"},
            {"name": "2x1 en postres los martes", "kind": "nxm", "buy": 2, "pay": 1, "scope": "categoria",
             "target": "Postres", "days": "1"},
        ],
        "label": "Restaurante / Cafetería",
        "demo_name": "Café Aurora",
        "description": "Bares, cafeterías y restaurantes. Carta de platos y bebidas.",
        "item_label": "Plato",
        "tables": {"Sala": [(f"Mesa {n}", 4) for n in range(1, 9)],
                   "Terraza": [(f"Terraza {n}", 2) for n in range(1, 5)]},
        # Table reservations: several can share the same time.
        "agenda": {"title": "Reservas", "single": False, "duration": 90,
                   "hours": [13, 13.5, 14, 14.5, 20.5, 21, 21.5, 22]},
        "item_label_plural": "Carta",
        "tax_rate": 10.0,
        "target_margin": 70,  # usual gross margin on price, for price suggestions
        "categories": ["Entrantes", "Principales", "Postres", "Bebidas"],
        "track_stock": True,
        "catalog": [
            ("ENT-001", "Croquetas caseras (6 uds)", "Entrantes", 8.50, 2.40, 60, 20),
            ("ENT-002", "Ensalada mediterránea", "Entrantes", 9.90, 3.10, 40, 10),
            ("PRI-003", "Arroz del día", "Principales", 16.50, 5.20, 35, 10),
            ("PRI-004", "Solomillo a la brasa", "Principales", 22.00, 9.80, 6, 8),
            ("POS-005", "Tarta de queso", "Postres", 6.50, 1.70, 25, 8),
            ("BEB-006", "Café especialidad", "Bebidas", 2.20, 0.45, 200, 50),
            ("BEB-007", "Vino de la casa (copa)", "Bebidas", 3.80, 1.10, 90, 24),
        ],
    },
    "services": {
        "suppliers": [("Papelería Central", "pedidos@papeleria.example.com", "B55555555")],
        "fixed_costs": [("Impuestos y tasas", "Cuota de autónomos", 300, 28),
                        ("Alquiler", "Puesto en coworking", 220, 1),
                        ("Software y servicios", "Software de gestión y correo", 45, 3)],
        "promotions": [
            {"name": "Formación −10 %", "kind": "porcentaje", "value": 10, "scope": "categoria",
             "target": "Formación"},
        ],
        "label": "Autónomo / Servicios profesionales",
        "demo_name": "Ana García · Consultora",
        "description": "Consultoría, formación, reformas, estética… Servicios sin stock.",
        "item_label": "Servicio",
        # One person's diary: appointments cannot overlap.
        "agenda": {"title": "Agenda", "single": True, "duration": 60,
                   "hours": [9, 10, 11, 12, 16, 17, 18]},
        "item_label_plural": "Servicios",
        "tax_rate": 21.0,
        "target_margin": 60,  # usual gross margin on price, for price suggestions
        "categories": ["Consultoría", "Formación", "Soporte", "Proyectos"],
        "track_stock": False,
        # A freelancer closes far fewer, larger sales than a shop: keep the demo figures believable.
        "demo_sales_per_day": (0, 1),
        "demo_max_quantity": 1,
        "demo_max_items": 1,
        "catalog": [
            ("CON-001", "Hora de consultoría", "Consultoría", 75.00, 30.00, 0, 0),
            ("CON-002", "Auditoría inicial", "Consultoría", 450.00, 180.00, 0, 0),
            ("FOR-003", "Taller in-company (4 h)", "Formación", 600.00, 220.00, 0, 0),
            ("SOP-004", "Plan de soporte mensual", "Soporte", 199.00, 70.00, 0, 0),
            ("PRO-005", "Proyecto web básico", "Proyectos", 1800.00, 900.00, 0, 0),
        ],
    },
    "ecommerce": {
        "suppliers": [("TechDistribución S.A.", "b2b@techdistribucion.example.com", "A66666666"),
                      ("Embalajes Express", "ventas@embalajes.example.com", "B77777777")],
        "fixed_costs": [("Alquiler", "Almacén", 450, 1), ("Software y servicios", "Plataforma de tienda online", 79, 3),
                        ("Marketing", "Campañas de anuncios", 300, 15), ("Transporte", "Tarifa plana de envíos", 180, 20)],
        "promotions": [
            {"name": "3x2 en fundas y cargadores", "kind": "nxm", "buy": 3, "pay": 2, "scope": "categoria",
             "target": "Accesorios"},
        ],
        "label": "Tienda online / E-commerce",
        "demo_name": "TecnoShop Online",
        "description": "Venta por internet con envíos. Catálogo con control de stock.",
        "item_label": "Artículo",
        "item_label_plural": "Catálogo",
        "tax_rate": 21.0,
        "target_margin": 40,  # usual gross margin on price, for price suggestions
        "categories": ["Electrónica", "Accesorios", "Packs", "Envíos"],
        "track_stock": True,
        "catalog": [
            ("ELE-001", "Auriculares inalámbricos", "Electrónica", 59.90, 24.00, 35, 10),
            ("ELE-002", "Altavoz portátil", "Electrónica", 89.00, 38.00, 4, 6),
            ("ACC-003", "Funda protectora", "Accesorios", 15.90, 3.20, 80, 20),
            ("ACC-004", "Cargador rápido USB-C", "Accesorios", 24.90, 7.80, 50, 15),
            ("PAC-005", "Pack home office", "Packs", 149.00, 72.00, 8, 4),
            # Optional 8th field overrides the preset's track_stock.
            ("ENV-006", "Envío urgente 24 h", "Envíos", 6.90, 4.50, 0, 0, False),
        ],
    },
}

PAYMENT_METHODS = ["Tarjeta", "Efectivo", "Transferencia", "Bizum", "Otro"]

CURRENCIES = {"EUR": "€", "USD": "$", "MXN": "$", "COP": "$", "ARS": "$", "CLP": "$", "PEN": "S/", "GBP": "£"}

DEFAULT_SETTINGS = {
    "business_name": "Mi Negocio",
    "business_type": "retail",
    "tax_id": "",
    "address": "",
    "email": "",
    "phone": "",
    "currency": "EUR",
    "timezone": "Europe/Madrid",
    # Prices are entered with VAT included, as on the menu or the label.
    "prices_include_tax": "si",
    # "si" while the data is a demonstration: it may be wiped. Real data is kept by law.
    "demo_mode": "no",
    # "si" once the administrator turns on the chained billing register (VERI*FACTU); it is never turned off.
    "verifactu": "no",
    "tax_rate": "21.0",
    "invoice_prefix": "VTA",
    "accent_color": "#1F4E79",
    "inactive_days": "30",
    "reorder_lead_days": "14",
    "receipt_footer": "Gracias por su compra.",
    # Paper the till prints tickets on: a4 (any printer), 80 or 58 (thermal ticket printers, roll width in mm).
    "receipt_paper": "a4",
    # Emails to the business's address, when the operator has set up sending (see README): opt-in.
    "email_weekly": "no",
    "email_alerts": "no",
    "invoice_series": "FAC",
    "refund_prefix": "DEV",
    "agenda_enabled": "auto",
    # Online booking (public page …/?reservar): off until the business opens it from the Agenda.
    "booking_online": "no",
    "booking_hours": '{"0": "09:00-14:00, 16:00-20:00", "1": "09:00-14:00, 16:00-20:00", '
                     '"2": "09:00-14:00, 16:00-20:00", "3": "09:00-14:00, 16:00-20:00", '
                     '"4": "09:00-14:00, 16:00-20:00", "5": "10:00-14:00"}',
    "booking_closed": "",
    "booking_services": "",
    "booking_step": "30",
    "booking_duration": "",
    "booking_days": "30",
    "booking_notice_hours": "2",
    "booking_capacity": "30",
    "booking_max_party": "10",
    "booking_hourly_limit": "20",
    "tables_enabled": "auto",
    "opening_float": "150",
    # Idle time before a device asks to sign in again: a work shift, not a whole day (shared tills).
    "session_minutes": "480",
    # Highest manual discount (%) staff may give without a manager's authorisation.
    "max_discount_staff": "10",
    "loyalty_enabled": "si",
    "points_per_euro": "1",
    "point_value": "0.01",
    "min_redeem_points": "100",
}
