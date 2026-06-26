import pytest
import os
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from server import app
from models import Organization, User, Product, Recommendation, PriceChangeAudit, Configuration

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_price_matrix_hitl.db"

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
    # Clear tables
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
def test_data(client, db_session):
    # Org signup
    res = client.post(
        "/api/auth/register",
        json={
            "email": "admin@orga.com",
            "password": "password123",
            "full_name": "Admin A",
            "role": "ADMIN",
            "org_name": "Org A"
        }
    )
    token = res.json()["access_token"]
    org_id = res.json()["user"]["org_id"]

    # Product with cogs=100.0, margin_threshold=0.10 -> floor is 111.11. Current price=150.0
    prod = Product(
        org_id=org_id,
        sku="TEST-SKU",
        name="Test Item",
        category="electronics",
        current_price=Decimal("150.00"),
        cogs=Decimal("100.00"),
        inventory_count=50,
        margin_threshold=0.10
    )
    db_session.add(prod)
    db_session.commit()

    return {
        "token": token,
        "product": prod,
        "org_id": org_id
    }


def test_trigger_analysis_pending_vs_auto(client, test_data, db_session):
    headers = {"Authorization": f"Bearer {test_data['token']}"}
    prod = test_data["product"]

    # Let's set auto_execute_threshold to 0.90 so recommendations with confidence 0.80 remain PENDING
    config = db_session.query(Configuration).filter(Configuration.org_id == test_data["org_id"]).first()
    config.auto_execute_threshold = 0.90
    db_session.commit()

    # Trigger analysis
    res = client.post(f"/api/recommendations/analyze/{prod.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PENDING"
    assert float(data["recommended_price"]) == 150.0 # fallback rules match original

    # Now let's set auto_execute_threshold to 0.70 so it auto-executes
    config.auto_execute_threshold = 0.70
    db_session.commit()

    # Trigger analysis again
    res = client.post(f"/api/recommendations/analyze/{prod.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "AUTO_EXECUTED"

    # Verify price change and audit logs
    db_session.refresh(prod)
    assert float(prod.current_price) == 150.0
    audits = db_session.query(PriceChangeAudit).filter(PriceChangeAudit.product_id == prod.id).all()
    assert len(audits) == 1
    assert audits[0].change_type == "AUTO"


def test_approve_recommendation_flow(client, test_data, db_session):
    headers = {"Authorization": f"Bearer {test_data['token']}"}
    prod = test_data["product"]

    # 1. Create a pending recommendation manually
    rec = Recommendation(
        org_id=test_data["org_id"],
        product_id=prod.id,
        recommended_price=Decimal("160.00"),
        confidence_score=0.80,
        status="PENDING",
        agent_rationale={}
    )
    db_session.add(rec)
    db_session.commit()

    # 2. Approve it
    res = client.post(f"/api/recommendations/{rec.id}/approve", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "APPROVED"

    # 3. Check product current price updated
    db_session.refresh(prod)
    assert prod.current_price == Decimal("160.00")

    # 4. Check audit log is written
    audit = db_session.query(PriceChangeAudit).filter(PriceChangeAudit.recommendation_id == rec.id).first()
    assert audit is not None
    assert audit.change_type == "APPROVED"
    assert audit.new_price == Decimal("160.00")


def test_reject_recommendation_flow(client, test_data, db_session):
    headers = {"Authorization": f"Bearer {test_data['token']}"}
    prod = test_data["product"]

    rec = Recommendation(
        org_id=test_data["org_id"],
        product_id=prod.id,
        recommended_price=Decimal("160.00"),
        confidence_score=0.80,
        status="PENDING",
        agent_rationale={}
    )
    db_session.add(rec)
    db_session.commit()

    res = client.post(
        f"/api/recommendations/{rec.id}/reject",
        headers=headers,
        json={"reason": "Competitor pricing delta is too small."}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "REJECTED"
    assert res.json()["rejection_reason"] == "Competitor pricing delta is too small."

    # Price should NOT be updated
    db_session.refresh(prod)
    assert prod.current_price == Decimal("150.00")


def test_modify_recommendation_flow(client, test_data, db_session):
    headers = {"Authorization": f"Bearer {test_data['token']}"}
    prod = test_data["product"]

    rec = Recommendation(
        org_id=test_data["org_id"],
        product_id=prod.id,
        recommended_price=Decimal("160.00"),
        confidence_score=0.80,
        status="PENDING",
        agent_rationale={}
    )
    db_session.add(rec)
    db_session.commit()

    # 1. Modify with valid override (COGS=100.0, floor=111.11, target=120.00)
    res = client.post(
        f"/api/recommendations/{rec.id}/modify",
        headers=headers,
        json={"price": 120.00}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "APPROVED"
    
    db_session.refresh(prod)
    assert prod.current_price == Decimal("120.00")

    # Verify audit type
    audit = db_session.query(PriceChangeAudit).filter(PriceChangeAudit.recommendation_id == rec.id).first()
    assert audit.change_type == "MANUAL_OVERRIDE"

    # 2. Modify with invalid override (price=110.00 < floor 111.11)
    rec.status = "PENDING"
    db_session.commit()

    res_fail = client.post(
        f"/api/recommendations/{rec.id}/modify",
        headers=headers,
        json={"price": 110.00}
    )
    assert res_fail.status_code == 400
    assert "breaches margin floor" in res_fail.json()["detail"]


def test_storefront_sync_failure_rollback(client, test_data, db_session):
    headers = {"Authorization": f"Bearer {test_data['token']}"}
    prod = test_data["product"]

    rec = Recommendation(
        org_id=test_data["org_id"],
        product_id=prod.id,
        recommended_price=Decimal("180.00"),
        confidence_score=0.80,
        status="PENDING",
        agent_rationale={}
    )
    db_session.add(rec)
    db_session.commit()

    # Enable simulation fail
    os.environ["SIMULATE_STOREFRONT_FAIL"] = "true"

    try:
        res = client.post(f"/api/recommendations/{rec.id}/approve", headers=headers)
        assert res.status_code == 424
    finally:
        # Cleanup env
        if "SIMULATE_STOREFRONT_FAIL" in os.environ:
            del os.environ["SIMULATE_STOREFRONT_FAIL"]

    # Verify that status did NOT change to APPROVED, and product price was NOT updated!
    db_session.refresh(rec)
    db_session.refresh(prod)
    
    assert rec.status == "PENDING"
    assert prod.current_price == Decimal("150.00")
