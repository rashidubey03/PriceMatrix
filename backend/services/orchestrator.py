from sqlalchemy.orm import Session
from models import Product
from schemas import PricingStrategyOutput
from services.agents import (
    MarketIntelligenceAgent,
    DemandForecastingAgent,
    InventoryCostAgent,
    PricingStrategyAgent
)

class PricingOrchestrator:
    def __init__(self, db: Session):
        self.db = db

    def run_pricing_pipeline(self, product_id: str) -> PricingStrategyOutput:
        # 1. Fetch Product
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product with ID {product_id} not found.")

        # 2. Instantiate Agents
        market_agent = MarketIntelligenceAgent(self.db)
        demand_agent = DemandForecastingAgent(self.db)
        inventory_agent = InventoryCostAgent(self.db)
        strategy_agent = PricingStrategyAgent(self.db)

        # 3. Execute Specialized Agents
        market_output = market_agent.analyze(product)
        demand_output = demand_agent.analyze(product)
        inventory_output = inventory_agent.analyze(product)

        # 4. Synthesize Optimal Price
        strategy_output = strategy_agent.synthesize(
            product=product,
            market=market_output,
            demand=demand_output,
            inventory=inventory_output
        )

        return strategy_output
