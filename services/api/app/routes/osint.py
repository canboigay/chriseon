from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.osint import BreachVIPClient, SearchField, BreachResult
from app.settings import get_settings

router = APIRouter()


class BreachSearchRequest(BaseModel):
    """Request payload for breach search"""
    term: str = Field(min_length=1, max_length=100, description="Search term (supports wildcards * and ?)")
    fields: list[str] = Field(
        min_length=1,
        max_length=10,
        description="Fields to search: email, username, domain, ip, phone, etc.",
    )
    categories: list[str] | None = Field(default=None, description="Optional category filters")


class BreachSearchResponse(BaseModel):
    """Response with breach search results"""
    term: str
    fields: list[str]
    results: list[BreachResult]
    count: int


@router.post("/osint/breach/search", response_model=BreachSearchResponse)
async def search_breaches(request: BreachSearchRequest):
    """
    Search for data breaches across 1000+ databases (10B+ records)
    
    Powered by BreachVIP free API with rate limiting (15 requests/minute).
    
    Supports wildcards:
    - `*` matches zero or more characters
    - `?` matches one character
    
    Example queries:
    - `admin@example.com` - exact match
    - `*@company.com` - all emails from domain
    - `admin?` - admin1, admin2, etc.
    """
    try:
        # Validate fields
        valid_fields = [f.value for f in SearchField]
        for field in request.fields:
            if field not in valid_fields:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid field '{field}'. Valid fields: {', '.join(valid_fields)}",
                )

        # Search breaches (with Redis caching)
        settings = get_settings()
        async with BreachVIPClient(redis_url=settings.redis_url) as client:
            results = await client.search(
                term=request.term,
                fields=request.fields,  # type: ignore
                categories=request.categories,
            )

        return BreachSearchResponse(
            term=request.term,
            fields=request.fields,
            results=results,
            count=len(results),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/osint/breach/email/{email}")
async def search_by_email(email: str):
    """Quick search by email address"""
    try:
        settings = get_settings()
        async with BreachVIPClient(redis_url=settings.redis_url) as client:
            results = await client.search_email(email)

        return {
            "email": email,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/osint/breach/username/{username}")
async def search_by_username(username: str):
    """Quick search by username"""
    try:
        settings = get_settings()
        async with BreachVIPClient(redis_url=settings.redis_url) as client:
            results = await client.search_username(username)

        return {
            "username": username,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/osint/breach/domain/{domain}")
async def search_by_domain(domain: str):
    """Quick search by domain (e.g., company.com)"""
    try:
        settings = get_settings()
        async with BreachVIPClient(redis_url=settings.redis_url) as client:
            results = await client.search_domain(domain)

        return {
            "domain": domain,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/osint/breach/ip/{ip}")
async def search_by_ip(ip: str):
    """Quick search by IP address"""
    try:
        settings = get_settings()
        async with BreachVIPClient(redis_url=settings.redis_url) as client:
            results = await client.search_ip(ip)

        return {
            "ip": ip,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/osint/fields")
async def list_search_fields():
    """List all available search fields"""
    return {
        "fields": [
            {
                "name": field.value,
                "description": field.value.replace("_", " ").title(),
            }
            for field in SearchField
        ]
    }
