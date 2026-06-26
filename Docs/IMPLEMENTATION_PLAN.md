# Implementation Plan - Dynamic Pricing Intelligence Dashboard

This document details the multi-phase execution strategy to build the Dynamic Pricing Intelligence Dashboard (Option B) using FastAPI (Backend) and Next.js (Frontend), directly mapping to the requirements outlined in the [PRD.md](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/Docs/PRD.md).

## User Review Required

> [!IMPORTANT]
> **Pydantic Agent Outputs**: In accordance with your request, all agents will yield structured Pydantic outputs. This ensures prompt safety, type-checked inputs for the central Pricing Strategy Agent, and standard JSON database storage for the audit log/rationale view.
>
> **Lightweight Agentic Framework**: We will build a custom asynchronous orchestrator in Python instead of using heavy multi-agent frameworks (like LangGraph or AutoGen). This keeps code blocks clean, lightweight, highly readable, and straightforward to defend in the live interview.

---

## Agent Output Pydantic Schemas

To guarantee structured and robust communication, we will define the following Pydantic schemas:

```python
from pydantic import BaseModel, Field, condecimal
from typing import List, Optional, Dict
from decimal import Decimal

# 1. Market Intelligence Agent Output
class CompetitorMetric(BaseModel):
    competitor_name: str
    price: Decimal
    price_delta_percent: float = Field(..., description="Percentage difference compared to our current price")

class MarketIntelligenceOutput(BaseModel):
    sku: str
    competitor_metrics: List[CompetitorMetric]
    average_competitor_price: Decimal
    overall_sentiment: str = Field(..., description="Sentiment derived from recent market signals: POSITIVE, NEUTRAL, NEGATIVE")
    market_rational: str = Field(..., description="Market analysis breakdown text")

# 2. Demand Forecasting Agent Output
class DemandForecastingOutput(BaseModel):
    sku: str
    sales_velocity_30d: int
    projected_elasticity: float = Field(..., description="Estimate of price elasticity of demand")
    seasonal_multiplier: float
    demand_intensity: str = Field(..., description="HIGH, MEDIUM, LOW")
    demand_rationale: str

# 3. Inventory & Cost Agent Output
class InventoryCostOutput(BaseModel):
    sku: str
    current_stock: int
    stock_status: str = Field(..., description="CRITICALLY_LOW, HEALTHY, OVERSTOCKED")
    cogs: Decimal
    margin_floor_price: Decimal = Field(..., description="COGS / (1 - minimum_margin_threshold)")
    inventory_rationale: str

# 4. Pricing Strategy Agent Output (Central Orchestrator)
class PricingStrategyOutput(BaseModel):
    sku: str
    suggested_price: Decimal
    confidence_score: float = Field(..., description="Confidence score between 0.0 and 1.0")
    margin_impact_percent: float
    market_analysis: MarketIntelligenceOutput
    demand_analysis: DemandForecastingOutput
    inventory_analysis: InventoryCostOutput
    strategy_rationale: str = Field(..., description="Synthesized reasoning explaining how inputs were balanced")

# 5. Execution & Compliance Agent Output
class ExecutionComplianceOutput(BaseModel):
    sku: str
    approved_price: Decimal
    action_taken: str = Field(..., description="AUTO_EXECUTED, ROUTED_TO_REVIEW, REJECTED_BY_RULES")
    compliance_passed: bool
    compliance_logs: List[str]
```

---

## Proposed Changes & Phasing

The implementation will be carried out entirely within the project root directory `./` (with `./backend` and `./frontend` folders).

---

### Phase 1: Database Setup, Multi-Tenant Auth & Authentication Tests
Set up the core database structures, schemas, and user signup/login endpoints with multi-tenant query isolation hooks.

#### [NEW] [backend/database.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/database.py)
*   Database connector script using SQLAlchemy + SQLite (for local development/testing) or PostgreSQL.
*   Declares `get_db` session dependencies.

#### [NEW] [backend/models.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/models.py)
*   SQLAlchemy models matching the database schema (Organizations, Users, Configurations, Products, CompetitorPrices, DemandSignals, Recommendations, PriceChangeAudits).

#### [NEW] [backend/auth.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/auth.py)
*   JWT authentication helpers, password hashing/verification, and `get_current_user` dependencies.
*   Enforces `org_id` context propagation.

#### [NEW] [backend/tests/test_auth_tenant.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/tests/test_auth_tenant.py)
*   **Tests**: Validate token generation, password hashing, and user authentication API endpoints.
*   **Tests**: Create Org A and Org B, register users, and verify database queries filter queries strictly to the requesting user's `org_id` (data isolation).

---

### Phase 2: SKU Catalog CRUD & Data Simulation Engines
Develop the core product database operations alongside background scripts to simulate competitor pricing movements, inventory counts, and market demand fluctuations.

#### [NEW] [backend/routers/products.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/routers/products.py)
*   FastAPI routes for product catalog operations: list products (filterable, paginated), create SKU, update SKU, delete SKU.

