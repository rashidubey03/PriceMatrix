import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.server import app
from backend.models import Organization, User, Product, Configuration

# Testing DB setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_price_matrix_catalog.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    # Clear all data before each test to ensure a clean state
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def tokens(client):
    # Org A Signup
    res_a = client.post(
        "/api/auth/register",
        json={
            "email": "admin@orga.com",
            "password": "password123",
            "full_name": "Admin A",
            "role": "ADMIN",
            "org_name": "Org A"
        }
    )
    assert res_a.status_code == 201, f"Failed to register Admin A: {res_a.text}"
    token_a = res_a.json()["access_token"]

    # Org B Signup
    res_b = client.post(
        "/api/auth/register",
        json={
            "email": "admin@orgb.com",
            "password": "password123",
            "full_name": "Admin B",
            "role": "ADMIN",
            "org_name": "Org B"
        }
    )
    assert res_b.status_code == 201, f"Failed to register Admin B: {res_b.text}"
    token_b = res_b.json()["access_token"]

    # Org A Analyst Signup
    res_a_analyst = client.post(
        "/api/auth/register",
        json={
            "email": "analyst@orga.com",
            "password": "password123",
            "full_name": "Analyst A",
            "role": "ANALYST",
            "org_id": res_a.json()["user"]["org_id"]
        }
    )
    assert res_a_analyst.status_code == 201, f"Failed to register Analyst A: {res_a_analyst.text}"
    token_a_analyst = res_a_analyst.json()["access_token"]

    return {
        "admin_a": token_a,
        "admin_b": token_b,
        "analyst_a": token_a_analyst
    }


def test_create_and_read_product(client, tokens):
    headers_a = {"Authorization": f"Bearer {tokens['admin_a']}"}
    
    # 1. Create product in Org A
    response = client.post(
        "/api/products",
        headers=headers_a,
        json={
            "sku": "ELE-TEST-1",
            "name": "Test Electronics SKU",
            "category": "electronics",
            "current_price": 299.99,
            "cogs": 200.00,
            "inventory_count": 50,
            "margin_threshold": 0.15
        }
    )
    assert response.status_code == 201
    data = response.json()
    product_id = data["id"]
    assert data["sku"] == "ELE-TEST-1"
    assert data["name"] == "Test Electronics SKU"

    # 2. Query product from User A (Admin)
    get_res = client.get(f"/api/products/{product_id}", headers=headers_a)
    assert get_res.status_code == 200
    assert get_res.json()["sku"] == "ELE-TEST-1"

    # 3. Query product from User B (Org B) -> should fail (404)
    headers_b = {"Authorization": f"Bearer {tokens['admin_b']}"}
    get_res_b = client.get(f"/api/products/{product_id}", headers=headers_b)
    assert get_res_b.status_code == 404


def test_analyst_cannot_create_or_delete_product(client, tokens):
    headers_analyst = {"Authorization": f"Bearer {tokens['analyst_a']}"}
    
    # Analyst tries to create
    response = client.post(
        "/api/products",
        headers=headers_analyst,
        json={
            "sku": "ELE-TEST-2",
            "name": "Should Fail",
            "category": "electronics",
            "current_price": 100.0,
            "cogs": 50.0,
            "inventory_count": 10
        }
    )
    assert response.status_code == 403

    # Create product using admin
    headers_admin = {"Authorization": f"Bearer {tokens['admin_a']}"}
    create_res = client.post(
        "/api/products",
        headers=headers_admin,
        json={
            "sku": "ELE-TEST-3",
            "name": "Test Delete",
            "category": "electronics",
            "current_price": 100.0,
            "cogs": 50.0,
            "inventory_count": 10
        }
    )
    prod_id = create_res.json()["id"]

    # Analyst tries to delete
    del_res = client.delete(f"/api/products/{prod_id}", headers=headers_analyst)
    assert del_res.status_code == 403


def test_filtering_and_sorting(client, tokens):
    headers = {"Authorization": f"Bearer {tokens['admin_a']}"}
    
    # Create products with different fields
    client.post(
        "/api/products",
        headers=headers,
        json={"sku": "FILTER-1", "name": "Apparel Jacket", "category": "apparel", "current_price": 50.00, "cogs": 30.0, "inventory_count": 5} # low stock
    )
    client.post(
        "/api/products",
        headers=headers,
        json={"sku": "FILTER-2", "name": "Apparel Jeans", "category": "apparel", "current_price": 80.00, "cogs": 40.0, "inventory_count": 120} # overstock
    )
    client.post(
        "/api/products",
        headers=headers,
        json={"sku": "FILTER-3", "name": "Office Desk", "category": "home goods", "current_price": 150.00, "cogs": 100.0, "inventory_count": 50} # healthy
    )

    # 1. Filter by category
    res = client.get("/api/products?category=apparel", headers=headers)
    assert res.status_code == 200
    products = res.json()
    assert len(products) == 2
    assert all(p["category"] == "apparel" for p in products)

    # 2. Filter by stock level
    res_low = client.get("/api/products?stock_status=critically_low", headers=headers)
    assert len(res_low.json()) == 1
    assert res_low.json()[0]["sku"] == "FILTER-1"

    res_over = client.get("/api/products?stock_status=overstocked", headers=headers)
    assert len(res_over.json()) == 1
    assert res_over.json()[0]["sku"] == "FILTER-2"

    # 3. Search
    res_search = client.get("/api/products?search=Jeans", headers=headers)
    assert len(res_search.json()) == 1
    assert res_search.json()[0]["sku"] == "FILTER-2"

    # 4. Sorting
    res_sort = client.get("/api/products?sort_by=current_price&sort_order=desc", headers=headers)
    prices = [float(p["current_price"]) for p in res_sort.json() if "FILTER-" in p["sku"]]
    assert prices == sorted(prices, reverse=True)
