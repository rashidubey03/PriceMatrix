import os
import json
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

# Try importing groq, fallback to mock if not installed or no key
try:
    import groq
    from groq import Groq
except ImportError:
    groq = None
    Groq = None

from backend.models import Product, CompetitorPrice, DemandSignal, Configuration
from backend.schemas import (
    CompetitorMetric,
    MarketIntelligenceOutput,
    DemandForecastingOutput,
    InventoryCostOutput,
    PricingStrategyOutput
)

# Initialize Groq client if key is set
api_key = os.getenv("GROQ_API_KEY")
client = None
if groq and api_key:
    client = Groq(api_key=api_key)

class MarketIntelligenceAgent:
    def __init__(self, db: Session):
        self.db = db

    def analyze(self, product: Product) -> MarketIntelligenceOutput:
        # Fetch competitor prices
        comps = self.db.query(CompetitorPrice).filter(CompetitorPrice.product_id == product.id).all()
        
        # Safe calculations
        avg_price = Decimal("0.0")
        comp_metrics = []
        
        if comps:
            avg_price = sum(c.price for c in comps) / len(comps)
            for c in comps:
                delta = float((c.price - product.current_price) / product.current_price) * 100
                comp_metrics.append(CompetitorMetric(
                    competitor_name=c.competitor_name,
                    price=c.price,
                    price_delta_percent=round(delta, 2)
                ))
        else:
            avg_price = product.current_price
            comp_metrics.append(CompetitorMetric(
                competitor_name="Market Average (Self)",
                price=product.current_price,
                price_delta_percent=0.0
            ))
        
        # Decide sentiment
        sentiment = "NEUTRAL"
        if product.current_price > avg_price * Decimal("1.05"):
            sentiment = "NEGATIVE"  # Our price is higher, might be losing market share
        elif product.current_price < avg_price * Decimal("0.95"):
            sentiment = "POSITIVE"  # We are cheaper, highly competitive
            
        rationale = f"Analyzed {len(comps)} competitor price points. Average competitor price is {avg_price:.2f}. " \
                    f"Our current price is {product.current_price:.2f} (delta of {round(float(product.current_price - avg_price), 2)})."

        # Try LLM if configured
        if client:
            try:
                prompt = f"""
                You are a Market Intelligence Agent.
                Analyze the competitor prices for SKU {product.sku}.
                Product Current Price: {product.current_price}
                Competitors: {[{'name': m.competitor_name, 'price': float(m.price)} for m in comp_metrics]}
                
                Provide a structured JSON output matching:
                {{
                    "sku": "{product.sku}",
                    "competitor_metrics": [...],
                    "average_competitor_price": {float(avg_price)},
                    "overall_sentiment": "POSITIVE|NEUTRAL|NEGATIVE",
                    "market_rationale": "Your detailed reasoning here"
                }}
                """
                completion = client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                res = json.loads(completion.choices[0].message.content)
                # Parse to schema
                return MarketIntelligenceOutput(
                    sku=res["sku"],
                    competitor_metrics=[CompetitorMetric(**m) for m in res["competitor_metrics"]],
                    average_competitor_price=Decimal(str(res["average_competitor_price"])),
                    overall_sentiment=res["overall_sentiment"],
                    market_rationale=res["market_rationale"]
                )
            except Exception as e:
                # LLM Failure Fallback to rule engine
                pass
                
        return MarketIntelligenceOutput(
            sku=product.sku,
            competitor_metrics=comp_metrics,
            average_competitor_price=avg_price,
            overall_sentiment=sentiment,
            market_rationale=rationale
        )


