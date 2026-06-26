import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Numeric,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship
from backend.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="organization", cascade="all, delete-orphan")
    configuration = relationship("Configuration", uselist=False, back_populates="organization", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="organization", cascade="all, delete-orphan")
    audits = relationship("PriceChangeAudit", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'ADMIN' or 'ANALYST'
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")
    reviewed_recommendations = relationship("Recommendation", back_populates="reviewer")
    audited_changes = relationship("PriceChangeAudit", back_populates="user")


class Configuration(Base):
    __tablename__ = "configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    auto_execute_threshold = Column(Float, nullable=False, default=0.85)
    category_margin_floors = Column(JSON, nullable=False, default=dict)  # e.g., {"electronics": 0.10, "apparel": 0.25}
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="configuration")


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    sku = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    current_price = Column(Numeric(10, 2), nullable=False)
    cogs = Column(Numeric(10, 2), nullable=False)
    inventory_count = Column(Integer, nullable=False, default=0)
    margin_threshold = Column(Float, nullable=False, default=0.15)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="products")
    competitor_prices = relationship("CompetitorPrice", back_populates="product", cascade="all, delete-orphan")
    demand_signals = relationship("DemandSignal", back_populates="product", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="product", cascade="all, delete-orphan")
    audits = relationship("PriceChangeAudit", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("org_id", "sku", name="unique_sku_per_org"),
    )


class CompetitorPrice(Base):
    __tablename__ = "competitor_prices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    competitor_name = Column(String(100), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="competitor_prices")


class DemandSignal(Base):
    __tablename__ = "demand_signals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    trend_score = Column(Float, nullable=False, default=1.0)
    velocity_sales_30d = Column(Integer, nullable=False, default=0)
    seasonal_multiplier = Column(Float, nullable=False, default=1.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="demand_signals")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    recommended_price = Column(Numeric(10, 2), nullable=False)
    confidence_score = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")  # 'PENDING', 'APPROVED', 'REJECTED', 'AUTO_EXECUTED'
    rejection_reason = Column(String(255), nullable=True)
    agent_rationale = Column(JSON, nullable=False)  # Stores serialized dictionary of Pydantic outputs
    suggested_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    organization = relationship("Organization", back_populates="recommendations")
    product = relationship("Product", back_populates="recommendations")
    reviewer = relationship("User", back_populates="reviewed_recommendations")
    audits = relationship("PriceChangeAudit", back_populates="recommendation")


class PriceChangeAudit(Base):
    __tablename__ = "price_change_audits"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    recommendation_id = Column(String(36), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True)
    old_price = Column(Numeric(10, 2), nullable=False)
    new_price = Column(Numeric(10, 2), nullable=False)
    changed_by = Column(String(36), ForeignKey("users.id"), nullable=True)  # Null if auto-executed
    change_type = Column(String(50), nullable=False)  # 'AUTO', 'APPROVED', 'MANUAL_OVERRIDE'
    changed_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="audits")
    product = relationship("Product", back_populates="audits")
    recommendation = relationship("Recommendation", back_populates="audits")
    user = relationship("User", back_populates="audited_changes")
