# System Architecture Design - PriceMatrix AI

This document provides a technical guide to the architecture, database layout, component interactions, and security boundaries of the **PriceMatrix AI** platform.

---

## 1. High-Level Architecture Overview

PriceMatrix AI is built on a clean full-stack architectural split: a Next.js Single-Page Application (SPA) client and a FastAPI multi-tenant backend server connected to local SQLite database containers. 

The system leverages a **Multi-Agent AI Pipeline** to evaluate products and suggest pricing updates, which are either auto-executed or routed to a manual queue based on confidence thresholds and organization margin rules.

```mermaid
graph TD
    %% Frontend Client Layer
    subgraph Client Layer (Next.js SPA)
        UI[page.tsx Dashboard UI]
        APIClient[api.ts Fetch client]
        Storage[(Browser LocalStorage)]
        UI --> APIClient
        APIClient -.->|Read/Write JWT| Storage
    end

    %% Backend Server Gateway
    subgraph Application Server (FastAPI)
        RouteAuth[routers/auth.py]
        RouteProd[routers/products.py]
        RouteRec[routers/recommendations.py]
        Middleware[auth.py JWT & RBAC Middleware]
        
        APIClient -->|HTTP REST + JWT Bearer| Middleware
        Middleware --> RouteAuth
        Middleware --> RouteProd
        Middleware --> RouteRec
    end

    %% Core Application Orchestrator & Services
    subgraph AI & Compliance Engine
        Orch[services/orchestrator.py]
        Agents[services/agents.py Multi-Agents]
        Comp[services/compliance.py Compliance Guard]
        
        RouteRec -->|Trigger Pipeline| Orch
        Orch -->|Invoke LLM / Fallbacks| Agents
        Agents -->|Suggested Price + Confidence| Orch
        Orch -->|Evaluate Constraints| Comp
    end

    %% Database & External Integrations
    subgraph Integrations & Persistence
        DB[(SQLAlchemy / price_matrix.db)]
        Storefront[Mock Storefront Sync Endpoint]
        
        RouteAuth & RouteProd & RouteRec -->|SQL Query| DB
        Comp -->|Query org configs & save| DB
        Comp -->|Storefront PUT Sync| Storefront
    end
    
    style Client Layer fill:#f9f,stroke:#333,stroke-width:2px
    style Application Server fill:#bbf,stroke:#333,stroke-width:2px
    style AI & Compliance Engine fill:#dfd,stroke:#333,stroke-width:2px
    style Integrations & Persistence fill:#fdd,stroke:#333,stroke-width:2px
```

---

## 2. Core System Components

### A. Frontend Client (Next.js SPA)
*   **Location:** `frontend/`
*   **Design Pattern:** State-driven Single-Page Application using React Hooks.
*   **Authentication & Security:** 
    *   JWT token is stored in the browser's `localStorage`.
    *   The `api.ts` file encapsulates all fetch calls, automatically adding the `Authorization: Bearer <JWT>` header to all outgoing requests.
    *   *401 Interceptor:* If the API returns a `401 Unauthorized` response (e.g. database reseeded, stale token), the client clears the token and triggers a page refresh, immediately redirecting the user back to the login screen.
*   **Access Control:** Role-Based visibility controls. Admin inputs (Auto-Execute sliders, Category Margin sliders, SKU creation buttons) are disabled or hidden in the UI when the logged-in user is an `ANALYST`.

### B. REST API Gateway (FastAPI)
*   **Location:** `backend/`
*   **Routing Engine:** Sub-routers divided by domain:
    *   `/api/auth`: Login and registration routes.
    *   `/api/products`: SKU catalog CRUD routes.
    *   `/api/recommendations`: Triggering pipeline analyses, reading recommendations, processing manual approvals, overrides, or rejections.
    *   `/api/config`: Fetching and saving configuration settings.
*   **Dependency Injection (`Depends`):** Exposes reusable dependency chains:
    *   `get_db`: Yields transactional SQLAlchemy sessions.
    *   `get_current_user`: Extracts JWT tokens from requests, validates them, and yields the authenticated `User` record.
    *   `require_role`: Checks the caller's role to enforce path permissions (e.g. Workspace Admins only).

### C. Multi-Tenant Relational Databases (SQLAlchemy & SQLite)
*   **Persistence Layer:** Individual SQLite database engines.
*   **Model Schema Layout:**
    *   `organizations` (Org Container)
    *   `users` (User records connected via `org_id` with hashed password records)
    *   `configurations` (Workspace margins config connected via `org_id`)
    *   `products` (SKU catalog connected via `org_id`)
    *   `competitor_prices` (Historical pricing logs connected to product records)
    *   `demand_signals` (Historical elasticity signals connected to product records)
    *   `recommendations` (Computed AI prices queue connected via `org_id` and `product_id`)
    *   `price_change_audits` (Historical timeline audit tracker connected via `org_id` and `product_id`)

---

## 3. Multi-Agent Pricing Execution Pipeline

