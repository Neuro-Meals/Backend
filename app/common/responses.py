from __future__ import annotations

from math import ceil
from typing import Any

def success_response(
    data: Any = None,
    message: str = "Success",
):
    """
    Standard successful API response.
    """

    return {
        "success": True,
        "message": message,
        "data": data,
    }

def created_response(
    data: Any = None,
    message: str = "Created successfully.",
):
    """
    Standard response after creating a resource.
    """

    return {
        "success": True,
        "message": message,
        "data": data,
    }

def updated_response(
    data: Any = None,
    message: str = "Updated successfully.",
):
    return {
        "success": True,
        "message": message,
        "data": data,
    }

def deleted_response(
    message: str = "Deleted successfully.",
):
    return {
        "success": True,
        "message": message,
    }

def list_response(
    *,
    items,
    page: int,
    limit: int,
    total: int,
    message: str = "Success",
):
    """
    Standard paginated response.
    """

    total_pages = ceil(total / limit) if limit else 1

    return {
        "success": True,
        "message": message,
        "data": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_items": total,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
        },
    }

def dashboard_response(
    *,
    overview,
    statistics=None,
    charts=None,
    recent_activity=None,
):
    """
    Standard dashboard response.
    """

    return {
        "success": True,
        "data": {
            "overview": overview,
            "statistics": statistics or {},
            "charts": charts or {},
            "recent_activity": recent_activity or [],
        },
    }

def analytics_response(
    analytics,
):
    return {
        "success": True,
        "data": analytics,
    }

def error_payload(
    message: str,
    errors=None,
):
    """
    Optional helper for custom exception handlers.

    Normally FastAPI raises HTTPException, but if you
    implement a global exception handler later this helper
    can be reused.
    """

    return {
        "success": False,
        "message": message,
        "errors": errors or [],
    }

def validation_error_response(
    errors,
):
    return {
        "success": False,
        "message": "Validation failed.",
        "errors": errors,
    }

def empty_response(
    message="No data found.",
):
    return {
        "success": True,
        "message": message,
        "data": [],
    }