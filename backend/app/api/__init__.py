"""
API Router - Aggregate all routes
"""

from fastapi import APIRouter
from app.api.routes import (
    dashboard_router,
    forecast_router,
    optimization_router,
    audit_router
)

api_router = APIRouter()

# Include all routers with prefixes
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(forecast_router, prefix="/forecast", tags=["Forecast"])
api_router.include_router(optimization_router, prefix="/optimization", tags=["Optimization"])
api_router.include_router(audit_router, prefix="/audit", tags=["Audit"])
