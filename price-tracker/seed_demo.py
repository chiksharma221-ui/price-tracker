"""Seed the local JSON store with SIMULATED listings so the dashboard and the
report can be demoed without live scraping.

Every point is tagged source="simulated", product names say "(demo)", and
the report generator labels output from this data as simulated. Never present
these numbers as real findings.

    python seed_demo.py            # adds 24 demo listings + a demo sale window
"""
from price_tracker.analysis.simulate import simulate_market
from price_tracker.config import settings
from price_tracker.models import Product
from price_tracker.storage import JsonStore

store = JsonStore(settings.json_store_path)
listings, sale = simulate_market(n=24, seed=21)
sale.name = "Demo Festive Sale"
store.add_sale_event(sale)

for i, listing in enumerate(listings):
    product = Product(url=f"https://demo.local/product/{i + 1}", name=f"{listing.name} (demo)",
                      category=listing.category)
    store.add_product(product)
    for point in listing.history:
        store.append_price(product.id, point)
print(f"Seeded {len(listings)} simulated listings and sale window '{sale.name}'.")
