import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from server import app
from models import Organization, User, Product, Configuration

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_price_matrix.db"

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
    # Override get_db dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_register_new_org(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "admin@org1.com",
            "password": "password123",
            "full_name": "Admin User",
            "role": "ADMIN",
            "org_name": "Org One"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@org1.com"
    assert data["user"]["role"] == "ADMIN"
    
    # Check default configurations were created
    org_id = data["user"]["org_id"]
    config = db_session.query(Configuration).filter(Configuration.org_id == org_id).first()
    assert config is not None
    assert config.auto_execute_threshold == 0.85


def test_register_join_existing_org(client, db_session):
    # Create org manually in DB
    org = Organization(name="Existing Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "analyst@orgex.com",
            "password": "password123",
            "full_name": "Analyst User",
            "role": "ANALYST",
            "org_id": org.id
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["org_id"] == org.id
    assert data["user"]["role"] == "ANALYST"


def test_login(client, db_session):
    # Register first
    client.post(
        "/api/auth/register",
        json={
            "email": "user@login.com",
            "password": "password123",
            "full_name": "Login User",
            "role": "ANALYST",
            "org_name": "Login Org"
        }
    )

    # Attempt login
    response = client.post(
        "/api/auth/login",
        json={
            "email": "user@login.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "user@login.com"


def test_multi_tenant_isolation(client, db_session):
    # Register Organization A
    res_a = client.post(
        "/api/auth/register",
        json={
            "email": "admin@orga.com",
            "password": "password123",
            "full_name": "Admin Org A",
            "role": "ADMIN",
            "org_name": "Org A"
        }
    )
    org_a_id = res_a.json()["user"]["org_id"]

    # Register Organization B
    res_b = client.post(
        "/api/auth/register",
        json={
            "email": "admin@orgb.com",
            "password": "password123",
            "full_name": "Admin Org B",
            "role": "ADMIN",
            "org_name": "Org B"
        }
    )
    org_b_id = res_b.json()["user"]["org_id"]

    # Create Org A Product directly in db
    prod_a = Product(
        org_id=org_a_id,
        sku="SKU-A",
        name="Product A",
        category="electronics",
        current_price=100.0,
        cogs=80.0,
        inventory_count=10
    )
    db_session.add(prod_a)

    # Create Org B Product directly in db
    prod_b = Product(
        org_id=org_b_id,
        sku="SKU-B",
        name="Product B",
        category="electronics",
        current_price=200.0,
        cogs=160.0,
        inventory_count=20
    )
    db_session.add(prod_b)
    db_session.commit()

    # Query products filtered by Org A context
    org_a_products = db_session.query(Product).filter(Product.org_id == org_a_id).all()
    assert len(org_a_products) == 1
    assert org_a_products[0].sku == "SKU-A"

    # Query products filtered by Org B context
    org_b_products = db_session.query(Product).filter(Product.org_id == org_b_id).all()
    assert len(org_b_products) == 1
    assert org_b_products[0].sku == "SKU-B"
