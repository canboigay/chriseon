"""
SkidSearch OSINT Integration Client

Provides interface to SkidSearch for data breach lookups.
Supports searching by email, username, IP, and other identifiers.
"""

import os
import httpx
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class SearchType(Enum):
    """Types of searches supported by SkidSearch"""
    EMAIL = "email"
    USERNAME = "username"
    IP = "ip"
    DOMAIN = "domain"
    PHONE = "phone"


@dataclass
class BreachResult:
    """Represents a data breach result"""
    source: str
    date: Optional[str]
    data_types: List[str]
    records: Dict[str, Any]


class SkidSearchClient:
    """Client for interacting with SkidSearch API"""
    
    def __init__(
        self,
        base_url: str = "https://www.skidsearch.xyz",
        api_key: Optional[str] = None,
        session_cookie: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize SkidSearch client
        
        Args:
            base_url: Base URL for SkidSearch
            api_key: API key if available
            session_cookie: Browser session cookie for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.api_key = api_key or os.getenv("SKIDSEARCH_API_KEY")
        self.session_cookie = session_cookie or os.getenv("SKIDSEARCH_SESSION")
        self.timeout = timeout
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._build_headers()
        )
    
    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with authentication"""
        headers = {
            "User-Agent": "SkidSearch-Python-Client/1.0",
            "Accept": "application/json",
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        if self.session_cookie:
            headers["Cookie"] = self.session_cookie
        
        return headers
    
    async def search(
        self,
        query: str,
        search_type: SearchType = SearchType.EMAIL,
        limit: int = 100
    ) -> List[BreachResult]:
        """
        Search for data breaches
        
        Args:
            query: Search query (email, username, IP, etc.)
            search_type: Type of search to perform
            limit: Maximum results to return
            
        Returns:
            List of breach results
        """
        # Placeholder - will be updated once we know the actual API structure
        endpoint = f"/api/search"  # Adjust based on actual API
        
        params = {
            "query": query,
            "type": search_type.value,
            "limit": limit
        }
        
        try:
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_results(data)
            
        except httpx.HTTPStatusError as e:
            raise Exception(f"SkidSearch API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"SkidSearch request failed: {str(e)}")
    
    def _parse_results(self, data: Dict[str, Any]) -> List[BreachResult]:
        """Parse API response into structured results"""
        # This will be updated based on actual API response format
        results = []
        
        # Placeholder parsing logic
        if isinstance(data, dict) and "results" in data:
            for item in data["results"]:
                result = BreachResult(
                    source=item.get("source", "Unknown"),
                    date=item.get("breach_date"),
                    data_types=item.get("data_types", []),
                    records=item.get("data", {})
                )
                results.append(result)
        
        return results
    
    async def search_email(self, email: str) -> List[BreachResult]:
        """Convenience method for email searches"""
        return await self.search(email, SearchType.EMAIL)
    
    async def search_username(self, username: str) -> List[BreachResult]:
        """Convenience method for username searches"""
        return await self.search(username, SearchType.USERNAME)
    
    async def search_ip(self, ip: str) -> List[BreachResult]:
        """Convenience method for IP searches"""
        return await self.search(ip, SearchType.IP)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Example usage
async def example_usage():
    """Example of how to use the SkidSearch client"""
    async with SkidSearchClient(session_cookie="your_session_cookie") as client:
        # Search for breaches by email
        results = await client.search_email("test@example.com")
        
        for breach in results:
            print(f"Source: {breach.source}")
            print(f"Date: {breach.date}")
            print(f"Data types: {', '.join(breach.data_types)}")
            print(f"Records: {breach.records}")
            print("-" * 50)


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
