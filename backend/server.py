import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base
from backend.routers import auth, products, recommendations

# Initialize DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Dynamic Pricing Intelligence Dashboard API",
    description="Multi-tenant backend for SKU catalog, AI multi-agent pricing orchestration, and HITL workflow.",
    version="1.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(recommendations.router)

@app.get("/")
def read_root():
    return {"message": "Dynamic Pricing Intelligence API is running."}

if __name__ == "__main__":
    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000, reload=True)
