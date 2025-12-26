# SkidSearch Integration

Integration client for SkidSearch OSINT platform for data breach lookups.

## Setup

### 1. Capture API Details from Browser

Since SkidSearch requires authentication and we need to reverse-engineer their API:

1. **Open SkidSearch in your browser** (https://www.skidsearch.xyz)
2. **Open Developer Tools** (Cmd+Option+I on Mac, F12 on Windows/Linux)
3. **Go to the Network tab**
4. **Perform a search** (email, username, IP, etc.)
5. **Look for API requests**:
   - Filter by `XHR` or `Fetch` requests
   - Find requests that contain search results
   - Note the:
     - **Endpoint URL** (e.g., `/api/search`, `/api/lookup`)
     - **Request method** (GET, POST)
     - **Request headers** (especially `Authorization` or `Cookie`)
     - **Request parameters** or body
     - **Response format**

### 2. Extract Authentication

In the Network tab, look at the **Request Headers** for any search request:

**Option A: Session Cookie**
```
Cookie: session=abc123...; other_cookie=xyz...
```

**Option B: API Key/Bearer Token**
```
Authorization: Bearer sk_live_abc123...
```

Copy the full cookie string or token.

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# SkidSearch Authentication
SKIDSEARCH_API_KEY=your_api_key_if_available
SKIDSEARCH_SESSION=your_full_cookie_string
```

### 4. Update the Client

Once you have the actual API structure, update `skidsearch_client.py`:

- Update the `endpoint` in the `search()` method
- Adjust request parameters/body format
- Update `_parse_results()` to match actual response format

## Usage

```python
from integrations.skidsearch_client import SkidSearchClient, SearchType

async def search_breach():
    async with SkidSearchClient() as client:
        # Search by email
        results = await client.search_email("test@example.com")
        
        for breach in results:
            print(f"Found in: {breach.source}")
            print(f"Date: {breach.date}")
            print(f"Exposed data: {breach.data_types}")
```

## API Structure Discovery

### Common API Patterns

**Pattern 1: RESTful API**
```
GET /api/search?query=email@example.com&type=email
POST /api/lookup
{
  "query": "email@example.com",
  "type": "email"
}
```

**Pattern 2: GraphQL**
```
POST /graphql
{
  "query": "{ search(query: \"email@example.com\") { source date data } }"
}
```

**Pattern 3: Simple endpoints**
```
GET /search/email/email@example.com
GET /lookup?q=email@example.com
```

### Response Format Examples

**JSON Response**
```json
{
  "results": [
    {
      "source": "Database Leak 2023",
      "breach_date": "2023-05-15",
      "data_types": ["email", "password", "username"],
      "data": {
        "email": "test@example.com",
        "username": "testuser",
        "password_hash": "..."
      }
    }
  ],
  "count": 1
}
```

## Integration with Chriseon

This can be integrated into the Chriseon orchestrator as:

1. **Pre-scan intelligence** - Gather breach data before security testing
2. **Context enrichment** - Add breach context to AI responses
3. **Automated monitoring** - Track new breaches for targets
4. **Report generation** - Include breach history in security reports

## Ethical & Legal Notice

- Only use for authorized security research
- Respect SkidSearch's Terms of Service
- Follow bug bounty program rules
- Never use for harassment or illegal activities
- Implement proper rate limiting to avoid service disruption
