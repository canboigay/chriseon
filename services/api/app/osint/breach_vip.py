"""
BreachVIP OSINT Integration Client

Free database search engine providing access to 1000+ databases
for breach research, OSINT and analysis. 10 billion records indexed.

API: https://breach.vip/api/docs
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field
from redis import Redis


class SearchField(str, Enum):
    """Supported search fields"""
    EMAIL = "email"
    PASSWORD = "password"
    DOMAIN = "domain"
    USERNAME = "username"
    IP = "ip"
    NAME = "name"
    UUID = "uuid"
    STEAMID = "steamid"
    PHONE = "phone"
    DISCORDID = "discordid"


class BreachResult(BaseModel):
    """A single breach record"""
    source: str = Field(description="Breach name/source")
    categories: str | list[str] = Field(description="Breach categories")
    # Additional dynamic fields returned in results
    data: dict[str, Any] = Field(default_factory=dict, description="All matched fields")

    class Config:
        extra = "allow"


class SearchRequest(BaseModel):
    """Request payload for breach search"""
    term: str = Field(min_length=1, max_length=100, description="Search term (supports wildcards)")
    fields: list[SearchField] = Field(min_length=1, max_length=10, description="Fields to search")
    categories: list[str] | None = Field(default=None, description="Filter by categories (e.g. ['minecraft'])")


class SearchResponse(BaseModel):
    """API response from breach search"""
    results: list[dict[str, Any]]
    total: int


class BreachVIPClient:
    """
    Client for BreachVIP API
    
    Free tier with rate limiting:
    - 15 requests per minute
    - Maximum 10,000 results per query
    
    Supports wildcards:
    - * matches zero or more characters
    - ? matches one character
    """

    BASE_URL = "https://breach.vip"
    RATE_LIMIT_PER_MINUTE = 15
    MAX_RESULTS = 10000

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        redis_url: str | None = None,
        cache_ttl: timedelta = timedelta(hours=24),
    ):
        """
        Initialize BreachVIP client
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Number of retries for failed requests
            redis_url: Redis connection URL for caching (optional)
            cache_ttl: How long to cache results (default 24 hours)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_ttl = cache_ttl
        self._client: httpx.AsyncClient | None = None
        self._redis: Redis | None = None
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time: float = 0
        
        # Initialize Redis if URL provided
        if redis_url:
            try:
                self._redis = Redis.from_url(redis_url, decode_responses=True)
            except Exception:
                # Silently fail - caching is optional
                self._redis = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.timeout,
            headers={
                "User-Agent": "Chriseon-OSINT/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
        if self._redis:
            self._redis.close()

    async def _rate_limit(self):
        """Enforce rate limiting (15 requests/minute)"""
        async with self._rate_limit_lock:
            import time
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            
            # Minimum time between requests (60s / 15 requests = 4s)
            min_interval = 60.0 / self.RATE_LIMIT_PER_MINUTE
            
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)
            
            self._last_request_time = time.time()

    async def search(
        self,
        term: str,
        fields: list[SearchField] | list[str],
        categories: list[str] | None = None,
    ) -> list[BreachResult]:
        """
        Search for breaches (with Redis caching)
        
        Args:
            term: Search term (supports wildcards * and ?)
            fields: Fields to search in (email, username, ip, etc.)
            categories: Optional category filters (e.g. ["minecraft"])
            
        Returns:
            List of breach results
            
        Raises:
            HTTPError: On API errors
            
        Examples:
            >>> results = await client.search("test@*.com", [SearchField.EMAIL])
            >>> results = await client.search("admin", [SearchField.USERNAME, SearchField.EMAIL])
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        # Convert string fields to enum if needed
        field_enums = []
        for f in fields:
            if isinstance(f, str):
                field_enums.append(SearchField(f))
            else:
                field_enums.append(f)
        
        # Check cache first
        cache_key = f"breach:{term}:{':'.join(sorted(f.value for f in field_enums))}"
        if categories:
            cache_key += f":{':'.join(sorted(categories))}"
        
        if self._redis:
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    return [BreachResult(**item) for item in data]
            except Exception:
                # Cache read failed, continue with API call
                pass

        request = SearchRequest(
            term=term,
            fields=field_enums,
            categories=categories,
        )

        # Rate limiting
        await self._rate_limit()

        # Make request with retries
        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    "/api/search",
                    json=request.model_dump(exclude_none=True),
                )
                response.raise_for_status()
                
                data = response.json()
                search_response = SearchResponse(**data)
                
                # Parse results into BreachResult objects
                results = []
                for item in search_response.results:
                    source = item.pop("source", "Unknown")
                    categories_val = item.pop("categories", [])
                    
                    result = BreachResult(
                        source=source,
                        categories=categories_val,
                        data=item,  # All other fields go into data dict
                    )
                    results.append(result)
                
                # Cache results
                if self._redis and results:
                    try:
                        cache_data = [r.dict() for r in results]
                        self._redis.setex(
                            cache_key,
                            int(self.cache_ttl.total_seconds()),
                            json.dumps(cache_data)
                        )
                    except Exception:
                        # Cache write failed, but we have results so continue
                        pass
                
                return results

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - wait and retry
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(60)  # Wait 1 minute
                        continue
                    raise Exception("Rate limit exceeded. Try again later.")
                elif e.response.status_code == 400:
                    raise ValueError(f"Bad request: {e.response.text}")
                elif e.response.status_code == 500:
                    raise Exception(f"Server error: {e.response.text}")
                else:
                    raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
            
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise Exception(f"Request failed: {str(e)}")

        raise Exception("Max retries exceeded")

    # Convenience methods for common searches

    async def search_email(self, email: str) -> list[BreachResult]:
        """Search by email address"""
        return await self.search(email, [SearchField.EMAIL])

    async def search_username(self, username: str) -> list[BreachResult]:
        """Search by username"""
        return await self.search(username, [SearchField.USERNAME])

    async def search_domain(self, domain: str) -> list[BreachResult]:
        """Search by domain (e.g., company.com)"""
        return await self.search(domain, [SearchField.DOMAIN])

    async def search_ip(self, ip: str) -> list[BreachResult]:
        """Search by IP address"""
        return await self.search(ip, [SearchField.IP])

    async def search_phone(self, phone: str) -> list[BreachResult]:
        """Search by phone number"""
        return await self.search(phone, [SearchField.PHONE])

    async def search_discord(self, discord_id: str) -> list[BreachResult]:
        """Search by Discord ID"""
        return await self.search(discord_id, [SearchField.DISCORDID])

    async def search_multi_field(
        self,
        term: str,
        fields: list[SearchField] | list[str],
    ) -> list[BreachResult]:
        """
        Search across multiple fields simultaneously
        
        Useful for finding all references to a term across different data types
        """
        return await self.search(term, fields)


# Example usage
async def example_usage():
    """Example of how to use the BreachVIP client"""
    async with BreachVIPClient() as client:
        print("=== Search by Email ===")
        email_results = await client.search_email("test@example.com")
        for result in email_results:
            print(f"Source: {result.source}")
            print(f"Categories: {result.categories}")
            print(f"Data: {result.data}")
            print("-" * 50)

        print("\n=== Search with Wildcard ===")
        wildcard_results = await client.search("admin*", [SearchField.USERNAME])
        print(f"Found {len(wildcard_results)} results for admin*")

        print("\n=== Multi-field Search ===")
        multi_results = await client.search_multi_field(
            "target_identifier",
            [SearchField.EMAIL, SearchField.USERNAME, SearchField.IP],
        )
        print(f"Found {len(multi_results)} results across multiple fields")


if __name__ == "__main__":
    asyncio.run(example_usage())
