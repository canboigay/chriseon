"""
OSINT (Open Source Intelligence) integrations

Provides clients for various OSINT data sources:
- BreachVIP: Data breach search (10B+ records, 1000+ databases)
"""

from app.osint.breach_vip import BreachVIPClient, SearchField, BreachResult

__all__ = ["BreachVIPClient", "SearchField", "BreachResult"]
