# Chriseon Code Review & Recommendations

## Executive Summary

**Overall Assessment:** Solid MVP foundation with clean architecture. Several security, performance, and scalability issues need addressing before production.

**Priority Levels:**
- 🔴 Critical - Must fix before production
- 🟡 High - Fix soon, impacts quality/security
- 🟢 Medium - Improve when convenient

---

## 🔴 Critical Issues

### 1. **Security: datetime.utcnow() Deprecated**
**Files:** `models.py`, `jobs.py`
```python
# ❌ PROBLEMATIC
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

# ✅ FIX
from datetime import datetime, timezone
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```
**Impact:** `datetime.utcnow()` is deprecated in Python 3.12+ and returns timezone-naive datetime with timezone-aware column.

### 2. **Security: No Input Validation on Context Fetching**
**File:** `worker/context.py`
```python
# ❌ PROBLEMATIC - Can fetch any URL
resp = requests.get(url, timeout=10, allow_redirects=True)
```

**Risks:**
- SSRF (Server-Side Request Forgery) attacks
- Can access internal services (localhost, 192.168.x.x, etc.)
- Can be used to port scan internal network
- No size limits on responses

**Fix:**
```python
import ipaddress
from urllib.parse import urlparse

BLOCKED_CIDRS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),  # Link-local
]

MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB

def _is_safe_url(url: str) -> bool:
    """Block internal/private IPs"""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Resolve hostname
        import socket
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        
        # Check if IP is in blocked ranges
        for cidr in BLOCKED_CIDRS:
            if ip_obj in cidr:
                return False
        
        return True
    except:
        return False

# In extract_and_fetch_context:
if not _is_safe_url(url):
    print(f"Blocked unsafe URL: {url}")
    continue

# Add streaming with size limit
resp = requests.get(
    url,
    timeout=10,
    stream=True,
    headers={"user-agent": "chriseon/0.1"}
)
content = b""
for chunk in resp.iter_content(chunk_size=8192):
    content += chunk
    if len(content) > MAX_CONTENT_SIZE:
        raise ValueError(f"Response too large (> {MAX_CONTENT_SIZE} bytes)")
```

### 3. **Security: No Rate Limiting on API Endpoints**
**Impact:** Vulnerable to DoS attacks, API abuse, excessive costs from AI providers.

**Fix:** Add rate limiting middleware:
```python
# services/api/requirements.txt
slowapi==0.1.9

# services/api/app/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

def create_app() -> FastAPI:
    app = FastAPI(title="chriseon-api")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # In routes:
    @router.post("/runs")
    @limiter.limit("10/minute")  # 10 runs per minute per IP
    def create_run(request: Request, body: RunCreateRequest):
        ...
```

### 4. **Database: No Connection Pooling Configuration**
**File:** `db.py`
```python
# ❌ Current - uses defaults which may not be optimal
return create_engine(settings.database_url, pool_pre_ping=True)

# ✅ Better
return create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,          # Max connections in pool
    max_overflow=20,       # Extra connections beyond pool_size
    pool_recycle=3600,     # Recycle connections after 1 hour
    pool_timeout=30,       # Timeout for getting connection from pool
)
```

---

## 🟡 High Priority Issues

### 5. **Error Handling: Subprocess Crashes Not Logged Properly**
**File:** `jobs.py:92`
```python
# ❌ PROBLEMATIC
except Exception:
    code = p.exitcode
    return "", {}, f"provider process exited unexpectedly (exitcode={code})"
```

**Issues:**
- No logging of actual error
- No stack trace
- Hard to debug production issues

**Fix:**
```python
import logging
logger = logging.getLogger(__name__)

except Exception as e:
    code = p.exitcode
    logger.error(
        f"Provider process crashed",
        extra={
            "provider": provider,
            "model": model,
            "exitcode": code,
            "exception": str(e)
        },
        exc_info=True
    )
    return "", {}, f"provider process exited unexpectedly (exitcode={code})"
```

### 6. **Performance: N+1 Query in Artifacts Endpoint**
**File:** `routes/runs.py:77-92`
```python
# ❌ PROBLEMATIC - Separate queries for artifacts and scores
artifacts = session.query(Artifact).filter(...).all()
artifact_ids = [a.id for a in artifacts]
scores = session.query(Score).filter(Score.artifact_id.in_(artifact_ids)).all()

# ✅ Better - Single query with JOIN
from sqlalchemy.orm import joinedload

artifacts = (
    session.query(Artifact)
    .options(joinedload(Artifact.score))  # Eager load scores
    .filter(Artifact.run_id == run_uuid)
    .order_by(Artifact.pass_index.asc())
    .all()
)

# Then access artifact.score directly
```

