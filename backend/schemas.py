from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime

# Auth Schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str
    role: str = Field(..., description="ADMIN or ANALYST")
    org_name: Optional[str] = Field(None, description="Provide to create a new organization")
    org_id: Optional[str] = Field(None, description="Provide to join an existing organization")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    org_id: str

    class Config:
        orm_mode = True
        from_attributes = True

class OrganizationResponse(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Product Schemas
class ProductBase(BaseModel):
    sku: str
    name: str
    category: str
    current_price: Decimal
    cogs: Decimal
    inventory_count: int
    margin_threshold: float = 0.15

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    current_price: Optional[Decimal] = None
    cogs: Optional[Decimal] = None
    inventory_count: Optional[int] = None
    margin_threshold: Optional[float] = None

class ProductResponse(ProductBase):
    id: str
    org_id: str
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

# Configuration Schemas
class ConfigurationUpdate(BaseModel):
    auto_execute_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    category_margin_floors: Optional[Dict[str, float]] = None

class ConfigurationResponse(BaseModel):
    id: str
    org_id: str
    auto_execute_threshold: float
    category_margin_floors: Dict[str, float]
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

# Competitor Price & Demand Signal Schemas
class CompetitorPriceResponse(BaseModel):
    id: str
    competitor_name: str
    price: Decimal
    fetched_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class DemandSignalResponse(BaseModel):
    id: str
    trend_score: float
    velocity_sales_30d: int
    seasonal_multiplier: float
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

# Recommendation Schemas
class RecommendationResponse(BaseModel):
    id: str
    org_id: str
    product_id: str
    recommended_price: Decimal
    confidence_score: float
    status: str
    rejection_reason: Optional[str] = None
    agent_rationale: Dict
    suggested_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    class Config:
        orm_mode = True
        from_attributes = True

class RecommendationReject(BaseModel):
    reason: str

class RecommendationModify(BaseModel):
    price: Decimal

# Audit Schemas
class AuditResponse(BaseModel):
    id: str
    org_id: str
    product_id: str
    recommendation_id: Optional[str] = None
    old_price: Decimal
    new_price: Decimal
    changed_by: Optional[str] = None
    change_type: str
    changed_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

# Agent Pydantic Outputs
class CompetitorMetric(BaseModel):
    competitor_name: str
    price: Decimal
    price_delta_percent: float

class MarketIntelligenceOutput(BaseModel):
    sku: str
    competitor_metrics: List[CompetitorMetric]
    average_competitor_price: Decimal
    overall_sentiment: str  # POSITIVE, NEUTRAL, NEGATIVE
    market_rationale: str

class DemandForecastingOutput(BaseModel):
    sku: str
    sales_velocity_30d: int
    projected_elasticity: float
    seasonal_multiplier: float
    demand_intensity: str  # HIGH, MEDIUM, LOW
    demand_rationale: str

class InventoryCostOutput(BaseModel):
    sku: str
    current_stock: int
    stock_status: str  # CRITICALLY_LOW, HEALTHY, OVERSTOCKED
    cogs: Decimal
    margin_floor_price: Decimal
    inventory_rationale: str

class PricingStrategyOutput(BaseModel):
    sku: str
    suggested_price: Decimal
    confidence_score: float  # 0.0 to 1.0
    margin_impact_percent: float
    market_analysis: MarketIntelligenceOutput
    demand_analysis: DemandForecastingOutput
    inventory_analysis: InventoryCostOutput
    strategy_rationale: str

class ExecutionComplianceOutput(BaseModel):
    sku: str
    approved_price: Decimal
    action_taken: str  # AUTO_EXECUTED, ROUTED_TO_REVIEW, REJECTED_BY_RULES
    compliance_passed: bool
    compliance_logs: List[str]
