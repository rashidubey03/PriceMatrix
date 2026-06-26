# Walkthrough - Dynamic Pricing Intelligence Dashboard

We have completed the full-stack implementation of the **Dynamic Pricing Intelligence Dashboard (Option B)** as defined in the technical assessment. 

---

## Deliverables Summary

All backend logic, test files, and frontend layout codes are located in the project root:

### 1. Database & Authentication (Multi-Tenancy)
*   [database.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/database.py): Core SQLAlchemy engine connector using SQLite.
*   [models.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/models.py): Declares relational entities containing `org_id` parameters to guarantee multi-tenant security.
*   [auth.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/auth.py): Implements direct `bcrypt` password checks, JWT access token generation, and `get_current_user` middleware hooks.
*   [schemas.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/schemas.py): Pydantic validation schemas.

### 2. Multi-Tenant API Routers
*   [routers/auth.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/routers/auth.py): Signup and login routes, initializing default configurations on organization setups.
*   [routers/products.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/routers/products.py): SKU catalog CRUD endpoints.
*   [routers/recommendations.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/routers/recommendations.py): Recommendation queue actions (approve, reject, modify overrides), configurations edits, and price audit log endpoints.

### 3. Multi-Agent Pricing Engine (Pydantic Outputs & Fallbacks)
*   [services/agents.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/services/agents.py): Housing individual agent prompts (Market, Demand, Inventory, Strategy) yielding structured Pydantic models. Includes local business rule fallback systems for server resilience.
*   [services/orchestrator.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/services/orchestrator.py): Synthesizer pipeline driver.
*   [services/compliance.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/services/compliance.py): Execution and compliance boundaries router, handling storefront webhooks.

### 4. Seed Data & Automation Scripts
*   [scripts/simulate_data.py](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/backend/scripts/simulate_data.py): DB seeder. Spawns 12 products across category groups and populates competitor histories and Google Trends demands.

### 5. Next.js Frontend Dashboard Client
*   [api.ts](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/frontend/src/app/api.ts): API client wrapper managing request authorizations.
*   [globals.css](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/frontend/src/app/globals.css): Custom dark theme palette (`#09090b`), card boards, progress bars, and custom layouts.
*   [page.tsx](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/frontend/src/app/page.tsx): Main client application providing multi-tenant authentication views, the catalog grid table with custom search/sort, recommendations drawers with explainability accordions, config sliders, and price audit log widgets.
*   [layout.tsx](file:///c:/Users/rashi/OneDrive/Desktop/PriceMatrix/frontend/src/app/layout.tsx): Top-level shell configuration incorporating SEO title tags and descriptions.

---

## Verification & Build Results

### 1. Backend Testing Suite
We executed the pytest suite containing **16 automated test cases** verifying token configurations, tenant isolations, multi-agent rule logic, manual overrides margin validations, and transactional database rollbacks.

**Result: 16 Passed**
```bash
backend\tests\test_agents.py ....                                        [ 25%]
backend\tests\test_auth_tenant.py ....                                   [ 50%]
backend\tests\test_catalog_sim.py ...                                    [ 68%]
backend\tests\test_hitl_compliance.py .....                              [100%]
====================== 16 passed in 5.46s =======================
```

### 2. Frontend Optimized Compilation
We executed the Next.js production bundler to verify TypeScript and client code safety.

**Result: Compiled Successfully**
```bash
▲ Next.js 16.2.9 (Turbopack)
  Creating an optimized production build ...
✓ Compiled successfully in 1551ms
  Running TypeScript ...
  Finished TypeScript in 1773ms ...
✓ Generating static pages using 5 workers (4/4) in 529ms
```

---

## Local Development Execution Guide

To run the application locally on your machine, follow these steps:

### 1. Setup Virtual Environment & Install Dependencies
Navigate into the `backend` directory, create a Python virtual environment, and install the required dependencies:
```powershell
# Navigate to the backend folder
cd backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (CMD):
.\venv\Scripts\activate.bat
# On macOS/Linux:
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
```

### 2. Start the Backend API
With the virtual environment activated, stay in the `backend` directory to run the database seeder and FastAPI server:
```powershell
# 1. Populate the database
python scripts/simulate_data.py

# 2. Run the FastAPI development server
uvicorn server:app --reload
```
The API documentation will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 3. Run the Frontend Dashboard
Navigate to the `frontend` folder and launch the client dev server:
```powershell
cd frontend
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your web browser.

### 4. Demo Credentials
Use these pre-seeded accounts to verify multi-tenant isolation and role levels:
*   **Admin User**:
    *   **Email**: `admin@klypup.com`
    *   **Password**: `admin123`
*   **Analyst User**:
    *   **Email**: `analyst@klypup.com`
    *   **Password**: `analyst123`