class DemandForecastingAgent:
    def __init__(self, db: Session):
        self.db = db

    def analyze(self, product: Product) -> DemandForecastingOutput:
        demand = self.db.query(DemandSignal).filter(DemandSignal.product_id == product.id).first()
        
        # Default fallback
        velocity = 0
        trend = 1.0
        season = 1.0
        elasticity = -1.5
        intensity = "MEDIUM"
        
        if demand:
            velocity = demand.velocity_sales_30d
            trend = demand.trend_score
            season = demand.seasonal_multiplier
            
            # Simple heuristic
            if velocity > 50 or trend > 1.3:
                intensity = "HIGH"
                elasticity = -1.1  # less elastic (price inelastic, demand is hot)
            elif velocity < 15 or trend < 0.8:
                intensity = "LOW"
                elasticity = -2.2  # highly elastic (consumers sensitive to price drops)
                
        rationale = f"Sales velocity is {velocity} units/30d with a trend score of {trend}. " \
                    f"Seasonal multiplier is {season}x, yielding {intensity} demand intensity."

        if client:
            try:
                prompt = f"""
                You are a Demand Forecasting Agent.
                Analyze the demand factors for SKU {product.sku}.
                Historical 30-day velocity: {velocity} units
                Google Trends index: {trend}
                Seasonal Multiplier: {season}
                
                Provide a structured JSON output matching:
                {{
                    "sku": "{product.sku}",
                    "sales_velocity_30d": {velocity},
                    "projected_elasticity": {elasticity},
                    "seasonal_multiplier": {season},
                    "demand_intensity": "HIGH|MEDIUM|LOW",
                    "demand_rationale": "Your detailed reasoning here"
                }}
                """
                completion = client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                res = json.loads(completion.choices[0].message.content)
                return DemandForecastingOutput(**res)
            except Exception:
                pass

        return DemandForecastingOutput(
            sku=product.sku,
            sales_velocity_30d=velocity,
            projected_elasticity=elasticity,
            seasonal_multiplier=season,
            demand_intensity=intensity,
            demand_rationale=rationale
        )


class InventoryCostAgent:
    def __init__(self, db: Session):
        self.db = db

    def analyze(self, product: Product) -> InventoryCostOutput:
        # Fetch organization configuration to get category margin floors
        config = self.db.query(Configuration).filter(Configuration.org_id == product.org_id).first()
        
        # Minimum margin fallback
        min_margin = product.margin_threshold  # default product threshold
        if config and product.category in config.category_margin_floors:
            min_margin = config.category_margin_floors[product.category]
            
        # Margin floor price calculation: price where margin = min_margin
        # current_margin = (price - cogs) / price  => price = cogs / (1 - min_margin)
        margin_floor = product.cogs / Decimal(str(1 - min_margin))
        margin_floor = Decimal(f"{margin_floor:.2f}")

        # Decide stock status
        stock = product.inventory_count
        status = "HEALTHY"
        if stock <= 10:
            status = "CRITICALLY_LOW"
        elif stock >= 100:
            status = "OVERSTOCKED"

        rationale = f"Stock level is {stock} ({status}). COGS is {product.cogs}. " \
                    f"Enforced minimum margin for category '{product.category}' is {int(min_margin*100)}%, " \
                    f"yielding a margin floor price of {margin_floor:.2f}."

        if client:
            try:
                prompt = f"""
                You are an Inventory & Cost Agent.
                Analyze the inventory and margin constraints for SKU {product.sku}.
                Stock Level: {stock}
                COGS: {float(product.cogs)}
                Margin floor price: {float(margin_floor)}
                
                Provide a structured JSON output matching:
                {{
                    "sku": "{product.sku}",
                    "current_stock": {stock},
                    "stock_status": "CRITICALLY_LOW|HEALTHY|OVERSTOCKED",
                    "cogs": {float(product.cogs)},
                    "margin_floor_price": {float(margin_floor)},
                    "inventory_rationale": "Your detailed reasoning here"
                }}
                """
                completion = client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                res = json.loads(completion.choices[0].message.content)
                return InventoryCostOutput(
                    sku=res["sku"],
                    current_stock=res["current_stock"],
                    stock_status=res["stock_status"],
                    cogs=Decimal(str(res["cogs"])),
                    margin_floor_price=Decimal(str(res["margin_floor_price"])),
                    inventory_rationale=res["inventory_rationale"]
                )
            except Exception:
                pass

        return InventoryCostOutput(
            sku=product.sku,
            current_stock=stock,
            stock_status=status,
            cogs=product.cogs,
            margin_floor_price=margin_floor,
            inventory_rationale=rationale
        )


