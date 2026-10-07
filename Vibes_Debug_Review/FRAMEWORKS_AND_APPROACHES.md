# Frameworks & Architectural Approaches for Claudey

## Table of Contents
1. [Current Architecture Analysis](#current-architecture-analysis)
2. [Recommended Frameworks](#recommended-frameworks)
3. [Architectural Patterns](#architectural-patterns)
4. [Migration Strategies](#migration-strategies)
5. [Implementation Roadmap](#implementation-roadmap)

---

## Current Architecture Analysis

### Strengths

```
┌─────────────────────────────────────────────────────────────┐
│                    Claudey Architecture                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Phase 1    │    │   Phase 2    │    │   Phase 3    │  │
│  │ Seed Verify  │───▶│ Board Pulls  │───▶│ Discovery    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│           │                 │                 │              │
│           └────────────────┼────────────────┘              │
│                            ▼                                      │
│                    ┌──────────────┐                            │
│                    │   Phase 4    │                            │
│                    │  Scoring     │                            │
│                    └──────────────┘                            │
│                            ▼                                      │
│                    ┌──────────────┐                            │
│                    │   Phase 5    │                            │
│                    │   Output     │                            │
│                    └──────────────┘                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    Shared Components                       ││
│  ├──────────  ├──────────  ├──────────  ├────────────────┤│
│  │  http.py   │  config.py │  models.py │   db.py (SQLite)  ││
│  │  (Core)    │  (Config)  │  (Models)  │   (Persistence)    ││
│  └──────────  └──────────  └──────────  └────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘

Key Strengths:
✓ Clear phase separation
✓ Shared HTTP client with rate limiting
✓ Centralized configuration
✓ Type hints (Pydantic models)
✓ SQLite for working data
✓ File-based caching
✓ Respects robots.txt
✓ Cross-process rate limiting
```

### Limitations

```
⚠️ Issues:
  • Sequential processing in critical paths
  • No async/await support
  • Limited error propagation
  • No circuit breakers
  • Basic logging
  • Hardcoded ATS adapters
  • No plugin system
  • Tight coupling between phases
  • No distributed processing
  • Limited test coverage for core components
```

---

## Recommended Frameworks

### 1. Async HTTP: **aiohttp**

**Why:** Replace `httpx` with `aiohttp` for async HTTP requests

**Benefits:**
- Non-blocking I/O
- Better performance for many concurrent requests
- Native async/await support
- Better resource utilization

**Implementation:**

```python
# radar/async_http.py
import aiohttp
import asyncio
from typing import AsyncIterator

class AsyncPoliteClient:
    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.semaphores: dict[str, asyncio.Semaphore] = {}
        self.lock = asyncio.Lock()
    
    async def get(self, url: str) -> aiohttp.ClientResponse:
        host = url.split('/')[2]
        
        # Rate limiting per host
        async with self.lock:
            if host not in self.semaphores:
                self.semaphores[host] = asyncio.Semaphore(1)
        
        semaphore = self.semaphores[host]
        
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return response
    
    async def close(self):
        for semaphore in self.semaphores.values():
            # Clean up semaphores
            pass

# Usage
async def async_verify_urls(urls: list[str]) -> list:
    client = AsyncPoliteClient()
    tasks = [client.get(url) for url in urls]
    return await asyncio.gather(*tasks)
```

**Migration Path:**
1. Create `async_http.py` alongside `http.py`
2. Gradually migrate ATS adapters to async
3. Update pipeline to use async where beneficial
4. Keep sync HTTP for compatibility

---

### 2. Task Queue: **Celery** or **RQ**

**Why:** Enable distributed processing and better job management

**Benefits:**
- Distributed workers
- Job retries with backoff
- Result storage
- Monitoring and metrics
- Priority queues

**Implementation with Celery:**

```python
# radar/celery_app.py
from celery import Celery
from . import config

app = Celery(
    'radar',
    broker=config.CELERY_BROKER_URL or 'redis://localhost:6379/0',
    backend=config.CELERY_RESULT_BACKEND or 'redis://localhost:6379/1',
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@app.task(bind=True, max_retries=3)
def verify_url_task(self, url: str, company: str):
    from .verify import verify_url
    try:
        return verify_url(url, company).model_dump()
    except Exception as e:
        self.retry(exc=e, countdown=60)

@app.task
 def pull_board_task(ats: str, slug: str, company: str):
    from .phase2 import pull
    status, postings = pull(ats, slug, company, "")
    return {
        'status': status,
        'postings': [p.model_dump() for p in postings],
    }
```

**Implementation with RQ (Simpler):**

```python
# radar/rq_worker.py
from redis import Redis
from rq import Worker, Queue, Connection
from . import config

listen = ['default']
redis_url = config.REDIS_URL or 'redis://localhost:6379'
conn = Redis.from_url(redis_url)

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()

# radar/rq_tasks.py
from redis import Redis
from rq import Queue
from . import config

q = Queue(connection=Redis.from_url(config.REDIS_URL))

def enqueue_verify_url(url: str, company: str):
    from .verify import verify_url
    return q.enqueue(verify_url, url, company)

def enqueue_pull_board(ats: str, slug: str, company: str):
    from .phase2 import pull
    return q.enqueue(pull, ats, slug, company, "")
```

---

### 3. Dependency Injection: **dependency-injector**

**Why:** Decouple components and make testing easier

**Benefits:**
- Loose coupling
- Easy mocking for tests
- Clear dependencies
- Better testability

**Implementation:**

```python
# radar/container.py
from dependency_injector import containers, providers
from .http import PoliteClient
from . import config

class Container(containers.DeclarativeContainer):
    """Dependency injection container."""
    
    # Configuration
    config = providers.Configuration()
    
    # HTTP Client
    http_client = providers.Singleton(
        PoliteClient,
        use_cache=config.http.use_cache,
        cache_ttl_hours=config.http.cache_ttl,
    )
    
    # ATS Adapters
    greenhouse_adapter = providers.Factory(
        'radar.ats.greenhouse.GreenhouseAdapter',
        client=http_client,
    )
    
    # Services
    verification_service = providers.Factory(
        'radar.verify.VerificationService',
        client=http_client,
    )
    
    # Repositories
    posting_repository = providers.Factory(
        'radar.db.PostingRepository',
        conn=providers.Resource(db.conn),
    )
```

**Usage:**

```python
# In your code
def verify_seeds(container: Container):
    verifier = container.verification_service()
    http = container.http_client()
    
    # Use services
    results = verifier.verify_all(seeds)
    return results

# In tests
def test_verify_seeds():
    container = Container()
    container.config.from_dict({
        'http': {'use_cache': False},
    })
    
    # Override with mock
    container.http_client.override(providers.Object(MockClient()))
    
    results = verify_seeds(container)
    assert len(results) > 0
```

---

### 4. Event-Driven: **pydantic-events** or **faust**

**Why:** Decouple phases and enable real-time processing

**Benefits:**
- Loose coupling between components
- Real-time processing
- Better scalability
- Event sourcing capability

**Implementation with pydantic-events:**

```python
# radar/events.py
from pydantic import BaseModel
from pydantic_events import Event, EventDispatcher
from typing import Literal

class PostingFoundEvent(BaseModel):
    type: Literal['posting_found']
    posting: dict
    source: str
    timestamp: str

class PostingVerifiedEvent(BaseModel):
    type: Literal['posting_verified']
    posting: dict
    verification_result: str
    timestamp: str

class PostingScoredEvent(BaseModel):
    type: Literal['posting_scored']
    posting: dict
    score: int
    bucket: str
    timestamp: str

# Event dispatcher
class RadarEventDispatcher(EventDispatcher):
    def __init__(self):
        super().__init__()
        self.handlers: dict[str, list] = {}
    
    def register(self, event_type: str, handler):
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    async def dispatch(self, event: Event):
        for handler in self.handlers.get(event.type, []):
            await handler(event)

# Global dispatcher
dispatcher = RadarEventDispatcher()
```

**Usage:**

```python
# In phase2.py
from .events import dispatcher, PostingFoundEvent
from datetime import datetime

async def pull_board(ats: str, slug: str, company: str):
    status, postings = pull(ats, slug, company, "")
    
    for posting in postings:
        event = PostingFoundEvent(
            type='posting_found',
            posting=posting.model_dump(),
            source=f'board:{ats}',
            timestamp=datetime.utcnow().isoformat(),
        )
        await dispatcher.dispatch(event)
    
    return status, postings

# Register handler
async def log_posting(event: PostingFoundEvent):
    logger.info(f"Posting found: {event.posting['title']} from {event.source}")

dispatcher.register('posting_found', log_posting)
```

---

### 5. Plugin System: **pluggy** or **importlib-metadata**

**Why:** Make ATS adapters and discovery channels pluggable

**Benefits:**
- Easy to add new ATS adapters
- Easy to add new discovery channels
- Better separation of concerns
- Community contributions possible

**Implementation:**

```python
# radar/plugins.py
import importlib
import pkgutil
from typing import Protocol, runtime_checkable

@runtime_checkable
class ATSAdapterProtocol(Protocol):
    """Interface for ATS adapters."""
    
    @staticmethod
    def probe(slug: str) -> tuple[bool, int]:
        """Check if board exists and get job count."""
        ...
    
    @staticmethod
    def pull(slug: str, company: str, source: str) -> tuple[str, list]:
        """Pull all jobs from board."""
        ...
    
    @staticmethod
    def verify(board: str, job_id: str, company: str, source: str) -> Posting | None:
        """Verify a specific job."""
        ...

class PluginManager:
    def __init__(self):
        self.ats_adapters: dict[str, ATSAdapterProtocol] = {}
        self.discovery_channels: dict[str, any] = {}
        self._loaded = False
    
    def load_plugins(self):
        if self._loaded:
            return
        
        # Load built-in adapters
        self._load_builtin_ats()
        self._load_builtin_discovery()
        
        # Load external plugins
        self._load_external_plugins()
        
        self._loaded = True
    
    def _load_builtin_ats(self):
        from .ats import greenhouse, lever, ashby, workday
        self.ats_adapters['greenhouse'] = greenhouse
        self.ats_adapters['lever'] = lever
        self.ats_adapters['ashby'] = ashby
        self.ats_adapters['workday'] = workday
    
    def _load_builtin_discovery(self):
        from .discover import commoncrawl, websearch, hn, feeds
        self.discovery_channels['commoncrawl'] = commoncrawl
        self.discovery_channels['websearch'] = websearch
        self.discovery_channels['hn'] = hn
        self.discovery_channels['feeds'] = feeds
    
    def _load_external_plugins(self):
        """Load plugins from entry points."""
        try:
            from importlib.metadata import entry_points
            
            # Load ATS adapters
            for entry in entry_points(group='radar.ats_adapters'):
                self.ats_adapters[entry.name] = entry.load()
            
            # Load discovery channels
            for entry in entry_points(group='radar.discovery_channels'):
                self.discovery_channels[entry.name] = entry.load()
        except ImportError:
            # importlib.metadata not available (Python < 3.8)
            pass
    
    def get_ats_adapter(self, name: str):
        self.load_plugins()
        return self.ats_adapters.get(name)
    
    def get_discovery_channel(self, name: str):
        self.load_plugins()
        return self.discovery_channels.get(name)

# Global plugin manager
plugins = PluginManager()
```

**Plugin Definition (setup.py):**

```python
# For a new ATS adapter plugin
from setuptools import setup

setup(
    name='radar-ats-bamboohr',
    version='0.1.0',
    entry_points={
        'radar.ats_adapters': [
            'bamboohr = radar_ats_bamboohr:BambooHRAdapter',
        ],
    },
)
```

---

### 6. Configuration: **pydantic-settings**

**Why:** Better configuration management with validation

**Benefits:**
- Type-safe configuration
- Validation
- Multiple sources (env, file, CLI)
- Documentation

**Implementation:**

```python
# radar/config.py (enhanced)
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

class HTTPConfig(BaseSettings):
    timeout: float = 30.0
    max_retries: int = 4
    min_delay: float = 1.0
    user_agent: str = "JobRadar/0.1"
    cache_ttl_hours: float = 20.0
    robots_exempt_hosts: set[str] = set()

class CacheConfig(BaseSettings):
    dir: Path = Path("cache")
    http_ttl_hours: float = 20.0
    max_size_mb: int = 1000

class ATSConfig(BaseSettings):
    greenhouse_api_key: Optional[str] = None
    workday_username: Optional[str] = None
    workday_password: Optional[str] = None

class DatabaseConfig(BaseSettings):
    path: Path = Path("data/jobs.sqlite")
    journal_mode: str = "WAL"

class PipelineConfig(BaseSettings):
    channel_timeout: int = 3000  # 50 minutes
    max_workers: int = 10
    batch_size: int = 20

class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )
    
    # Sub-configurations
    http: HTTPConfig = HTTPConfig()
    cache: CacheConfig = CacheConfig()
    ats: ATSConfig = ATSConfig()
    db: DatabaseConfig = DatabaseConfig()
    pipeline: PipelineConfig = PipelineConfig()
    
    # Root directory
    root: Path = Path(__file__).resolve().parent.parent
    
    @property
    def DATA(self) -> Path:
        return self.root / "data"
    
    @property
    def OUT(self) -> Path:
        return self.root / "out"
    
    @property
    def CACHE(self) -> Path:
        return self.root / "cache"
    
    @property
    def USER_AGENT(self) -> str:
        contact = self.http.user_agent
        if self.ats.greenhouse_api_key:
            contact += f" (gh:{self.ats.greenhouse_api_key[:8]}...)"
        return contact

# Global config instance
config = Config()
```

---

### 7. Monitoring: **Prometheus** + **Grafana**

**Why:** Track system health and performance

**Benefits:**
- Real-time monitoring
- Historical metrics
- Alerting
- Performance insights

**Implementation:**

```python
# radar/monitoring.py
from prometheus_client import start_http_server, Counter, Histogram, Gauge
import time

# Metrics definitions
REQUEST_COUNT = Counter(
    'radar_http_requests_total',
    'Total HTTP requests',
    ['method', 'host', 'status'],
)
REQUEST_DURATION = Histogram(
    'radar_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'host'],
)
POSTINGS_FOUND = Counter(
    'radar_postings_found_total',
    'Total postings found',
    ['source', 'bucket'],
)
POSTINGS_PROCESSED = Counter(
    'radar_postings_processed_total',
    'Total postings processed',
    ['phase'],
)
ACTIVE_WORKERS = Gauge(
    'radar_active_workers',
    'Number of active workers',
)

class MonitoredHTTPClient:
    """HTTP client with Prometheus metrics."""
    
    def __init__(self, client):
        self.client = client
    
    def get(self, url: str, **kwargs):
        method = 'GET'
        host = url.split('/')[2]
        
        with REQUEST_DURATION.labels(method, host).time():
            start = time.time()
            try:
                result = self.client.get(url, **kwargs)
                REQUEST_COUNT.labels(method, host, result.status or 'error').inc()
                return result
            except Exception as e:
                REQUEST_COUNT.labels(method, host, 'exception').inc()
                raise
    
    # Implement other methods similarly...

def start_monitoring(port: int = 8000):
    """Start Prometheus metrics server."""
    start_http_server(port)
    print(f"Prometheus metrics server started on port {port}")
```

**Grafana Dashboard:**

```yaml
# Example Grafana dashboard configuration
dashboard:
  title: "Claudey Job Radar"
  panels:
    - title: "HTTP Requests"
      type: graph
      targets:
        - expr: "rate(radar_http_requests_total[1m])"
          legend: "{{host}}"
    
    - title: "Request Duration"
      type: graph
      targets:
        - expr: "histogram_quantile(0.95, sum(rate(radar_http_request_duration_seconds_bucket[5m])) by (le, host))"
          legend: "{{host}} p95"
    
    - title: "Postings by Source"
      type: pie
      targets:
        - expr: "sum(radar_postings_found_total) by (source)"
    
    - title: "Postings by Bucket"
      type: pie
      targets:
        - expr: "sum(radar_postings_found_total) by (bucket)"
```

---

## Architectural Patterns

### 1. Repository Pattern

**Current:** Direct database access in business logic
**Proposed:** Repository layer for data access

```python
# radar/repositories/posting_repository.py
from typing import Optional, list
from ..models import Posting
from .. import db

class PostingRepository:
    def __init__(self, conn):
        self.conn = conn
    
    def get_by_key(self, key: str) -> Optional[Posting]:
        return db.get_posting(key)
    
    def get_by_dedupe_key(self, dedupe_key: str) -> list[Posting]:
        rows = self.conn.execute(
            "SELECT data FROM postings WHERE dedupe_key=?",
            (dedupe_key,)
        ).fetchall()
        return [Posting.model_validate_json(row['data']) for row in rows]
    
    def save(self, posting: Posting) -> None:
        db.upsert_posting(posting)
    
    def delete(self, key: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM postings WHERE key=?", (key,))
        return cursor.rowcount > 0
    
    def search(self, company: str = None, title: str = None) -> list[Posting]:
        # Implement search logic
        ...
```

### 2. Service Pattern

**Current:** Functions with side effects
**Proposed:** Stateless services

```python
# radar/services/verification_service.py
from typing import Protocol
from ..models import Posting
from ..repositories import PostingRepository

class VerificationService:
    def __init__(self, repository: PostingRepository, client):
        self.repository = repository
        self.client = client
    
    def verify_url(self, url: str, company: str, source: str) -> Outcome:
        # Implementation
        ...
    
    def verify_all(self, urls: list[tuple[str, str]]) -> list[Outcome]:
        return [self.verify_url(url, company, source) for url, company, source in urls]
    
    def verify_board(self, ats: str, board: str, company: str) -> list[Posting]:
        # Implementation
        ...
```

### 3. Factory Pattern

**Current:** Direct instantiation of adapters
**Proposed:** Factory for creating adapters

```python
# radar/factories/ats_factory.py
from typing import Protocol
from ..plugins import plugins

class ATSFactory:
    def __init__(self):
        self.plugins = plugins
    
    def create(self, ats_type: str, **kwargs):
        adapter_class = self.plugins.get_ats_adapter(ats_type)
        if adapter_class is None:
            raise ValueError(f"Unknown ATS type: {ats_type}")
        return adapter_class(**kwargs)
    
    def get_supported_types(self) -> list[str]:
        return list(self.plugins.ats_adapters.keys())

# Usage
factory = ATSFactory()
adapter = factory.create('greenhouse', api_key='...')
```

### 4. Strategy Pattern

**Current:** Conditional logic for different ATS types
**Proposed:** Strategy pattern for interchangeable algorithms

```python
# radar/strategies/scoring_strategy.py
from typing import Protocol
from ..models import Posting

class ScoringStrategy(Protocol):
    def score(self, posting: Posting) -> Posting:
        ...

class RubricScoringStrategy:
    """Score based on CLAUDE.md rubric."""
    
    def score(self, posting: Posting) -> Posting:
        from ..score import score
        return score(posting)

class MLScoringStrategy:
    """Score using machine learning model."""
    
    def __init__(self, model):
        self.model = model
    
    def score(self, posting: Posting) -> Posting:
        # Use ML model to score
        ...

class ScoringContext:
    def __init__(self, strategy: ScoringStrategy):
        self.strategy = strategy
    
    def score(self, posting: Posting) -> Posting:
        return self.strategy.score(posting)
    
    def set_strategy(self, strategy: ScoringStrategy):
        self.strategy = strategy

# Usage
context = ScoringContext(RubricScoringStrategy())
scored_posting = context.score(posting)

# Switch to ML strategy
context.set_strategy(MLScoringStrategy(model))
scored_posting = context.score(posting)
```

### 5. Observer Pattern

**Current:** Direct function calls for notifications
**Proposed:** Observer pattern for event notifications

```python
# radar/observers.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class ObserverProtocol(Protocol):
    def update(self, event: dict) -> None:
        ...

class Subject:
    def __init__(self):
        self.observers: list[ObserverProtocol] = []
    
    def attach(self, observer: ObserverProtocol):
        self.observers.append(observer)
    
    def detach(self, observer: ObserverProtocol):
        self.observers.remove(observer)
    
    def notify(self, event: dict):
        for observer in self.observers:
            observer.update(event)

# Example observer
class LoggingObserver:
    def update(self, event: dict):
        logger.info(f"Event: {event['type']}, Data: {event.get('data')}")

class MetricsObserver:
    def update(self, event: dict):
        if event['type'] == 'posting_found':
            metrics.incr('postings_found', 1)

# Usage
subject = Subject()
subject.attach(LoggingObserver())
subject.attach(MetricsObserver())

subject.notify({'type': 'posting_found', 'data': {...}})
```

---

## Migration Strategies

### 1. Incremental Migration

**Approach:** Gradually replace components without breaking existing functionality

**Steps:**
1. **Add new implementation alongside old**
   - Create `async_http.py` alongside `http.py`
   - Create `repositories/` directory alongside direct db access
   
2. **Update internal code to use new implementation**
   - Update ATS adapters to use new HTTP client
   - Update services to use repositories
   
3. **Update external interfaces**
   - Update CLI commands
   - Update pipeline
   
4. **Remove old implementation**
   - Once all code uses new implementation, remove old

**Example:**
```python
# Step 1: Add new implementation
# radar/http_v2.py
import aiohttp

class AsyncPoliteClient:
    # ... async implementation ...

# Step 2: Update adapter to support both
# radar/ats/greenhouse.py
import os

if os.getenv('RADAR_USE_ASYNC', 'false').lower() == 'true':
    from ..http_v2 import AsyncPoliteClient as Client
else:
    from ..http import PoliteClient as Client

class GreenhouseAdapter:
    def __init__(self):
        self.client = Client()
```

### 2. Feature Flags

**Approach:** Use feature flags to enable/disable new functionality

**Implementation:**

```python
# radar/feature_flags.py
from typing import Callable, Any
from functools import wraps

class FeatureFlags:
    def __init__(self):
        self.flags: dict[str, bool] = {}
    
    def is_enabled(self, flag: str) -> bool:
        return self.flags.get(flag, False)
    
    def set(self, flag: str, enabled: bool):
        self.flags[flag] = enabled
    
    def from_env(self):
        """Load flags from environment."""
        import os
        for key, value in os.environ.items():
            if key.startswith('RADAR_FF_'):
                flag = key[10:].lower()
                self.flags[flag] = value.lower() in ('true', '1', 'yes')

# Global feature flags
flags = FeatureFlags()
flags.from_env()

def feature_flag(flag: str):
    """Decorator to check feature flag."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not flags.is_enabled(flag):
                # Fall back to old implementation or raise
                raise NotImplementedError(f"Feature {flag} is disabled")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Usage
@feature_flag('async_http')
def fetch_async(url: str):
    # Async implementation
    ...

# Fallback
try:
    result = fetch_async(url)
except NotImplementedError:
    result = fetch_sync(url)
```

### 3. Parallel Run

**Approach:** Run old and new implementations in parallel, compare results

**Implementation:**

```python
# radar/parallel_run.py
import asyncio
from typing import Tuple

async def run_parallel(
    old_func: callable,
    new_func: callable,
    *args,
    **kwargs
) -> Tuple[any, any]:
    """Run old and new implementations in parallel."""
    old_result = None
    new_result = None
    old_error = None
    new_error = None
    
    async def run_old():
        nonlocal old_result, old_error
        try:
            old_result = old_func(*args, **kwargs)
        except Exception as e:
            old_error = e
    
    async def run_new():
        nonlocal new_result, new_error
        try:
            new_result = await new_func(*args, **kwargs)
        except Exception as e:
            new_error = e
    
    await asyncio.gather(run_old(), run_new())
    
    return (
        (old_result, old_error),
        (new_result, new_error),
    )

def compare_results(old_result, new_result, comparator: callable = None):
    """Compare results from old and new implementations."""
    if old_result != new_result:
        if comparator:
            return comparator(old_result, new_result)
        return False
    return True

# Usage
old_result, old_error = await run_old()
new_result, new_error = await run_new()

if old_error and new_error:
    # Both failed - compare errors
    pass
elif old_error:
    # Old failed, new succeeded - new is better
    pass
elif new_error:
    # New failed, old succeeded - new has bug
    pass
else:
    # Both succeeded - compare results
    if not compare_results(old_result, new_result):
        # Results differ - investigate
        pass
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

**Goal:** Improve stability and maintainability

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Add request timeouts | High | 2h | High |
| Improve error handling | High | 4h | High |
| Add structured logging | High | 4h | High |
| Add health checks | Medium | 4h | Medium |
| Add metrics collection | Medium | 4h | Medium |
| Extract constants | Medium | 4h | Medium |
| Add type hints | Medium | 8h | Medium |

**Deliverables:**
- More reliable system
- Better debugging capabilities
- Cleaner codebase

---

### Phase 2: Performance (Week 3-4)

**Goal:** Improve performance and scalability

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Add caching for ATS metadata | High | 4h | High |
| Optimize thread pool sizing | High | 4h | High |
| Add batch processing | High | 8h | High |
| Improve deduplication | Medium | 4h | Medium |
| Add async HTTP client | Medium | 8h | High |
| Add circuit breakers | Medium | 4h | Medium |

**Deliverables:**
- Faster execution
- Better resource utilization
- More resilient to failures

---

### Phase 3: Architecture (Week 5-8)

**Goal:** Improve architecture and testability

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Add dependency injection | High | 8h | High |
| Implement repository pattern | High | 8h | High |
| Add service layer | High | 8h | High |
| Implement plugin system | Medium | 8h | Medium |
| Add event-driven architecture | Medium | 8h | Medium |
| Improve configuration | Medium | 4h | Medium |

**Deliverables:**
- More maintainable codebase
- Easier to test
- More extensible

---

### Phase 4: Scaling (Week 9-12)

**Goal:** Enable distributed processing

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Add Celery/RQ support | High | 8h | High |
| Implement distributed rate limiting | High | 8h | High |
| Add result aggregation | High | 4h | High |
| Add monitoring | Medium | 8h | Medium |
| Add alerting | Medium | 4h | Medium |

**Deliverables:**
- Horizontal scalability
- Better resource utilization
- Monitoring and alerting

---

### Phase 5: Advanced Features (Ongoing)

**Goal:** Add advanced capabilities

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Add ML scoring | Low | 16h | High |
| Add web UI | Low | 24h | High |
| Add real-time processing | Low | 16h | Medium |
| Add anomaly detection | Low | 8h | Medium |

**Deliverables:**
- Smarter scoring
- Better user experience
- Proactive issue detection

---

## Comparison Matrix

| Framework | Use Case | Complexity | Maturity | Integration Effort |
|-----------|----------|------------|----------|-------------------|
| aiohttp | Async HTTP | Medium | High | Medium |
| Celery | Task queue | High | High | High |
| RQ | Simple task queue | Low | High | Medium |
| dependency-injector | DI | Low | High | Medium |
| pydantic-settings | Config | Low | High | Low |
| pluggy | Plugins | Medium | High | Medium |
| pydantic-events | Events | Medium | Medium | Medium |
| Prometheus | Monitoring | Medium | High | Medium |

---

## Recommendations

### For Immediate Improvement

1. **Start with Phase 1 tasks** - These provide the biggest bang for the buck
2. **Add structured logging** - This will help debug all other issues
3. **Add request timeouts** - Prevents hung requests
4. **Improve error handling** - Makes failures more visible

### For Long-Term Success

1. **Adopt dependency injection** - Makes testing easier
2. **Implement repository pattern** - Decouples business logic from data access
3. **Add plugin system** - Makes the system extensible
4. **Add async support** - Improves performance significantly

### For Production Deployment

1. **Add monitoring** - Track system health
2. **Add distributed processing** - Enable horizontal scaling
3. **Add circuit breakers** - Improve resilience
4. **Add alerting** - Proactive issue detection

---

## Example: Full Async Implementation

Here's what a fully async implementation might look like:

```python
# radar/async_pipeline.py
import asyncio
from typing import AsyncIterator
from .async_http import AsyncPoliteClient
from .models import Posting
from .ats.async_adapters import AsyncGreenhouseAdapter

class AsyncPipeline:
    def __init__(self):
        self.http_client = AsyncPoliteClient()
        self.greenhouse = AsyncGreenhouseAdapter(self.http_client)
    
    async def verify_seeds_async(self, seeds: list) -> list:
        """Verify seeds concurrently."""
        tasks = [
            self._verify_seed_async(seed) 
            for seed in seeds
        ]
        return await asyncio.gather(*tasks)
    
    async def _verify_seed_async(self, seed) -> SeedResult:
        # Async verification
        result = await self.http_client.get(seed.url)
        # Process result
        ...
    
    async def pull_boards_async(self, boards: list) -> list:
        """Pull boards concurrently."""
        tasks = [
            self._pull_board_async(ats, slug, company) 
            for ats, slug, company in boards
        ]
        return await asyncio.gather(*tasks)
    
    async def _pull_board_async(self, ats: str, slug: str, company: str) -> tuple:
        if ats == 'greenhouse':
            return await self.greenhouse.pull_async(slug, company)
        # Other ATS types
        ...
    
    async def run_async(self) -> dict:
        """Run full pipeline asynchronously."""
        # Phase 1
        seeds = await self.verify_seeds_async(seeds)
        
        # Phase 2
        boards = await self.pull_boards_async(boards)
        
        # Phase 3
        discoveries = await self.run_discovery_async(channels)
        
        # Phase 4
        postings = await self.score_postings_async(all_postings)
        
        # Phase 5
        await self.generate_outputs_async(postings)
        
        return summary

# Usage
async def main():
    pipeline = AsyncPipeline()
    summary = await pipeline.run_async()
    print(summary)

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Conclusion

The Claudey job radar has a solid foundation but can benefit significantly from:

1. **Better error handling and reliability** (Phase 1)
2. **Improved performance** (Phase 2)
3. **Cleaner architecture** (Phase 3)
4. **Scalability** (Phase 4)
5. **Advanced features** (Phase 5)

**Recommended starting point:** Begin with Phase 1 tasks to improve stability, then move to Phase 2 for performance improvements. The architectural improvements in Phase 3 will make future development easier.

For production deployment, consider adding monitoring (Prometheus + Grafana) and distributed processing (Celery or RQ) early to ensure the system can handle production workloads.

---

*Last updated: 2026-10-07*