### 7. **Scoring: Placeholder Algorithm Not Production-Ready**
**File:** `scoring.py`
```python
# Current scoring is too simplistic:
- Only counts words
- Basic heuristics for "brief" and "list"
- No actual quality assessment
```

**Recommendation:** Implement LLM-as-judge or use structured evaluation:
```python
async def compute_score_with_llm(
    instructions: str,
    output_text: str,
    reference_outputs: list[str],  # Other model outputs for comparison
) -> ScoreResult:
    """
    Use a judge LLM (e.g., GPT-4) to score outputs on:
    - Factual accuracy (vs reference materials)
    - Instruction adherence
    - Completeness
    - Clarity/coherence
    """
    judge_prompt = f"""
    Evaluate this AI response on a 0-1 scale for each dimension:
    
    Instructions: {instructions}
    Response: {output_text}
    
    Rate on:
    1. Factual Accuracy (0-1)
    2. Instruction Adherence (0-1)
    3. Completeness (0-1)
    4. Clarity (0-1)
    
    Return JSON: {{"scores": {{"factual": 0.8, ...}}, "notes": "..."}}
    """
    # Call cheap judge model (gpt-4o-mini, claude-haiku, etc.)
```

### 8. **Frontend: No Loading States During Streaming**
**File:** `page.tsx`
- Currently just disables submit button
- No progress indication
- User can't see which model is running

**Recommendation:** Add real-time SSE updates:
```typescript
// In /runs/[id] page
useEffect(() => {
  const eventSource = new EventSource(`${API_BASE}/v1/runs/${id}/events`);
  
  eventSource.addEventListener('artifact.started', (e) => {
    const data = JSON.parse(e.data);
    setCurrentArtifact(data.model_id);
  });
  
  eventSource.addEventListener('artifact.created', (e) => {
    // Show completion animation
  });
  
  return () => eventSource.close();
}, [id]);
```

### 9. **OSINT Integration: No Caching**
**File:** `osint/breach_vip.py`
- Hitting rate limits quickly (15 req/min)
- Same queries repeated across runs
- No persistent storage

**Fix:**
```python
import redis
from datetime import timedelta

class BreachVIPClient:
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client
        self.cache_ttl = timedelta(hours=24)
    
    async def search(self, term: str, fields: list[SearchField]) -> list[BreachResult]:
        # Check cache first
        cache_key = f"breach:{term}:{':'.join(sorted(f.value for f in fields))}"
        
        if self.redis:
            cached = self.redis.get(cache_key)
            if cached:
                return [BreachResult(**r) for r in json.loads(cached)]
        
        # Make API call
        results = await self._api_search(term, fields)
        
        # Cache results
        if self.redis and results:
            self.redis.setex(
                cache_key,
                int(self.cache_ttl.total_seconds()),
                json.dumps([r.dict() for r in results])
            )
        
        return results
```

---

## 🟢 Medium Priority Improvements

### 10. **Observability: No Structured Logging**
Add structured logging with context:
```python
# Add to main.py
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### 11. **Testing: No Tests**
Critical gaps:
- No unit tests for scoring logic
- No integration tests for API endpoints
- No tests for OSINT client
- No tests for encryption/decryption

**Add:**
```bash
# services/api/requirements-dev.txt
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.27.2  # For testing async endpoints

# Run tests
pytest services/api/tests/ -v --cov=app
```

### 12. **Configuration: Environment Variables Scattered**
Create centralized config validation:
```python
# services/api/app/config.py
from pydantic import Field, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Core
    env: str = Field(default="dev")
    debug: bool = Field(default=False)
    
    # Database
    database_url: str
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=20)
    
    # Redis
    redis_url: str
    redis_max_connections: int = Field(default=50)
    
    # Security
    key_encryption_master_key_b64: str
    cors_origins: list[str] = Field(default_factory=list)
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_runs_per_minute: int = Field(default=10)
    
    # Context Fetching
    context_fetch_enabled: bool = Field(default=True)
    context_fetch_timeout: int = Field(default=10)
    context_fetch_max_size: int = Field(default=5242880)  # 5MB
    
    @validator('key_encryption_master_key_b64')
    def validate_encryption_key(cls, v):
        import base64
        try:
            decoded = base64.b64decode(v)
            if len(decoded) != 32:
                raise ValueError("Must be 32 bytes")
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")
        return v