class PricingStrategyAgent:
    def __init__(self, db: Session):
        self.db = db

    def synthesize(
        self,
        product: Product,
        market: MarketIntelligenceOutput,
        demand: DemandForecastingOutput,
        inventory: InventoryCostOutput
    ) -> PricingStrategyOutput:
        
        # Rule Engine Logic (Synthesizer)
        suggested_price = product.current_price
        confidence = 0.80
        
        # Constraint: Suggested price must be >= margin floor price
        floor_price = inventory.margin_floor_price
        
        # Rule 1: Critically Low stock
        if inventory.stock_status == "CRITICALLY_LOW":
            # Increase price to maximize margins and slow sales velocity
            suggested_price = product.current_price * Decimal("1.10")
            confidence = 0.88
            strategy = "Critically low stock detected. Pricing strategy aims to increase margins and slow sales velocity to prevent stockouts."
            
        # Rule 2: Overstocked inventory
        elif inventory.stock_status == "OVERSTOCKED":
            # Drop price to clear stock, but keep it >= floor price
            suggested_price = min(product.current_price * Decimal("0.90"), market.average_competitor_price)
            suggested_price = max(suggested_price, floor_price)
            confidence = 0.85
            strategy = "High inventory levels detected. Pricing strategy drops price to stimulate sales volume and release cash, bounded by our margin floor."
            
        # Rule 3: Healthy stock & Competitive Pressure
        else:
            # If competitor average is significantly lower, we drop our price to match (but keep >= floor)
            if market.overall_sentiment == "NEGATIVE":
                suggested_price = max(market.average_competitor_price, floor_price)
                confidence = 0.78
                strategy = f"Competitors are pricing lower on average ({market.average_competitor_price:.2f}). Adjusting our price downwards to capture market demand, respecting the margin floor."
            # If demand is hot and competitors are higher, we can capture extra margin
            elif demand.demand_intensity == "HIGH" and market.overall_sentiment == "POSITIVE":
                suggested_price = product.current_price * Decimal("1.05")
                confidence = 0.82
                strategy = "Strong demand signals combined with higher competitor pricing. Increasing price slightly to maximize margin opportunities."
            else:
                # Default match competitor average if profitable
                suggested_price = max(market.average_competitor_price, floor_price)
                confidence = 0.80
                strategy = "Stable demand and market conditions. Aligned price with average competitor pricing to remain competitive."

        # Format suggested price
        suggested_price = Decimal(f"{suggested_price:.2f}")
        
        # Safety constraint check
        if suggested_price <= floor_price:
            suggested_price = floor_price
            if "Forced to margin floor constraint" not in strategy:
                strategy += " (Forced to margin floor constraint)."
            
        # Margin impact calculation
        margin_impact = float((suggested_price - product.cogs) / suggested_price) * 100

        if client:
            try:
                prompt = f"""
                You are the Pricing Strategy Orchestrator Agent.
                Synthesize the outputs from the specialized agents to recommend the final optimal price.
                SKU: {product.sku}
                COGS: {float(product.cogs)}
                Current Price: {float(product.current_price)}
                Market Sentiment: {market.overall_sentiment}
                Average Competitor Price: {float(market.average_competitor_price)}
                Demand Intensity: {demand.demand_intensity}
                Inventory Status: {inventory.stock_status}
                Margin Floor Price Constraint: {float(floor_price)}
                
                Provide a structured JSON output matching:
                {{
                    "sku": "{product.sku}",
                    "suggested_price": {float(suggested_price)},
                    "confidence_score": {confidence},
                    "margin_impact_percent": {margin_impact},
                    "strategy_rationale": "Your detailed reasoning here"
                }}
                """
                completion = client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                res = json.loads(completion.choices[0].message.content)
                
                final_price = Decimal(str(res["suggested_price"]))
                # Strict enforcement of margin floor even for LLM suggestions
                if final_price < floor_price:
                    final_price = floor_price
                    res["strategy_rationale"] += " (Price corrected to margin floor boundary)."
                    
                return PricingStrategyOutput(
                    sku=product.sku,
                    suggested_price=final_price,
                    confidence_score=float(res["confidence_score"]),
                    margin_impact_percent=float(res["margin_impact_percent"]),
                    market_analysis=market,
                    demand_analysis=demand,
                    inventory_analysis=inventory,
                    strategy_rationale=res["strategy_rationale"]
                )
            except Exception:
                pass

        return PricingStrategyOutput(
            sku=product.sku,
            suggested_price=suggested_price,
            confidence_score=confidence,
            margin_impact_percent=round(margin_impact, 2),
            market_analysis=market,
            demand_analysis=demand,
            inventory_analysis=inventory,
            strategy_rationale=strategy
        )