#### [NEW] [scripts/simulate_data.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/scripts/simulate_data.py)
*   A utility script to populate seed products (500+ items across electronics, home goods, apparel) and continuously update competitor prices and demand signals.

#### [NEW] [backend/tests/test_catalog_sim.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/tests/test_catalog_sim.py)
*   **Tests**: Test CRUD routes with valid and invalid payloads.
*   **Tests**: Test simulation utilities to verify data is correctly generated and updated in the DB.

---

### Phase 3: AI Multi-Agent Engine & Pydantic Schema Processing
Build the core async agentic orchestrator, write LLM integration layers with structured outputs (using Groq's JSON mode structured output capabilities), and implement test harnesses.

#### [NEW] [backend/services/agents.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/services/agents.py)
*   Implements `MarketAgent`, `DemandAgent`, `InventoryAgent`, and `StrategyAgent`.
*   Includes prompts, LLM client connections, and enforces structured outputs parsing directly into the respective Pydantic schemas.

#### [NEW] [backend/services/orchestrator.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/services/orchestrator.py)
*   The orchestrator service coordinating the execution flow.
*   Runs agents, forwards states, and returns final `PricingStrategyOutput`.

#### [NEW] [backend/tests/test_agents.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/tests/test_agents.py)
*   **Tests**: Mock the LLM service responses and check that agent classes properly parse LLM output into Pydantic models.
*   **Tests**: Verify that when the LLM service fails or returns invalid structures, fallback rules are triggered without crashing the pipeline.

---

### Phase 4: Human-in-the-Loop (HITL) Routing & Storefront Sync
Implement the Routing rules (Execution & Compliance Agent) that either auto-execute or push recommendations to the review queue. Implement decision endpoints and a simulated storefront interface.

#### [NEW] [backend/routers/recommendations.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/routers/recommendations.py)
*   API endpoints to retrieve recommendations, approve them, reject them, or override proposed prices.
*   Integrates database transaction locks to write audit trail logs during price changes.

#### [NEW] [backend/services/compliance.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/services/compliance.py)
*   Implements the `ExecutionComplianceAgent` validations:
    *   Compare strategy output confidence vs. auto-execute threshold.
    *   Compare suggested price against margin floors.
    *   Trigger mock storefront webhook sync.

#### [NEW] [backend/tests/test_hitl_compliance.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/tests/test_hitl_compliance.py)
*   **Tests**: Verify configuration thresholds routing (e.g. low-confidence -> `PENDING`, high-confidence -> `AUTO_EXECUTED`).
*   **Tests**: Verify storefront webhook updates roll back the database transaction if the external storefront returns a 500 error or times out.
*   **Tests**: Verify audit trail records match the exact change attributes (type, old price, new price, and author).

---

### Phase 5: Next.js Frontend Dashboard Scaffolding & Integration
Build a premium, visual, dark-mode Next.js frontend displaying the catalog, recommendations drawer, configuration slider, explainability diagrams, and audit trails.

#### [NEW] [frontend/package.json](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/frontend/package.json)
*   Scaffolds the Next.js and frontend package dependency configuration.

#### [NEW] [frontend/app/dashboard/page.tsx](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/frontend/app/dashboard/page.tsx)
*   Main interface featuring SKU catalog, sorting, filtering, and real-time status highlights.

#### [NEW] [frontend/app/recommendations/page.tsx](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/frontend/app/recommendations/page.tsx)
*   A side-by-side or dashboard view highlighting pending pricing recommendations.
*   Includes detailed drawer containing Pydantic-based agent outputs, confidence breakdowns, and manual action buttons (Approve / Reject / Modify).

#### [NEW] [frontend/app/globals.css](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/frontend/app/globals.css)
*   Implements the design tokens (Harmonized HSL dark palette, custom glassmorphic panels, outline animations).

---

## Verification Plan

### Automated Tests
We will write PyTest-based tests inside the backend directory:
```bash
# Run database and authentication isolation tests
pytest backend/tests/test_auth_tenant.py

# Run catalog and simulation verification tests
pytest backend/tests/test_catalog_sim.py

# Run agent schemas and mock LLM tests
pytest backend/tests/test_agents.py

# Run compliance, HITL routing, and rollback tests
pytest backend/tests/test_hitl_compliance.py
```

### Manual Verification
1.  **Orchestrator Execution**: Trigger competitor price change simulator, observe if agent recommendations are generated.
2.  **Threshold Validation**: Set auto-execute threshold to `0.90`. Observe if recommendations with `0.85` confidence remain `PENDING` in the UI. Change threshold to `0.80`, confirm auto-execution triggers storefront API.
3.  **Tenant Security check**: Log in with User A (Org A), attempt to call `/api/recommendations` with an Org B product ID, and verify the backend returns a `404 Not Found` or `403 Forbidden` response.
4.  **UI Responsiveness and Styling**: Verify the page components scale gracefully across Desktop displays and that loaders/skeletons render properly.
