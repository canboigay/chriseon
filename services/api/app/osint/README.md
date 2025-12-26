# OSINT Integration - BreachVIP

Comprehensive data breach search integration providing access to **10 billion records** across **1,000+ databases**.

## Overview

BreachVIP is a free database search engine that indexes breach data for security research and OSINT purposes. This integration provides:

- **10 billion individual records** indexed
- **1,000+ unique breach sources**
- **2 terabytes** of raw data
- Free API with rate limiting (15 requests/minute)
- Wildcard search support

### Supported Search Fields

- `email` - Email addresses
- `username` - Usernames
- `password` - Password hashes/plaintext
- `domain` - Domain names
- `ip` - IP addresses
- `phone` - Phone numbers
- `name` - Full names
- `uuid` - UUIDs
- `steamid` - Steam IDs
- `discordid` - Discord IDs

## API Endpoints

### Search Breach Data

**POST** `/v1/osint/breach/search`

```json
{
  "term": "admin@example.com",
  "fields": ["email"],
  "categories": null
}
```

**Response:**
```json
{
  "term": "admin@example.com",
  "fields": ["email"],
  "count": 3,
  "results": [
    {
      "source": "Collection #1",
      "categories": ["credential"],
      "data": {
        "email": "admin@example.com",
        "password": "hashed_password",
        "username": "admin"
      }
    }
  ]
}
```

### Quick Search Endpoints

**GET** `/v1/osint/breach/email/{email}`
**GET** `/v1/osint/breach/username/{username}`
**GET** `/v1/osint/breach/domain/{domain}`
**GET** `/v1/osint/breach/ip/{ip}`

### List Available Fields

**GET** `/v1/osint/fields`

Returns all supported search fields.

## Wildcard Search

The API supports two wildcard operators:

- `*` - Matches zero or more characters
- `?` - Matches exactly one character

**Examples:**
- `admin@*.com` - All admin emails on any .com domain
- `test?@example.com` - test1@, test2@, etc.
- `*@company.com` - All emails from company.com

**Note:** Wildcard queries cannot begin with `*` or `?`

## Rate Limiting

- **15 requests per minute** per IP
- Exceeding this limit results in a 1-minute block
- HTTP 429 (Too Many Requests) returned when rate limited
- Built-in automatic retry with backoff

## Python Client Usage

### Basic Search

```python
from app.osint import BreachVIPClient, SearchField

async with BreachVIPClient() as client:
    # Search by email
    results = await client.search_email("test@example.com")
    
    for result in results:
        print(f"Source: {result.source}")
        print(f"Data: {result.data}")
```

### Advanced Search

```python
# Multi-field search
results = await client.search(
    term="admin",
    fields=[SearchField.EMAIL, SearchField.USERNAME],
    categories=["minecraft"]
)

# Wildcard search
results = await client.search(
    term="*@company.com",
    fields=[SearchField.EMAIL]
)

# Domain search
results = await client.search_domain("example.com")
```

### Convenience Methods

```python
# Search by specific field type
email_results = await client.search_email("user@example.com")
username_results = await client.search_username("admin")
domain_results = await client.search_domain("company.com")
ip_results = await client.search_ip("192.168.1.1")
phone_results = await client.search_phone("+1234567890")
discord_results = await client.search_discord("123456789")
```

## Use Cases for Bug Bounty Research

### 1. Target Reconnaissance

```python
# Find all breaches related to a target domain
results = await client.search_domain("targetcompany.com")

# Discover email patterns
results = await client.search("*@targetcompany.com", [SearchField.EMAIL])
```

### 2. Credential Intelligence

```python
# Check if admin accounts have been breached
results = await client.search_username("admin")

# Find common password patterns for a target
results = await client.search(
    term="targetcompany.com",
    fields=[SearchField.EMAIL, SearchField.PASSWORD]
)
```

### 3. Infrastructure Mapping

```python
# Find IP addresses associated with breaches
results = await client.search_ip("203.0.113.0")

# Discover related infrastructure
results = await client.search_multi_field(
    "target_identifier",
    [SearchField.IP, SearchField.DOMAIN]
)
```

### 4. User Enumeration

```python
# Find usernames with patterns
results = await client.search("admin?", [SearchField.USERNAME])

# Discord/Gaming platforms
results = await client.search(
    term="targetuser",
    fields=[SearchField.DISCORDID, SearchField.STEAMID]
)
```

## Integration with Chriseon Orchestrator

The OSINT integration can enhance the AI orchestrator:

### Pre-Scan Intelligence

```python
# Before security testing, gather breach intelligence
async def pre_scan_intelligence(target_domain: str):
    async with BreachVIPClient() as client:
        breaches = await client.search_domain(target_domain)
        
    return {
        "breach_count": len(breaches),
        "sources": [b.source for b in breaches],
        "exposed_emails": [b.data.get("email") for b in breaches if "email" in b.data]
    }
```

### Context Enrichment

Add breach context to AI responses for better security insights.

### Automated Monitoring

```python
# Monitor for new breaches
async def monitor_target(domain: str):
    async with BreachVIPClient() as client:
        results = await client.search_domain(domain)
        
    # Store and compare with previous results
    # Alert on new breaches
```

## Error Handling

```python
try:
    results = await client.search_email("test@example.com")
except ValueError as e:
    # Bad request (invalid parameters)
    print(f"Invalid request: {e}")
except Exception as e:
    # Server error or rate limit
    print(f"Search failed: {e}")
```

## Best Practices

1. **Respect Rate Limits** - Built-in rate limiting enforces 15 req/min
2. **Use Specific Searches** - Narrow down fields for better performance
3. **Handle Empty Results** - Not all queries will return matches
4. **Cache Results** - Store frequently accessed breach data
5. **Ethical Use Only** - Only use for authorized security research

## API Reference

Full API documentation: https://breach.vip/api/docs

## Ethical & Legal Notice

- Use only for authorized security research
- Follow bug bounty program rules
- Never use for harassment or illegal activities
- Respect BreachVIP's Terms of Service
- Implement proper data handling and privacy practices

## Related Tools

- **HaveIBeenPwned** - Troy Hunt's breach notification service
- **DeHashed** - Commercial breach search
- **Intelligence X** - Dark web and breach search
- **Snusbase** - Premium breach database

## Support

- BreachVIP FAQ: https://breach.vip/faq
- API Docs: https://breach.vip/api/docs
- Issues: Report in Chriseon project

---

**Note:** This integration is for the FREE tier of BreachVIP. No API key required, but rate limiting applies.
