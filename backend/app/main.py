from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routers import auth, organization, products, upload, dashboard, sku_detail, reports, import_history, subscription, admin

# Create database tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Multi-Tenant E-Commerce Profitability CRM SaaS Backend API",
    version=settings.VERSION
)

# CORS configuration: strict parameterized origins in production, localhost in development
if settings.ENVIRONMENT == "production":
    allowed_origins = [settings.FRONTEND_URL.rstrip("/")] if settings.FRONTEND_URL else []
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    if settings.FRONTEND_URL and settings.FRONTEND_URL.rstrip("/") not in allowed_origins:
        allowed_origins.append(settings.FRONTEND_URL.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
for pfx in ["/api/v1", "/api"]:
    app.include_router(auth.router, prefix=pfx)
    app.include_router(organization.router, prefix=pfx)
    app.include_router(products.router, prefix=pfx)
    app.include_router(upload.router, prefix=pfx)
    app.include_router(dashboard.router, prefix=pfx)
    app.include_router(sku_detail.router, prefix=pfx)
    app.include_router(reports.router, prefix=pfx)
    app.include_router(import_history.router, prefix=pfx)
    app.include_router(subscription.router, prefix=pfx)
    app.include_router(admin.router, prefix=pfx)

@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "tagline": settings.TAGLINE,
        "status": "online",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