The Pricing Engine uses a multi-agent modular workflow where specialized task components are isolated to prevent monolithic context confusion and query degradation:

```
[Trigger Post Request]
         │
         ▼
┌──────────────────────────────────────────────┐
│  services/orchestrator.py (Orchestrator)     │
└────────┬─────────────────────────────────────┘
         │
         ├─► [Market Intelligence Agent]  ──► (Analyzes Competitor History)
         ├─► [Demand Forecasting Agent]   ──► (Evaluates Search Multipliers)
         └─► [Inventory Cost Agent]       ──► (Checks Inventory Pressures)
         │
         ▼
┌──────────────────────────────────────────────┐
│  Pricing Strategy Agent (Synthesizer)        │ (LLM Llama-3 / Resilient Fallbacks)
└────────┬─────────────────────────────────────┘
         │ (Returns Suggested Price & Confidence)
         ▼
┌──────────────────────────────────────────────┐
│  services/compliance.py (Compliance Agent)   │
└────────┬─────────────────────────────────────┘
         │
         ├─► Check Category Floors (Adjusts up if breached)
         │
         ├── [Confidence >= Auto-Execute Threshold]
         │        ├─► Sync to Storefront API (Mock)
         │        ├─► On Sync Success: Commit to DB (Update Price + Log Audit)
         │        └─► On Sync Fail: Abort and Rollback Transaction
         │
         └── [Confidence < Auto-Execute Threshold]
                  └─► Save to Recommendations Queue in DB (PENDING status)
```

### Agent Roles & prompt patterns
1.  **Market Intelligence Agent:** Evaluates average competitor price data. Returns structured JSON containing average competitor price and overall sentiment analysis (`POSITIVE`, `NEUTRAL`, `NEGATIVE`).
2.  **Demand Forecasting Agent:** Evaluates velocity (sales volume) and seasonality demand multipliers. Returns structured demand intensity flags (`HIGH`, `MEDIUM`, `LOW`).
3.  **Inventory Cost Agent:** Identifies holding costs based on stocking thresholds. Returns stock pressure alerts (`OVERSTOCKED`, `HEALTHY`, `CRITICALLY_LOW`).
4.  **Strategy Agent (Synthesizer):** Combines the findings from the previous three agents. Computes the optimal suggestion price, records the strategy rationale, and evaluates the confidence score (from `0.0` to `1.0`).
5.  **Local Rule Fallback Engine:** If the LLM call fails, is rate-limited, or outputs malformed strings, the orchestrator triggers a fallback pricing function. This helper computes competitor averages, checks inventory status, evaluates demand signals, and applies a business rule calculation to keep the application responsive.

---

## 4. Multi-Tenant Security Architecture

Multi-tenancy is enforced using the **Shared Database, Column-Based Separation** pattern. All organizational data is kept in the same database file, and tenant isolation is strictly verified at the application level:

```
[Frontend Client Request]
         │ (JWT Bearer Token Header)
         ▼
┌────────────────────────────────────────────────────────┐
│  FastAPI Security Dependency Check                     │
└────────┬───────────────────────────────────────────────┘
         │ 1. Validate signature of token using SECRET_KEY
         │ 2. Extract payload `sub` (User UUID)
         │ 3. Fetch User and retrieve their Organization ID (`org_id`)
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Middleware-Scoped SQLAlchemy Session Injection       │
└────────┬───────────────────────────────────────────────┘
         │ Exposes User's `org_id` context to the API router handler
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Enforced SQL Filtering                                 │
└────────────────────────────────────────────────────────┘
         │ E.g.: db.query(Product).filter(
         │           Product.org_id == current_user.org_id,
         │           Product.id == product_id
         │       ).first()
```

*   **Middleware-Level Scoping:** Endpoints scoping operations (such as listing catalog products, modifying margin configs, or reading audits) append `filter(Model.org_id == current_user.org_id)` to SQL queries. This guarantees that an authenticated user from Workspace A cannot view, modify, or delete any records belonging to Workspace B.

---

## 5. Storefront Integration & Atomic Rollbacks

To prevent state inconsistencies (e.g. database updates a price but the storefront sync fails), the compliance guard enforces **atomic transactional boundaries** during Human-in-the-Loop (HITL) approvals:

1.  **Open Transaction Context:** The router opens an explicit SQL transaction block: `with db.begin():` (providing atomic safety).
2.  **State Staging:** Stages database mutations: updates the recommendation status to `APPROVED`, changes the product's `current_price` to the suggested price, and generates a new `PriceChangeAudit` log.
3.  **External Sync Trigger:** Issues a mock API call to synchronize the price changes with the external storefront (Shopify/WooCommerce).
4.  **Transactional Commit / Rollback:**
    *   *If Storefront Sync Succeeds:* The database transaction is committed cleanly, and the frontend updates.
    *   *If Storefront Sync Fails:* An exception is thrown, rolling back the staged database updates. The catalog price and recommendation status revert to their original values, preventing database-to-storefront state mismatch.
