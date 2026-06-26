import sys
import os
import random
from decimal import Decimal
from datetime import datetime, timedelta

# Ensure project root directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal, engine, Base
from backend.models import (
    Organization,
    User,
    Configuration,
    Product,
    CompetitorPrice,
    DemandSignal,
)
from backend.auth import get_password_hash

# Sample Products list
SEED_PRODUCTS = [
    # Electronics
    {"sku": "ELE-SONY-XM5", "name": "Sony WH-1000XM5 Wireless Headphones", "category": "electronics", "price": 349.99, "cogs": 240.00, "inventory": 45, "margin_threshold": 0.15},
    {"sku": "ELE-APP-APP2", "name": "Apple AirPods Pro (2nd Gen)", "category": "electronics", "price": 249.00, "cogs": 170.00, "inventory": 6, "margin_threshold": 0.15}, # low inventory
    {"sku": "ELE-SAM-S24U", "name": "Samsung Galaxy S24 Ultra 256GB", "category": "electronics", "price": 1299.99, "cogs": 950.00, "inventory": 18, "margin_threshold": 0.12},
    {"sku": "ELE-DEL-XPS13", "name": "Dell XPS 13 Laptop Intel Core i7", "category": "electronics", "price": 1099.00, "cogs": 800.00, "inventory": 30, "margin_threshold": 0.15},
    
    # Home Goods
    {"sku": "HOM-ERG-CHR1", "name": "Ergonomic Mesh Office Desk Chair", "category": "home goods", "price": 189.99, "cogs": 110.00, "inventory": 160, "margin_threshold": 0.20}, # overstocked
    {"sku": "HOM-DYSON-V15", "name": "Dyson V15 Detect Cordless Vacuum", "category": "home goods", "price": 749.99, "cogs": 520.00, "inventory": 25, "margin_threshold": 0.18},
    {"sku": "HOM-INS-POT6", "name": "Instant Pot Duo Plus 9-in-1 6-Quart", "category": "home goods", "price": 129.99, "cogs": 85.00, "inventory": 85, "margin_threshold": 0.20},
    {"sku": "HOM-NES-VERT", "name": "Nespresso Vertuo Next Coffee Machine", "category": "home goods", "price": 199.00, "cogs": 130.00, "inventory": 120, "margin_threshold": 0.20},
    
    # Apparel
    {"sku": "APP-LEV-501M", "name": "Levi's Men's 501 Original Fit Jeans", "category": "apparel", "price": 79.50, "cogs": 35.00, "inventory": 70, "margin_threshold": 0.25},
    {"sku": "APP-NIK-AIRMAX", "name": "Nike Air Max 270 Sneakers", "category": "apparel", "price": 160.00, "cogs": 85.00, "inventory": 12, "margin_threshold": 0.25},
    {"sku": "APP-PAT-TORR", "name": "Patagonia Torrentshell 3L Rain Jacket", "category": "apparel", "price": 149.00, "cogs": 70.00, "inventory": 50, "margin_threshold": 0.25},
    {"sku": "APP-TNF-NUPTSE", "name": "The North Face 1996 Retro Nuptse Down Jacket", "category": "apparel", "price": 330.00, "cogs": 170.00, "inventory": 4, "margin_threshold": 0.25} # low inventory
]

COMPETITOR_NAMES = ["ShopMax", "AuraRetail", "DirectStore", "ZenithBuy"]

def seed_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 1. Check if organization already exists
    org = db.query(Organization).first()
    if not org:
        print("Seeding default Organization 'Klypup Retail'...")
        org = Organization(name="Klypup Retail")
        db.add(org)
        db.flush()
        
        # Create configuration
        config = Configuration(
            org_id=org.id,
            auto_execute_threshold=0.85,
            category_margin_floors={
                "electronics": 0.10,
                "home goods": 0.15,
                "apparel": 0.20
            }
        )
        db.add(config)
    else:
        print(f"Organization '{org.name}' already exists.")

    # 2. Check if users exist
    admin_user = db.query(User).filter(User.email == "admin@klypup.com").first()
    if not admin_user:
        print("Seeding admin user (admin@klypup.com)...")
        admin_user = User(
            org_id=org.id,
            email="admin@klypup.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Klypup Admin",
            role="ADMIN"
        )
        db.add(admin_user)

    analyst_user = db.query(User).filter(User.email == "analyst@klypup.com").first()
    if not analyst_user:
        print("Seeding analyst user (analyst@klypup.com)...")
        analyst_user = User(
            org_id=org.id,
            email="analyst@klypup.com",
            hashed_password=get_password_hash("analyst123"),
            full_name="Pricing Analyst One",
            role="ANALYST"
        )
        db.add(analyst_user)

    db.commit()

    # 3. Check if products exist
    products = db.query(Product).filter(Product.org_id == org.id).all()
    if not products:
        print("Seeding product catalog...")
        for p in SEED_PRODUCTS:
            product = Product(
                org_id=org.id,
                sku=p["sku"],
                name=p["name"],
                category=p["category"],
                current_price=Decimal(str(p["price"])),
                cogs=Decimal(str(p["cogs"])),
                inventory_count=p["inventory"],
                margin_threshold=p["margin_threshold"]
            )
            db.add(product)
        db.commit()
        products = db.query(Product).filter(Product.org_id == org.id).all()

    # 4. Generate/Update Competitor Prices & Demand Signals
    print("Generating simulation metrics (Competitor prices, demand signals)...")
    for product in products:
        db.query(CompetitorPrice).filter(CompetitorPrice.product_id == product.id).delete()
        
        num_comps = random.randint(2, 3)
        comps = random.sample(COMPETITOR_NAMES, num_comps)
        
        for comp_name in comps:
            variation = random.uniform(-0.15, 0.05) if product.sku == "ELE-SONY-XM5" else random.uniform(-0.08, 0.08)
            comp_price = product.current_price * Decimal(str(1 + variation))
            comp_price = Decimal(f"{comp_price:.2f}")
            
            competitor_entry = CompetitorPrice(
                product_id=product.id,
                competitor_name=comp_name,
                price=comp_price,
                fetched_at=datetime.utcnow() - timedelta(minutes=random.randint(5, 60))
            )
            db.add(competitor_entry)

        # Update or create demand signals
        demand = db.query(DemandSignal).filter(DemandSignal.product_id == product.id).first()
        if not demand:
            demand = DemandSignal(product_id=product.id)
            db.add(demand)
        
        if product.sku == "ELE-SONY-XM5":
            demand.trend_score = 1.6
            demand.velocity_sales_30d = 85
            demand.seasonal_multiplier = 1.2
        elif product.sku == "HOM-ERG-CHR1":
            demand.trend_score = 0.65
            demand.velocity_sales_30d = 12
            demand.seasonal_multiplier = 0.95
        else:
            demand.trend_score = round(random.uniform(0.7, 1.4), 2)
            demand.velocity_sales_30d = random.randint(10, 60)
            demand.seasonal_multiplier = round(random.uniform(0.9, 1.3), 2)

    db.commit()
    print("Database seeding and simulation update completed successfully.")
    db.close()

if __name__ == "__main__":
    seed_db()
