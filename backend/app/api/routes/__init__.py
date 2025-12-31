from .dashboard import router as dashboard_router
from .forecast import router as forecast_router
from .optimization import router as optimization_router
from .audit import router as audit_router

__all__ = [
    "dashboard_router",
    "forecast_router",
    "optimization_router",
    "audit_router"
]
