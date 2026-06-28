# Technical Decisions & Rationale - PriceMatrix AI

This document outlines the core engineering choices, architectural patterns, prompt design principles, trade-offs, and future improvements implemented in the **PriceMatrix AI** platform.

---

## 1. Option Selection & Business Value
*   **Selected Option:** Option B – Dynamic Pricing Intelligence Dashboard.
*   **Rationale:** Dynamic pricing is a high-value enterprise challenge. Option B represents a comprehensive blend of frontend complexity (explainability accordions, recommendation actions, configuration controls) and backend rigour (multi-tenant authentication, transaction rollbacks, structured JSON output validation, and database seeding). It demonstrates how AI can transition from a passive advice engine to an automated, safe decision-support tool using a Human-in-the-Loop (HITL) approval mechanism.

---

## 2. Technology Stack Selection & Alternatives
*   **Chosen Stack:**
    *   **Backend:** FastAPI, SQLAlchemy, SQLite, Pydantic, Python.
    *   **Frontend:** Next.js (TypeScript, TailwindCSS/Vanilla CSS).
    *   **AI Engine:** Groq API (Llama 3 8B model), Pydantic structures, and local rule-based fallback engines.
*   **Rationale:**
    *   *FastAPI:* Chosen over heavier frameworks (like Django or Django REST Framework) for its speed, minimal boilerplate, native async support, and automatic OpenAPI generation. Its dependency injection framework is highly effective for injecting SQLite database sessions and guarding routes with JWT tenant checks.
    *   *SQLite:* Selected for local execution simplicity. It requires zero infrastructure setup or host-level database installation, while still supporting standard SQL relations, foreign key cascades, and ACID transactions.
    *   *Next.js:* Provided standard component encapsulation, page layouts, and asset optimizations.
    *   *Groq Llama 3:* Offers extremely low latency for LLM inference, keeping the multi-agent pipeline execution snappy (usually under 2 seconds).
*   **Alternatives Considered:**
    *   *Django / Django REST Framework (DRF):* Rejected because of unnecessary overhead. FastAPI's simple dependency injection and lightweight model definitions were more agile for a rapid development cycle.
    *   *Express.js / Node.js:* Considered, but Python was preferred because of its robust AI/ML ecosystem, ease of prompt manipulation, and superior mathematical capabilities for rule-based fallbacks.
    *   *React SPA (Vite):* Next.js was preferred for its built-in router structure, compilation diagnostics, and easier path to production scaling.

---

## 3. Multi-Tenancy Approach & Patterns
*   **Pattern Used:** Shared Database with Column-Based Tenant Isolation (`org_id` column).
*   **Rationale:**
    *   SQLite is a single-file database and does not support PostgreSQL-like schemas. Creating separate SQLite database files per tenant (database-level isolation) would lead to file-handle management overhead and complex migration pipelines.
    *   The shared-table pattern with an `org_id` column on business models (User, Product, Configuration, Recommendation, Audit Logs) was selected. 
    *   *Enforcement Mechanism:* Middleware dependencies (`Depends(get_current_user)`) validate the caller's JWT token, identify their `org_id`, and scope all SQL operations (SELECT, INSERT, UPDATE, DELETE) strictly to that organization. A user from Org A cannot read, modify, or trigger pipelines for any records belonging to Org B.

---

## 4. AI Design & Prompt Engineering Choices
*   **Design Pattern:** Multi-Agent Pipeline with a Synthesizer/Orchestrator.
    *   Instead of a single, monolithic prompt that struggles to perform catalog lookups, compliance checks, and strategy generation concurrently, the task is divided among specialized agents:
        1.  *Market Intelligence Agent:* Assesses competitor histories.
        2.  *Demand Forecasting Agent:* Evaluates sales velocities and external search multipliers.
        3.  *Inventory Cost Agent:* Pinpoints stock pressure (overstocked vs. critically low).
        4.  *Pricing Strategy Agent (Synthesizer):* Evaluates inputs from the three agents to compute the optimal price and confidence score.
*   **Prompt Engineering Decisions:**
    *   *Strict JSON Mode:* Agents are instructed via system prompts to return strictly structured JSON matching specified schemas. 
    *   *Type Safety:* The JSON string returned by the LLM is parsed directly into Pydantic models on the backend to validate types, constraints, and ranges immediately.
    *   *Resilient Fallbacks:* If the Groq API fails (due to key absence, rate limits, or timeouts) or if the LLM output is malformed, the orchestrator catches the exception and falls back to a mathematical pricing model (incorporating competitor averages, inventory ratios, and category floors). This prevents server crashouts.

---

## 5. Timeline Trade-Offs (5-Day Scope)
*   **Mock Storefront Synchronization:** Rather than setting up actual OAuth verification loops and Webhook endpoints for live Shopify/WooCommerce stores (which requires domain setup and app store registration), we built a highly robust mock storefront sync simulator. It includes custom environment switches (`SIMULATE_STOREFRONT_FAIL`) to test failure rollbacks.
*   **Mock Scraper Data:** Pre-seeded competitor histories and demand multiplier trends are updated via a local simulator script (`simulate_data.py`) rather than running live puppeteer scrapers, which would introduce hosting latency and scraper blocks.
*   **Single SQLite Engine:** Used SQLite for local development speed instead of containerizing PostgreSQL.

---

## 6. Future Improvements (with 2 More Weeks)
1.  **Production Database Migration:** Migrate to PostgreSQL and utilize row-level security (RLS) policies to reinforce tenant isolation at the database engine level.
2.  **Live Scraping Connectors:** Connect the Market Intelligence agent to Google Shopping search endpoints or scrapers to extract real-time market data.
3.  **Real Storefront Integrations:** Build actual WooCommerce/Shopify sync webhooks using OAuth.
4.  **Interactive Performance Charts:** Expand the frontend to plot revenue performance, pricing cycles, competitor movements, and profit margin changes over time.
5.  **Agent Performance Tuning:** Fine-tune smaller models on pricing datasets or construct vector embeddings (RAG) containing company pricing policies.

---

## 7. Hardest Challenges & Solutions
*   **Challenge: Guaranteeing JSON Compliance & LLM Latency.**
    *   *Problem:* LLM output text can contain explanations, formatting artifacts, or invalid JSON, which causes API routes to crash when deserializing data.
    *   *Solution:* We solved this by pairing Pydantic schema validation with a robust fallback system. The orchestrator validates all outputs. If an agent fails, a local business rule-based fallback algorithm handles the calculation, records the fallback execution within the strategy rationale field, and passes it cleanly back to the frontend. This ensures the app is completely bulletproof even under API failures.
*   **Challenge: Atomic Transactions during Storefront Sync Failures.**
    *   *Problem:* If a user approves a price recommendation, the database writes the new price, but if the subsequent storefront sync webhook fails, the DB state and storefront state become out of sync.
    *   *Solution:* Implemented database transaction blocks (`db.begin()`). The new price, recommendation status, and audit logs are written within a context manager. The storefront sync is triggered before committing the transaction. If the sync fails, the context manager raises an exception, automatically rolling back all DB writes so no state mismatch occurs.
