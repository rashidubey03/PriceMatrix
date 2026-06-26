import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import Organization, Configuration, Product, CompetitorPrice, DemandSignal
from backend.services.agents import (
    MarketIntelligenceAgent,
    DemandForecastingAgent,
    InventoryCostAgent,
    PricingStrategyAgent
)
from backend.services.orchestrator import PricingOrchestrator

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_price_matrix_agents.db"

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
def sample_setup(db_session):
    # Org
    org = Organization(name="Test Org")
    db_session.add(org)
    db_session.flush()

    # Configuration
    config = Configuration(
        org_id=org.id,
        auto_execute_threshold=0.85,
        category_margin_floors={"electronics": 0.10, "apparel": 0.20}
    )
    db_session.add(config)

    # Products
    # 1. Healthy Stock Product
    prod1 = Product(
        org_id=org.id,
        sku="SKU-HEALTHY",
        name="Healthy Headphones",
        category="electronics",
        current_price=Decimal("100.00"),
        cogs=Decimal("70.00"),
        inventory_count=50,
        margin_threshold=0.15
    )
    db_session.add(prod1)

    # 2. Critically Low Product
    prod2 = Product(
        org_id=org.id,
        sku="SKU-LOW",
        name="Rare Watch",
        category="electronics",
        current_price=Decimal("200.00"),
        cogs=Decimal("150.00"),
        inventory_count=3, # critically low
        margin_threshold=0.15
    )
    db_session.add(prod2)

    # 3. Overstocked Product
    prod3 = Product(
        org_id=org.id,
        sku="SKU-HIGH",
        name="Bulk Socks",
        category="apparel",
        current_price=Decimal("10.00"),
        cogs=Decimal("6.00"),
        inventory_count=200, # overstocked
        margin_threshold=0.20
    )
    db_session.add(prod3)
    db_session.flush()

    # Competitor Prices for Healthy Headphones
    comp1 = CompetitorPrice(product_id=prod1.id, competitor_name="Comp A", price=Decimal("95.00"))
    comp2 = CompetitorPrice(product_id=prod1.id, competitor_name="Comp B", price=Decimal("90.00"))
    db_session.add(comp1)
    db_session.add(comp2)

    # Demand signals
    demand1 = DemandSignal(product_id=prod1.id, trend_score=1.0, velocity_sales_30d=30, seasonal_multiplier=1.0)
    demand2 = DemandSignal(product_id=prod2.id, trend_score=1.5, velocity_sales_30d=80, seasonal_multiplier=1.2)
    demand3 = DemandSignal(product_id=prod3.id, trend_score=0.5, velocity_sales_30d=5, seasonal_multiplier=0.9)
    db_session.add(demand1)
    db_session.add(demand2)
    db_session.add(demand3)

    db_session.commit()

    return {
        "org": org,
        "prod_healthy": prod1,
        "prod_low": prod2,
        "prod_high": prod3
    }


def test_market_intelligence_agent(db_session, sample_setup):
    prod = sample_setup["prod_healthy"]
    agent = MarketIntelligenceAgent(db_session)
    output = agent.analyze(prod)
    
    assert output.sku == prod.sku
    assert output.average_competitor_price == Decimal("92.50")
    assert output.overall_sentiment == "NEGATIVE"  # Our price (100) is higher than competitor average (92.50)
    assert len(output.competitor_metrics) == 2


def test_demand_forecasting_agent(db_session, sample_setup):
    prod_low = sample_setup["prod_low"]
    agent = DemandForecastingAgent(db_session)
    output = agent.analyze(prod_low)

    assert output.sku == prod_low.sku
    assert output.demand_intensity == "HIGH"
    assert output.sales_velocity_30d == 80


def test_inventory_cost_agent(db_session, sample_setup):
    prod_high = sample_setup["prod_high"]
    agent = InventoryCostAgent(db_session)
    output = agent.analyze(prod_high)

    assert output.sku == prod_high.sku
    assert output.stock_status == "OVERSTOCKED"
    # Category floor apparel is 0.20. COGS = 6.00.
    # Floor price = 6.00 / (1 - 0.20) = 7.50
    assert output.margin_floor_price == Decimal("7.50")


def test_pricing_strategy_enforces_floor(db_session, sample_setup):
    # Overstocked product has cogs=6.00 and floor=7.50. Current price=10.00.
    # Let's say competitor price drops to 5.00 (which is lower than COGS).
    prod = sample_setup["prod_high"]
    
    # Update competitor price for socks to 5.00
    comp = CompetitorPrice(product_id=prod.id, competitor_name="CheapComp", price=Decimal("5.00"))
    db_session.add(comp)
    db_session.commit()

    orchestrator = PricingOrchestrator(db_session)
    strategy_output = orchestrator.run_pricing_pipeline(prod.id)

    # Strategy recommends price cuts because it is overstocked and competitor is cheap.
    # However, it MUST NOT breach the floor price of 7.50!
    assert strategy_output.suggested_price >= Decimal("7.50")
    assert "margin floor constraint" in strategy_output.strategy_rationale or "corrected to margin floor" in strategy_output.strategy_rationale