```

### 13. **API Documentation: No OpenAPI Customization**
```python
# In main.py
app = FastAPI(
    title="Chriseon API",
    description="Multi-model AI orchestrator with OSINT integration",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "runs", "description": "AI orchestration runs"},
        {"name": "osint", "description": "OSINT data breach searches"},
        {"name": "settings", "description": "API key management"},
    ]
)

# Add examples to schemas
class RunCreateRequest(BaseModel):
    query: str = Field(
        min_length=1,
        example="Explain quantum computing in simple terms"
    )
    # ...
```

### 14. **Worker: No Graceful Shutdown**
```python
# services/worker/worker/__main__.py
import signal
import sys

def signal_handler(sig, frame):
    print('Graceful shutdown initiated...')
    # Finish current jobs
    # Close connections
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

### 15. **Multiprocessing: Context Spawn May Fail on Some Systems**
**File:** `jobs.py:72`
```python
ctx = mp.get_context("spawn")  # Works on macOS, may have issues elsewhere
```

**Better:**
```python
import sys

# Use appropriate context based on platform
if sys.platform == "darwin":  # macOS
    ctx = mp.get_context("spawn")
elif sys.platform == "win32":  # Windows
    ctx = mp.get_context("spawn")
else:  # Linux
    ctx = mp.get_context("forkserver")  # More stable than fork
```

---

## 📊 Architecture Improvements

### 16. **Add Health Checks with Dependencies**
```python
# routes/health.py
from sqlalchemy import text
from redis import Redis

@router.get("/health/live")
def liveness():
    """Basic liveness check"""
    return {"status": "ok"}

@router.get("/health/ready")
def readiness():
    """Readiness check - verify all dependencies"""
    checks = {}
    
    # Check database
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    
    # Check Redis
    try:
        r = Redis.from_url(get_settings().redis_url)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
    
    # Check worker queue
    try:
        q = get_queue("default")
        checks["queue"] = f"ok ({len(q)} jobs)"
    except Exception as e:
        checks["queue"] = f"error: {e}"
    
    all_ok = all(v == "ok" or v.startswith("ok (") for v in checks.values())
    status_code = 200 if all_ok else 503
    
    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=status_code
    )
```

### 17. **Add Metrics/Monitoring Hooks**
```python
# Add Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest

run_counter = Counter('chriseon_runs_total', 'Total runs', ['status', 'provider'])
run_duration = Histogram('chriseon_run_duration_seconds', 'Run duration')
api_requests = Counter('chriseon_api_requests_total', 'API requests', ['endpoint', 'method', 'status'])

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 18. **Add Database Migrations**
Currently using `Base.metadata.create_all()` which doesn't handle schema changes.

**Use Alembic:**
```bash
pip install alembic
alembic init migrations

# Create migration
alembic revision --autogenerate -m "initial schema"

# Apply
alembic upgrade head
```

---

## 🎯 Feature Enhancements

### 19. **Add Retry Logic for Provider Calls**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def _generate_with_retry(provider, model, instructions, user_input, api_key):
    return _generate_with_timeout(...)
```

### 20. **Add Cost Tracking**
```python
# In models.py
class Run(Base):
    # ... existing fields
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

# In jobs.py after each generation
COST_PER_1K_TOKENS = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    # ...
}

def calculate_cost(model_id: str, usage: dict) -> float:
    rates = COST_PER_1K_TOKENS.get(model_id, {"input": 0, "output": 0})
    input_tokens = usage.get("prompt_tokens", 0) / 1000
    output_tokens = usage.get("completion_tokens", 0) / 1000
    return (input_tokens * rates["input"]) + (output_tokens * rates["output"])
```

---

## 📝 Documentation Needs

1. **API Documentation** - Add OpenAPI examples and descriptions
2. **Architecture Diagram** - Show data flow between components
3. **Deployment Guide** - Production deployment instructions
4. **Security Best Practices** - Key management, network security
5. **Development Guide** - How to add new providers, extend scoring

---

## Summary of Recommendations

**Immediate Actions (Before Production):**
1. Fix datetime.utcnow() deprecation
2. Add SSRF protection to context fetching
3. Implement rate limiting
4. Add proper error logging
5. Fix N+1 query in artifacts endpoint

**Next Sprint:**
1. Add caching for OSINT
2. Implement proper LLM-based scoring
3. Add comprehensive tests
4. Set up structured logging
5. Add health checks with dependencies

**Future Enhancements:**
1. Database migrations with Alembic
2. Metrics/monitoring
3. Cost tracking
4. Retry logic for providers
5. Graceful shutdown handling

The codebase has a solid foundation with clean architecture patterns. Focus on security and observability improvements before scaling.
