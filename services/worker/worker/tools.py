"""
Tool System for Model Function Calling

Provides tools that models can call during refinement:
- Web search (DuckDuckGo, Google-like results)
- URL fetching (get content from specific URLs)
- OSINT breach search (BreachVIP integration)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tool definitions in OpenAI function calling format
# (compatible with Anthropic and Gemini with minor adaptations)
AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information. Use this when you need to research a topic, find recent data, or verify facts. Returns snippets and URLs from search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific and concise."
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 10)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and extract text content from a specific URL. Use this to read articles, documentation, or web pages. Returns cleaned text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to fetch (must start with http:// or https://)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "breach_search",
            "description": "Search data breach databases for exposed credentials, emails, or usernames. Use for security research or OSINT investigations. Returns breach sources and exposed data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Email, username, or identifier to search for"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["email", "username", "domain", "ip"],
                        "description": "Type of identifier being searched"
                    }
                },
                "required": ["term", "search_type"]
            }
        }
    }
]


def web_search(query: str, num_results: int = 5) -> dict[str, Any]:
    """
    Search the web using DuckDuckGo HTML scraping
    
    Returns:
        {
            "results": [
                {"title": "...", "snippet": "...", "url": "..."},
                ...
            ],
            "query": "original query"
        }
    """
    try:
        num_results = min(num_results, 10)  # Cap at 10
        
        # Use DuckDuckGo HTML (doesn't require API key)
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        results = []
        for result_div in soup.find_all("div", class_="result", limit=num_results):
            title_tag = result_div.find("a", class_="result__a")
            snippet_tag = result_div.find("a", class_="result__snippet")
            
            if title_tag:
                title = title_tag.get_text(strip=True)
                url = title_tag.get("href", "")
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "url": url
                })
        
        return {
            "results": results,
            "query": query,
            "count": len(results)
        }
    
    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)
        return {
            "error": f"Search failed: {str(e)}",
            "query": query,
            "results": []
        }


def fetch_url(url: str) -> dict[str, Any]:
    """
    Fetch content from a URL (with SSRF protection)
    
    Returns:
        {
            "url": "...",
            "title": "...",
            "content": "extracted text...",
            "length": 1234
        }
    """
    try:
        # Import SSRF protection from context module
        import ipaddress
        import socket
        from urllib.parse import urlparse
        
        # SSRF check
        BLOCKED_CIDRS = [
            ipaddress.ip_network('10.0.0.0/8'),
            ipaddress.ip_network('172.16.0.0/12'),
            ipaddress.ip_network('192.168.0.0/16'),
            ipaddress.ip_network('127.0.0.0/8'),
            ipaddress.ip_network('169.254.0.0/16'),
        ]
        
        parsed = urlparse(url)
        if not parsed.hostname:
            return {"error": "Invalid URL", "url": url}
        
        try:
            ip_str = socket.gethostbyname(parsed.hostname)
            ip_obj = ipaddress.ip_address(ip_str)
            
            for cidr in BLOCKED_CIDRS:
                if ip_obj in cidr:
                    return {"error": "Cannot fetch internal/private URLs", "url": url}
        except socket.gaierror:
            return {"error": "Could not resolve hostname", "url": url}
        
        # Fetch with size limit
        MAX_SIZE = 2 * 1024 * 1024  # 2MB for tool calls
        
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ChriseonBot/1.0)"},
            timeout=10,
            stream=True
        )
        resp.raise_for_status()
        
        content = b""
        for chunk in resp.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_SIZE:
                content = content[:MAX_SIZE]
                break
        
        text = content.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(text, "html.parser")
        
        # Remove scripts, styles, etc
        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.extract()
        
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""
        
        clean_text = soup.get_text(separator=" ", strip=True)
        # Truncate to reasonable length
        clean_text = clean_text[:10000]
        
        return {
            "url": url,
            "title": title_text,
            "content": clean_text,
            "length": len(clean_text)
        }
    
    except Exception as e:
        logger.error(f"URL fetch failed for {url}: {e}", exc_info=True)
        return {
            "error": f"Failed to fetch: {str(e)}",
            "url": url
        }


def breach_search(term: str, search_type: str) -> dict[str, Any]:
    """
    Search breach databases (placeholder - actual implementation would call BreachVIP)
    
    Returns:
        {
            "term": "...",
            "search_type": "...",
            "results": [
                {"source": "...", "data": {...}},
                ...
            ]
        }
    """
    try:
        # For now, return a note that this requires runtime access
        # In actual execution, this would be replaced with BreachVIP API call
        return {
            "term": term,
            "search_type": search_type,
            "note": "OSINT search requires runtime API access - contact system admin",
            "results": []
        }
    
    except Exception as e:
        logger.error(f"Breach search failed: {e}", exc_info=True)
        return {
            "error": f"Search failed: {str(e)}",
            "term": term,
            "results": []
        }


# Tool registry - maps function names to implementations
TOOL_FUNCTIONS: dict[str, Callable] = {
    "web_search": web_search,
    "fetch_url": fetch_url,
    "breach_search": breach_search,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a tool by name with given arguments
    
    Args:
        name: Tool function name
        arguments: Arguments to pass to the tool
        
    Returns:
        Tool execution result
    """
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    
    try:
        func = TOOL_FUNCTIONS[name]
        result = func(**arguments)
        return result
    except Exception as e:
        logger.error(f"Tool execution failed: {name}({arguments}): {e}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}


def format_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    """
    Format tool result as readable text for model context
    
    Args:
        tool_name: Name of tool that was executed
        result: Result from tool execution
        
    Returns:
        Formatted string for model consumption
    """
    if "error" in result:
        return f"[{tool_name} Error] {result['error']}"
    
    if tool_name == "web_search":
        if not result.get("results"):
            return f"[Web Search] No results found for: {result.get('query', '')}"
        
        output = f"[Web Search Results for: {result.get('query', '')}]\n\n"
        for i, r in enumerate(result["results"], 1):
            output += f"{i}. {r['title']}\n"
            output += f"   {r['snippet']}\n"
            output += f"   URL: {r['url']}\n\n"
        return output.strip()
    
    elif tool_name == "fetch_url":
        return f"[URL Content: {result.get('url', '')}]\nTitle: {result.get('title', 'N/A')}\n\n{result.get('content', '')}"
    
    elif tool_name == "breach_search":
        if not result.get("results"):
            return f"[Breach Search] No breaches found for: {result.get('term', '')}"
        
        output = f"[Breach Search for: {result.get('term', '')}]\n\n"
        for r in result["results"]:
            output += f"- Source: {r.get('source', 'Unknown')}\n"
            output += f"  Data: {json.dumps(r.get('data', {}), indent=2)}\n\n"
        return output.strip()
    
    else:
        return f"[{tool_name}]\n{json.dumps(result, indent=2)}"
