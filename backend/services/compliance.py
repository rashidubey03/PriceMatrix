import requests
from decimal import Decimal
from typing import List, Tuple
from sqlalchemy.orm import Session
from models import Configuration, Product, Recommendation, PriceChangeAudit
from schemas import PricingStrategyOutput, ExecutionComplianceOutput

class ExecutionComplianceAgent:
    def __init__(self, db: Session):
        self.db = db

    def process_recommendation(
        self,
        product: Product,
        strategy_output: PricingStrategyOutput
    ) -> ExecutionComplianceOutput:
        
        # 1. Fetch Org Config
        config = self.db.query(Configuration).filter(
            Configuration.org_id == product.org_id
        ).first()

        auto_threshold = 0.85
        category_floors = {}
        if config:
            auto_threshold = config.auto_execute_threshold
            category_floors = config.category_margin_floors

        # 2. Check margin floor compliance
        min_margin = product.margin_threshold
        if product.category in category_floors:
            min_margin = category_floors[product.category]

        suggested_price = strategy_output.suggested_price
        # margin = (price - cogs) / price
        margin_floor = product.cogs / Decimal(str(1 - min_margin))
        margin_floor = Decimal(f"{margin_floor:.2f}")

        logs = []
        compliance_passed = True
        
        if suggested_price < margin_floor:
            compliance_passed = False
            logs.append(f"Compliance Failed: Suggested price {suggested_price} breaches margin floor of {margin_floor}.")
        else:
            logs.append(f"Compliance Passed: Suggested price {suggested_price} is above margin floor of {margin_floor}.")

        # 3. Route based on confidence and compliance
        action_taken = "ROUTED_TO_REVIEW"
        if not compliance_passed:
            action_taken = "REJECTED_BY_RULES"
        elif strategy_output.confidence_score >= auto_threshold:
            action_taken = "AUTO_EXECUTED"
            logs.append(f"Auto-Execution Triggered: Confidence ({strategy_output.confidence_score}) meets/exceeds threshold ({auto_threshold}).")
        else:
            logs.append(f"Routed to Review: Confidence ({strategy_output.confidence_score}) is below threshold ({auto_threshold}).")

        # 4. Trigger Storefront update if Auto-Executed
        if action_taken == "AUTO_EXECUTED":
            success, msg = self.sync_to_storefront(product.id, suggested_price)
            if success:
                logs.append(f"Storefront Sync: {msg}")
            else:
                logs.append(f"Storefront Sync Error: {msg}")
                # Raise error to force DB transaction rollback
                raise RuntimeError(f"Storefront sync failed: {msg}. Transaction rolled back.")

        return ExecutionComplianceOutput(
            sku=product.sku,
            approved_price=suggested_price,
            action_taken=action_taken,
            compliance_passed=compliance_passed,
            compliance_logs=logs
        )

    def sync_to_storefront(self, product_id: str, new_price: Decimal) -> Tuple[bool, str]:
        # In a real environment, this makes an HTTP call to Shopify, Magento, etc.
        # We simulate a storefront webhook endpoint.
        # We can implement a local mock call to our backend storefront emulator.
        # If the environment variable 'SIMULATE_STOREFRONT_FAIL' is 'true', we mock a failure.
        import os
        if os.getenv("SIMULATE_STOREFRONT_FAIL") == "true":
            return False, "Storefront server returned 500 Internal Server Error."
        
        return True, f"Successfully synced new price of {new_price} to storefront."
