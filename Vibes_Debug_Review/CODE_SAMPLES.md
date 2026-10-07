# Code Samples for Claudey Improvements

## Table of Contents
1. [Error Handling Samples](#error-handling-samples)
2. [Performance Optimization Samples](#performance-optimization-samples)
3. [Architecture Pattern Samples](#architecture-pattern-samples)
4. [Testing Samples](#testing-samples)
5. [Utility Samples](#utility-samples)

---

## Error Handling Samples

### 1. Centralized Error Collection

```python
# radar/errors.py
"""Centralized error collection and handling."""
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum
import traceback
import time
from collections import defaultdict


class ErrorSeverity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorRecord:
    """Record of an error that occurred."""
    error_id: str
    timestamp: float
    severity: ErrorSeverity
    error_type: str
    message: str
    module: str
    function: str
    line: int
    context: dict = field(default_factory=dict)
    traceback: str = ""
    
    def to_dict(self) -> dict:
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp,
            'severity': self.severity.value,
            'error_type': self.error_type,
            'message': self.message,
            'module': self.module,
            'function': self.function,
            'line': self.line,
            'context': self.context,
            'traceback': self.traceback,
        }


class ErrorCollector:
    """Collects and manages errors during a run."""
    
    def __init__(self):
        self.errors: list[ErrorRecord] = []
        self.error_counts: dict[str, int] = defaultdict(int)
        self.start_time = time.time()
        self.run_id: Optional[str] = None
    
    def record(self, 
               severity: ErrorSeverity,
               error: Exception,
               context: dict = None,
               module: str = None,
               function: str = None,
               line: int = None) -> str:
        """Record an error."""
        import uuid
        import inspect
        
        if module is None or function is None:
            frame = inspect.currentframe().f_back.f_back
            module = frame.f_code.co_name if module is None else module
            function = frame.f_code.co_name if function is None else function
            line = frame.f_lineno if line is None else line
        
        error_id = str(uuid.uuid4())
        
        record = ErrorRecord(
            error_id=error_id,
            timestamp=time.time(),
            severity=severity,
            error_type=type(error).__name__,
            message=str(error),
            module=module,
            function=function,
            line=line,
            context=context or {},
            traceback=traceback.format_exc(),
        )
        
        self.errors.append(record)
        self.error_counts[f"{module}.{function}"] += 1
        self.error_counts[error_type] += 1
        
        return error_id
    
    def record_message(self,
                       severity: ErrorSeverity,
                       message: str,
                       context: dict = None,
                       module: str = None,
                       function: str = None,
                       line: int = None) -> str:
        """Record an error message without exception."""
        import uuid
        import inspect
        
        if module is None or function is None:
            frame = inspect.currentframe().f_back.f_back
            module = frame.f_code.co_name if module is None else module
            function = frame.f_code.co_name if function is None else function
            line = frame.f_lineno if line is None else line
        
        error_id = str(uuid.uuid4())
        
        record = ErrorRecord(
            error_id=error_id,
            timestamp=time.time(),
            severity=severity,
            error_type="Message",
            message=message,
            module=module,
            function=function,
            line=line,
            context=context or {},
            traceback="",
        )
        
        self.errors.append(record)
        self.error_counts[f"{module}.{function}"] += 1
        
        return error_id
    
    def get_summary(self) -> dict:
        """Get a summary of collected errors."""
        return {
            'total_errors': len(self.errors),
            'by_severity': {
                s.value: sum(1 for e in self.errors if e.severity == s)
                for s in ErrorSeverity
            },
            'by_type': dict(self.error_counts),
            'by_module': defaultdict(int),
            'recent_errors': [e.to_dict() for e in self.errors[-10:]],
        }
    
    def get_critical_errors(self) -> list[ErrorRecord]:
        """Get all critical and error severity errors."""
        return [
            e for e in self.errors 
            if e.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL)
        ]
    
    def save_to_file(self, path: str) -> None:
        """Save all errors to a file."""
        import json
        with open(path, 'w') as f:
            json.dump([e.to_dict() for e in self.errors], f, indent=2)
    
    def has_errors(self, severity: ErrorSeverity = None) -> bool:
        """Check if any errors of specified severity exist."""
        if severity is None:
            return len(self.errors) > 0
        return any(e.severity == severity for e in self.errors)


# Global error collector
_error_collector = ErrorCollector()


def get_error_collector() -> ErrorCollector:
    """Get the global error collector."""
    return _error_collector


def reset_error_collector() -> None:
    """Reset the global error collector."""
    global _error_collector
    _error_collector = ErrorCollector()


def set_run_id(run_id: str) -> None:
    """Set the run ID for the error collector."""
    _error_collector.run_id = run_id


# Convenience functions
def record_error(error: Exception, context: dict = None) -> str:
    """Record an error."""
    return _error_collector.record(ErrorSeverity.ERROR, error, context)


def record_warning(warning: Exception, context: dict = None) -> str:
    """Record a warning."""
    return _error_collector.record(ErrorSeverity.WARNING, warning, context)


def record_message(severity: ErrorSeverity, message: str, context: dict = None) -> str:
    """Record a message."""
    return _error_collector.record_message(severity, message, context)
```

**Usage:**

```python
# In any module
from radar.errors import record_error, record_warning, get_error_collector

def verify_url(url: str, company: str) -> Outcome:
    try:
        # ... verification logic ...
        return Outcome("open", posting, evidence, method)
    except Exception as e:
        record_error(e, context={'url': url, 'company': company})
        return Outcome("unverified", None, f"Error: {e}", "error")

# At the end of a run
from radar.errors import get_error_collector

collector = get_error_collector()
if collector.has_errors():
    collector.save_to_file(f"data/runs/{run_id}/errors.json")
    summary = collector.get_summary()
    print(f"Run completed with {summary['total_errors']} errors")
```

---

### 2. Circuit Breaker Pattern

```python
# radar/circuit_breaker.py
"""Circuit breaker pattern implementation."""
import time
from typing import Callable, Optional, Any
from threading import Lock
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 5          # Number of failures to open circuit
    recovery_timeout: float = 30.0    # Seconds to wait before trying again
    half_open_max_attempts: int = 3   # Max attempts in half-open state
    

class CircuitBreaker:
    """Circuit breaker for a specific operation."""
    
    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_attempts = 0
        self.lock = Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call the function with circuit breaker protection."""
        with self.lock:
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self.last_failure_time > self.config.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_attempts = 0
            
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open, will retry after "
                    f"{self.config.recovery_timeout - (time.time() - self.last_failure_time):.1f}s"
                )
        
        try:
            result = func(*args, **kwargs)
            
            with self.lock:
                if self.state == CircuitState.HALF_OPEN:
                    # Success in half-open state, close the circuit
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                
            return result
            
        except Exception as e:
            with self.lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.state == CircuitState.HALF_OPEN:
                    self.half_open_attempts += 1
                    if self.half_open_attempts >= self.config.half_open_max_attempts:
                        # Still failing, reopen the circuit
                        self.state = CircuitState.OPEN
                elif self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
            
            raise CircuitBreakerError(f"Function failed: {e}") from e
    
    def reset(self) -> None:
        """Reset the circuit breaker."""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
            self.half_open_attempts = 0
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
    
    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED
    
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Circuit breaker is open."""
    pass


class CircuitBreakerConfigError(CircuitBreakerError):
    """Circuit breaker configuration error."""
    pass


# Global circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_breakers_lock = Lock()


def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
    """Get or create a circuit breaker for a named operation."""
    with _circuit_breakers_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(config)
        return _circuit_breakers[name]


def reset_circuit_breaker(name: str) -> None:
    """Reset a circuit breaker."""
    with _circuit_breakers_lock:
        if name in _circuit_breakers:
            _circuit_breakers[name].reset()


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers."""
    with _circuit_breakers_lock:
        for cb in _circuit_breakers.values():
            cb.reset()
```

**Usage:**

```python
# In http.py or ATS adapters
from radar.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig

# Configure circuit breaker for a specific host
config = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=60.0,
)
breaker = get_circuit_breaker(f"host:example.com", config)

def fetch_from_host(url: str) -> Result:
    try:
        return breaker.call(lambda: client().get(url))
    except CircuitBreakerOpenError:
        # Return cached result or fail gracefully
        return get_cached_result(url) or Result(
            url=url,
            status=None,
            error="Circuit breaker open",
            blocked="circuit_open",
        )
```

---

## Performance Optimization Samples

### 3. Batch Processing

```python
# radar/batch.py
"""Batch processing utilities."""
from typing import Callable, TypeVar, Any, list, tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

T = TypeVar('T')
R = TypeVar('R')


class BatchProcessor:
    """Process items in batches with concurrency control."""
    
    def __init__(self, max_workers: int = 10, batch_size: int = 100):
        self.max_workers = max_workers
        self.batch_size = batch_size
    
    def process_in_batches(
        self,
        items: list[T],
        processor: Callable[[T], R],
        progress_callback: Callable[[int, int], None] = None,
    ) -> list[R]:
        """Process items in batches."""
        results = []
        total = len(items)
        
        for i in range(0, total, self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_results = self._process_batch(batch, processor)
            results.extend(batch_results)
            
            if progress_callback:
                progress_callback(i + len(batch), total)
        
        return results
    
    def _process_batch(self, batch: list[T], processor: Callable[[T], R]) -> list[R]:
        """Process a single batch."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(processor, item): item 
                for item in batch
            }
            
            batch_results = []
            for future in as_completed(futures):
                item = futures[future]
                try:
                    result = future.result()
                    batch_results.append(result)
                except Exception as e:
                    # Handle error for this item
                    batch_results.append(self._handle_error(item, e))
            
            return batch_results
    
    def _handle_error(self, item: T, error: Exception) -> R:
        """Handle an error for a specific item."""
        # Log the error
        from radar.errors import record_error
        record_error(error, context={'item': str(item)})
        
        # Return a default/error result
        # This should be customized based on the use case
        return None  # type: ignore
    
    def process_in_batches_async(
        self,
        items: list[T],
        processor: Callable[[T], R],
        progress_callback: Callable[[int, int], None] = None,
    ) -> list[R]:
        """Process items in batches asynchronously (non-blocking)."""
        import asyncio
        
        async def process():
            results = []
            total = len(items)
            
            for i in range(0, total, self.batch_size):
                batch = items[i:i + self.batch_size]
                batch_results = await self._process_batch_async(batch, processor)
                results.extend(batch_results)
                
                if progress_callback:
                    progress_callback(i + len(batch), total)
            
            return results
        
        return asyncio.run(process())
    
    async def _process_batch_async(self, batch: list[T], processor: Callable[[T], R]) -> list[R]:
        """Process a single batch asynchronously."""
        import asyncio
        
        async def process_item(item: T) -> R:
            try:
                return processor(item)
            except Exception as e:
                return self._handle_error(item, e)
        
        tasks = [process_item(item) for item in batch]
        return await asyncio.gather(*tasks)


# Convenience functions
def batch_process(
    items: list[T],
    processor: Callable[[T], R],
    max_workers: int = 10,
    batch_size: int = 100,
    progress_callback: Callable[[int, int], None] = None,
) -> list[R]:
    """Convenience function for batch processing."""
    processor = BatchProcessor(max_workers, batch_size)
    return processor.process_in_batches(items, processor, progress_callback)
```

**Usage:**

```python
# In phase2.py
from radar.batch import batch_process
from radar.ats import greenhouse, lever, ashby

def pull_all_boards(boards: list[tuple]) -> list[Posting]:
    """Pull all boards using batch processing."""
    
    def pull_board(board_info: tuple) -> list[Posting]:
        ats, slug, company, segment = board_info
        if ats == 'greenhouse':
            status, postings = greenhouse.pull(slug, company, f'board:{ats}')
        elif ats == 'lever':
            status, postings = lever.pull(slug, company, f'board:{ats}')
        elif ats == 'ashby':
            status, postings = ashby.pull(slug, company, f'board:{ats}')
        else:
            postings = []
        return postings
    
    # Process all boards in parallel batches
    all_postings = []
    for batch_results in batch_process(boards, pull_board, max_workers=5, batch_size=10):
        all_postings.extend(batch_results)
    
    return all_postings
```

---

### 4. Caching with TTL

```python
# radar/cache.py
"""Enhanced caching with TTL and size limits."""
from typing import Any, Callable, Optional, TypeVar
import time
import hashlib
from functools import wraps
from threading import Lock

T = TypeVar('T')


class TTLCache:
    """Thread-safe cache with TTL."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl_seconds:
                    return value
                # Expired, remove it
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in cache."""
        with self._lock:
            # Evict old entries if cache is full
            if len(self._cache) >= self.max_size:
                self._evict_oldest()
            
            self._cache[key] = (value, time.time())
    
    def _evict_oldest(self) -> None:
        """Evict the oldest entry."""
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
        del self._cache[oldest_key]
    
    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
        return False
    
    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        """Get the current cache size."""
        with self._lock:
            return len(self._cache)
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries and return count."""
        with self._lock:
            expired_keys = [
                k for k, (_, timestamp) in self._cache.items()
                if time.time() - timestamp >= self.ttl_seconds
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


# Global caches
_ats_metadata_cache = TTLCache(max_size=100, ttl_seconds=86400)  # 24 hours
_field_extraction_cache = TTLCache(max_size=1000, ttl_seconds=3600)  # 1 hour
_url_cache = TTLCache(max_size=5000, ttl_seconds=1800)  # 30 minutes


class CacheKey:
    """Helper for creating cache keys."""
    
    @staticmethod
    def make(*args, **kwargs) -> str:
        """Create a cache key from arguments."""
        # Sort kwargs for consistent ordering
        sorted_kwargs = sorted(kwargs.items())
        key_string = repr(args) + repr(sorted_kwargs)
        return hashlib.sha256(key_string.encode()).hexdigest()


# Decorator for caching function results
def cached(ttl_seconds: float = 3600.0, cache: TTLCache = None, key_func: Callable = None):
    """Decorator to cache function results."""
    def decorator(func: Callable) -> Callable:
        cache = cache or TTLCache(ttl_seconds=ttl_seconds)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = CacheKey.make(args, kwargs)
            
            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result
        
        # Add method to clear cache for this function
        wrapper.cache_clear = lambda: cache.clear()
        
        return wrapper
    return decorator


# Decorator for caching based on first argument (common pattern)
def cached_by_first_arg(ttl_seconds: float = 3600.0, cache: TTLCache = None):
    """Decorator to cache based on first argument."""
    def key_func(*args, **kwargs) -> str:
        if args:
            return str(args[0])
        return CacheKey.make(args, kwargs)
    
    return cached(ttl_seconds, cache, key_func)
```

**Usage:**

```python
# In greenhouse.py or other ATS adapters
from radar.cache import cached_by_first_arg, _ats_metadata_cache

@cached_by_first_arg(ttl_seconds=86400, cache=_ats_metadata_cache)
def board_name(slug: str) -> str:
    """Get board name with caching."""
    # Original implementation
    url = f"https://boards.greenhouse.io/v1/boards/{slug}"
    response = client().get(url)
    if response.ok:
        data = response.json()
        return data.get('name', slug)
    return slug

# In extract.py
from radar.cache import cached, _field_extraction_cache

@cached(ttl_seconds=3600, cache=_field_extraction_cache)
def pay_from_text(text: str) -> Pay:
    """Extract pay from text with caching."""
    # Original implementation
    ...
```

---

## Architecture Pattern Samples

### 5. Repository Pattern Implementation

```python
# radar/repositories/base.py
"""Base repository classes."""
from typing import Generic, TypeVar, Optional, list
from abc import ABC, abstractmethod

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Base repository interface."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """Get an entity by key."""
        pass
    
    @abstractmethod
    def get_all(self) -> list[T]:
        """Get all entities."""
        pass
    
    @abstractmethod
    def save(self, entity: T) -> None:
        """Save an entity."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete an entity."""
        pass
    
    @abstractmethod
    def search(self, **kwargs) -> list[T]:
        """Search for entities."""
        pass


class InMemoryRepository(BaseRepository[T]):
    """In-memory repository for testing."""
    
    def __init__(self):
        self._store: dict[str, T] = {}
    
    def get(self, key: str) -> Optional[T]:
        return self._store.get(key)
    
    def get_all(self) -> list[T]:
        return list(self._store.values())
    
    def save(self, entity: T) -> None:
        # Assume entity has a 'key' attribute
        self._store[entity.key] = entity
    
    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False
    
    def search(self, **kwargs) -> list[T]:
        # Simple implementation: filter by attributes
        results = []
        for entity in self._store.values():
            match = True
            for key, value in kwargs.items():
                if not hasattr(entity, key) or getattr(entity, key) != value:
                    match = False
                    break
            if match:
                results.append(entity)
        return results
```

```python
# radar/repositories/posting_repository.py
"""Posting repository implementation."""
from typing import Optional, list
from .base import BaseRepository
from ..models import Posting
from .. import db


class PostingRepository(BaseRepository[Posting]):
    """Repository for Posting entities."""
    
    def __init__(self, conn=None):
        self.conn = conn or db.conn()
    
    def get(self, key: str) -> Optional[Posting]:
        return db.get_posting(key)
    
    def get_all(self) -> list[Posting]:
        rows = self.conn.execute("SELECT data FROM postings").fetchall()
        return [Posting.model_validate_json(row['data']) for row in rows]
    
    def save(self, posting: Posting) -> None:
        db.upsert_posting(posting)
    
    def delete(self, key: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM postings WHERE key=?", (key,))
        return cursor.rowcount > 0
    
    def search(
        self,
        company: str = None,
        title: str = None,
        status: str = None,
        bucket: str = None,
        limit: int = None,
    ) -> list[Posting]:
        """Search for postings with filters."""
        query = "SELECT data FROM postings WHERE 1=1"
        params = []
        
        if company:
            query += " AND company = ?"
            params.append(company)
        if title:
            query += " AND title LIKE ?"
            params.append(f"%{title}%")
        if status:
            query += " AND status = ?"
            params.append(status)
        if bucket:
            query += " AND bucket = ?"
            params.append(bucket)
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        rows = self.conn.execute(query, params).fetchall()
        return [Posting.model_validate_json(row['data']) for row in rows]
    
    def get_by_dedupe_key(self, dedupe_key: str) -> list[Posting]:
        """Get all postings with the same deduplication key."""
        rows = self.conn.execute(
            "SELECT data FROM postings WHERE dedupe_key=?",
            (dedupe_key,)
        ).fetchall()
        return [Posting.model_validate_json(row['data']) for row in rows]
    
    def get_by_company(self, company: str) -> list[Posting]:
        """Get all postings for a company."""
        return self.search(company=company)
    
    def get_recent(self, days: int = 7) -> list[Posting]:
        """Get postings from the last N days."""
        import datetime as dt
        since_date = (dt.datetime.now() - dt.timedelta(days=days)).date().isoformat()
        rows = self.conn.execute(
            "SELECT data FROM postings WHERE last_seen >= ?",
            (since_date,)
        ).fetchall()
        return [Posting.model_validate_json(row['data']) for row in rows]
```

**Usage:**

```python
# In phase4.py or other modules
from radar.repositories import PostingRepository

# Create repository
repo = PostingRepository()

# Get a posting
posting = repo.get('greenhouse:board123:job456')

# Search for postings
fit_postings = repo.search(bucket='fit')

# Get recent postings
recent = repo.get_recent(days=7)
```

---

### 6. Service Pattern Implementation

```python
# radar/services/verification_service.py
"""Verification service."""
from typing import Optional
from ..models import Posting
from ..repositories import PostingRepository
from ..http import PoliteClient
from ..errors import record_error


class VerificationService:
    """Service for verifying postings."""
    
    def __init__(self, repository: PostingRepository, client: PoliteClient):
        self.repository = repository
        self.client = client
    
    def verify_url(self, url: str, company: str, source: str = "verify") -> Optional[Posting]:
        """Verify a single URL."""
        from ..verify import verify_url as _verify_url
        
        try:
            outcome = _verify_url(url, company, source)
            
            if outcome.posting:
                # Save to repository
                self.repository.save(outcome.posting)
                return outcome.posting
            
            return None
            
        except Exception as e:
            record_error(e, context={'url': url, 'company': company, 'source': source})
            return None
    
    def verify_urls(self, urls: list[tuple[str, str, str]]) -> list[Optional[Posting]]:
        """Verify multiple URLs."""
        from radar.batch import batch_process
        
        def verify_single(url_info: tuple[str, str, str]) -> Optional[Posting]:
            url, company, source = url_info
            return self.verify_url(url, company, source)
        
        return batch_process(urls, verify_single, max_workers=10)
    
    def verify_board(self, ats: str, board: str, company: str) -> list[Posting]:
        """Verify all postings on a board."""
        if ats == 'greenhouse':
            from ..ats import greenhouse
            status, postings = greenhouse.pull(board, company, f'board:{ats}')
        elif ats == 'lever':
            from ..ats import lever
            status, postings = lever.pull(board, company, f'board:{ats}')
        elif ats == 'ashby':
            from ..ats import ashby
            status, postings = ashby.pull(board, company, f'board:{ats}')
        else:
            return []
        
        # Save all postings
        for posting in postings:
            self.repository.save(posting)
        
        return postings
    
    def get_verified(self, company: str = None, since: str = None) -> list[Posting]:
        """Get all verified postings."""
        if company:
            return self.repository.search(company=company, status='open')
        elif since:
            return self.repository.search(status='open', last_seen__gte=since)
        else:
            return self.repository.search(status='open')


# Convenience function for creating service
from .. import db
from ..http import client as http_client

_default_verification_service: Optional[VerificationService] = None


def get_verification_service() -> VerificationService:
    """Get the default verification service."""
    global _default_verification_service
    if _default_verification_service is None:
        repo = PostingRepository()
        _default_verification_service = VerificationService(repo, http_client())
    return _default_verification_service
```

---

## Testing Samples

### 7. Test Fixtures

```python
# tests/conftest.py
"""Pytest fixtures for Claudey."""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_http_client():
    """Mock HTTP client."""
    with patch('radar.http.client') as mock:
        client = MagicMock()
        
        # Default response
        default_response = MagicMock()
        default_response.ok = True
        default_response.status = 200
        default_response.text = '<html></html>'
        default_response.headers = {'Content-Type': 'text/html'}
        default_response.content = b'<html></html>'
        default_response.json.return_value = {}
        
        client.get.return_value = default_response
        client.post_json.return_value = default_response
        
        mock.return_value = client
        yield client


@pytest.fixture
def mock_failing_http_client():
    """Mock HTTP client that fails."""
    with patch('radar.http.client') as mock:
        client = MagicMock()
        
        # Failing response
        failing_response = MagicMock()
        failing_response.ok = False
        failing_response.status = 500
        failing_response.text = 'Internal Server Error'
        failing_response.error = 'Connection refused'
        
        client.get.return_value = failing_response
        
        mock.return_value = client
        yield client


@pytest.fixture
def mock_ats_adapter():
    """Mock ATS adapter."""
    mock = MagicMock()
    mock.probe.return_value = (True, 10)  # (ok, job_count)
    mock.pull.return_value = ('ok', [])  # (status, postings)
    mock.verify.return_value = None
    return mock


@pytest.fixture
def sample_posting():
    """Create a sample posting."""
    from radar.models import Posting
    return Posting(
        key='test:123',
        company='Test Company',
        title='Test Job',
        url='https://example.com/job/123',
        location='New York, NY',
        pay_min=100000,
        pay_max=150000,
        pay_type='base',
        description='Test job description',
        status='open',
        bucket='fit',
    )


@pytest.fixture
def sample_postings():
    """Create multiple sample postings."""
    from radar.models import Posting
    return [
        Posting(
            key=f'test:{i}',
            company=f'Company {i}',
            title=f'Job {i}',
            url=f'https://example.com/job/{i}',
            location='New York, NY',
            pay_min=100000 + i * 10000,
            pay_max=150000 + i * 10000,
            pay_type='base',
            description=f'Job description {i}',
            status='open',
            bucket='fit' if i % 2 == 0 else 'poor',
        )
        for i in range(10)
    ]


@pytest.fixture
def mock_config(temp_data_dir):
    """Mock configuration."""
    with patch('radar.config') as mock_config:
        mock_config.DATA = temp_data_dir / 'data'
        mock_config.OUT = temp_data_dir / 'out'
        mock_config.CACHE = temp_data_dir / 'cache'
        mock_config.DB_PATH = temp_data_dir / 'data' / 'jobs.sqlite'
        mock_config.COMPANIES_CSV = temp_data_dir / 'seeds' / 'companies.csv'
        mock_config.SEED_LIST = temp_data_dir / 'seeds' / 'current_list.md'
        
        # Create directories
        (temp_data_dir / 'data').mkdir(parents=True, exist_ok=True)
        (temp_data_dir / 'out').mkdir(parents=True, exist_ok=True)
        (temp_data_dir / 'cache').mkdir(parents=True, exist_ok=True)
        (temp_data_dir / 'seeds').mkdir(parents=True, exist_ok=True)
        
        yield mock_config
```

---

### 8. Unit Test Examples

```python
# tests/test_score.py
"""Tests for scoring logic."""
import pytest
from radar.score import score, FIT_MIN, RX, EXCL
from radar.models import Posting


class TestScoring:
    """Tests for the scoring function."""
    
    def test_jd_required_signal(self):
        """Test that JD required gives a fit signal."""
        p = Posting(
            title='Legal Counsel',
            description='JD required',
            jd_required='Y',
        )
        scored = score(p)
        assert scored.fit_score >= 1
        assert 'JD required/preferred' in scored.fit_signals
    
    def test_clerkship_signal(self):
        """Test that clerkship mention gives a fit signal."""
        p = Posting(
            title='Attorney',
            description='Clerkship experience preferred',
        )
        scored = score(p)
        assert 'clerkship valued' in scored.fit_signals
    
    def test_sales_exclude(self):
        """Test that sales roles are hard excluded."""
        p = Posting(
            title='Account Executive',
            description='Sales role with quota',
        )
        scored = score(p)
        assert scored.hard_exclude_reason
        assert 'Sales' in scored.hard_exclude_reason
    
    def test_law_firm_exclude(self):
        """Test that law firm seats are poor match."""
        p = Posting(
            title='Associate Attorney',
            description='Law firm position',
            company='Skadden, Arps, Slate, Meagher & Flom LLP',
        )
        scored = score(p)
        assert 'Law-firm seat' in scored.poor_reason
    
    def test_pay_floor_exclude(self):
        """Test that postings below pay floor are excluded."""
        p = Posting(
            title='Legal Assistant',
            description='Entry level position',
            pay_min=50000,
            pay_max=60000,
            pay_type='base',
        )
        scored = score(p)
        assert 'below $150K' in scored.poor_reason
    
    def test_fit_minimum(self):
        """Test that postings need minimum signals to be fit."""
        p = Posting(
            title='Test Job',
            description='',
        )
        scored = score(p)
        # Should not be in fit bucket with 0 signals
        if scored.bucket == 'fit':
            assert scored.fit_score >= FIT_MIN
    
    def test_location_bucket(self):
        """Test that location affects bucket."""
        p_nyc = Posting(
            title='NYC Job',
            description='',
            location='New York, NY',
            loc_bucket='nyc',
        )
        p_sf = Posting(
            title='SF Job',
            description='',
            location='San Francisco, CA',
            loc_bucket='us_other',
        )
        
        scored_nyc = score(p_nyc)
        scored_sf = score(p_sf)
        
        # NYC job should be in better bucket
        assert scored_nyc.bucket in ('fit', 'poor')
        assert scored_sf.bucket == 'outside'


class TestRegexPatterns:
    """Tests for regex patterns used in scoring."""
    
    def test_clerkship_pattern(self):
        """Test clerkship regex pattern."""
        assert RX['clerkship'].search('Clerkship experience')
        assert RX['clerkship'].search('judicial clerk')
        assert not RX['clerkship'].search('clerk')
    
    def test_python_pattern(self):
        """Test Python requirement pattern."""
        assert EXCL['python'].search('Python required')
        assert EXCL['python'].search('Proficient in Python')
        assert not EXCL['python'].search('Python is a plus')
    
    def test_sales_pattern(self):
        """Test sales title pattern."""
        assert EXCL['sales_title'].search('Account Executive')
        assert EXCL['sales_title'].search('Sales Engineer')
        assert not EXCL['sales_title'].search('Legal Counsel')
```

---

### 9. Integration Test Examples

```python
# tests/test_pipeline_integration.py
"""Integration tests for the pipeline."""
import pytest
from pathlib import Path
import tempfile
import shutil


class TestPipelineIntegration:
    """Integration tests for the full pipeline."""
    
    @pytest.fixture
    def test_environment(self, temp_data_dir, mock_http_client):
        """Set up test environment."""
        # Create test data directory structure
        data_dir = temp_data_dir / 'data'
        out_dir = temp_data_dir / 'out'
        cache_dir = temp_data_dir / 'cache'
        seeds_dir = temp_data_dir / 'seeds'
        
        data_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        seeds_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal seed list
        seed_list = seeds_dir / 'current_list.md'
        seed_list.write_text('''# Current List

## Fit

| Position | Company | Location | Pay | Status |
|---|---|---|---|---|
| [Legal Counsel](https://example.com/job1) | Test Company | New York, NY | $150K-$200K | Open |

## Poor Match

| Position | Company | Location | Pay | Status | Reason |
|---|---|---|---|---|---|
| [Sales Rep](https://example.com/job2) | Sales Co | New York, NY | OTE | Open | Sales role |
''')
        
        # Create minimal companies.csv
        companies_csv = seeds_dir / 'companies.csv'
        companies_csv.write_text('company,segment,careers_url,ats,ats_slug_or_tenant\nTest Company,legal,https://example.com/careers,greenhouse,testco\n')
        
        # Patch config
        with pytest.MonkeyPatch.context() as m:
            m.setattr('radar.config.DATA', data_dir)
            m.setattr('radar.config.OUT', out_dir)
            m.setattr('radar.config.CACHE', cache_dir)
            m.setattr('radar.config.SEEDS', seeds_dir)
            m.setattr('radar.config.COMPANIES_CSV', companies_csv)
            m.setattr('radar.config.SEED_LIST', seed_list)
            
            yield {
                'data_dir': data_dir,
                'out_dir': out_dir,
                'cache_dir': cache_dir,
                'seeds_dir': seeds_dir,
            }
    
    def test_phase1_seed_verification(self, test_environment):
        """Test Phase 1 seed verification."""
        from radar import phase1
        
        results, closed = phase1.verify_seeds()
        
        # Should have processed the seed list
        assert len(results) >= 1
        
        # Check that we got the expected seed
        seed_titles = [r.row.title for r in results]
        assert 'Legal Counsel' in seed_titles
    
    def test_phase4_scoring(self, test_environment, mock_http_client):
        """Test Phase 4 scoring."""
        from radar import phase4
        from radar.models import Posting
        
        # Create a test posting
        posting = Posting(
            key='test:123',
            company='Test Company',
            title='Legal Counsel',
            url='https://example.com/job1',
            location='New York, NY',
            description='JD required, 3-5 years experience',
            status='open',
        )
        
        # Score the posting
        scored = phase4.score(posting)
        
        # Check that scoring worked
        assert scored.fit_score >= 0
        assert scored.bucket in ('fit', 'poor', 'outside')
    
    def test_full_pipeline_minimal(self, test_environment, mock_http_client):
        """Test full pipeline with minimal data."""
        from radar import pipeline
        
        # Mock discovery to avoid external calls
        with pytest.MonkeyPatch.context() as m:
            m.setattr('radar.pipeline.run_discovery', lambda c: {})
            
            # Run pipeline
            summary = pipeline.refresh(skip_discovery=True)
        
        # Check that pipeline completed
        assert 'fit' in summary
        assert 'poor' in summary
        assert 'outside' in summary
        
        # Check that outputs were created
        assert (test_environment['out_dir'] / 'open_positions_').exists()
```

---

## Utility Samples

### 10. Logging Utilities

```python
# radar/logging.py
"""Enhanced logging utilities."""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """Formatter that outputs JSON."""
    
    def __init__(self, include_timestamp: bool = True, include_level: bool = True):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_level = include_level
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        if self.include_timestamp:
            log_data['timestamp'] = datetime.utcnow().isoformat()
        
        if self.include_level:
            log_data['level'] = record.levelname
            log_data['level_num'] = record.levelno
        
        if record.module:
            log_data['module'] = record.module
        
        if record.funcName:
            log_data['function'] = record.funcName
        
        if record.lineno:
            log_data['line'] = record.lineno
        
        if record.process:
            log_data['process'] = record.process
        
        if record.thread:
            log_data['thread'] = record.thread
        
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None,
            }
        
        # Add any extra fields
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in (
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'message', 'asctime',
            ):
                try:
                    # Skip non-serializable values
                    json.dumps(value)
                    extra_fields[key] = value
                except (TypeError, ValueError):
                    extra_fields[key] = str(value)
        
        if extra_fields:
            log_data['extra'] = extra_fields
        
        return json.dumps(log_data, default=str)


class ColorFormatter(logging.Formatter):
    """Formatter with color output."""
    
    # ANSI color codes
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    RESET = '\033[0m'
    
    # Bold
    BOLD = '\033[1m'
    
    COLOR_MAP = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED + BOLD,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLOR_MAP.get(record.levelno, self.RESET)
        reset = self.RESET
        
        timestamp = self.formatTime(record)
        level = record.levelname
        message = record.getMessage()
        
        # Color the level
        colored_level = f"{color}{level}{reset}"
        
        # Basic format: timestamp - level - logger - message
        formatted = f"{timestamp} - {colored_level} - {record.name} - {message}"
        
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


class ContextFilter(logging.Filter):
    """Filter that adds context to log records."""
    
    def __init__(self, context: dict = None):
        super().__init__()
        self.context = context or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Add context to the record
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


class LoggerFactory:
    """Factory for creating configured loggers."""
    
    def __init__(self, name: str = 'radar'):
        self.name = name
        self._loggers: dict[str, logging.Logger] = {}
    
    def get_logger(
        self,
        name: Optional[str] = None,
        level: Optional[int] = None,
        json_format: bool = False,
        color_format: bool = False,
        context: Optional[dict] = None,
    ) -> logging.Logger:
        """Get or create a configured logger."""
        logger_name = name or self.name
        
        if logger_name in self._loggers:
            return self._loggers[logger_name]
        
        # Create logger
        logger = logging.getLogger(logger_name)
        
        # Set level
        if level is not None:
            logger.setLevel(level)
        elif logger.level == logging.NOTSET:
            logger.setLevel(logging.INFO)
        
        # Create handler
        handler = logging.StreamHandler(sys.stdout)
        
        # Set formatter
        if json_format:
            formatter = JSONFormatter()
        elif color_format:
            formatter = ColorFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
            )
        
        handler.setFormatter(formatter)
        
        # Add context filter
        if context:
            handler.addFilter(ContextFilter(context))
        
        # Add handler
        logger.addHandler(handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        # Store for reuse
        self._loggers[logger_name] = logger
        
        return logger
    
    def configure_root(
        self,
        level: int = logging.INFO,
        json_format: bool = False,
        color_format: bool = False,
    ) -> None:
        """Configure the root logger."""
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create handler
        handler = logging.StreamHandler(sys.stdout)
        
        # Set formatter
        if json_format:
            formatter = JSONFormatter()
        elif color_format:
            formatter = ColorFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
            )
        
        handler.setFormatter(formatter)
        
        # Add handler
        root_logger.addHandler(handler)
        
        # Reduce noise from third-party libraries
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)


# Global logger factory
logger_factory = LoggerFactory('radar')


def get_logger(
    name: str = None,
    level: int = None,
    json_format: bool = False,
    color_format: bool = False,
    context: dict = None,
) -> logging.Logger:
    """Get a configured logger."""
    return logger_factory.get_logger(name, level, json_format, color_format, context)


def configure_logging(
    level: int = logging.INFO,
    json_format: bool = False,
    color_format: bool = False,
) -> None:
    """Configure root logger."""
    logger_factory.configure_root(level, json_format, color_format)
```

---

### 11. Progress Bar

```python
# radar/progress.py
"""Progress bar utilities."""
import sys
import time
from typing import Optional, Callable


class ProgressBar:
    """Simple progress bar for terminal output."""
    
    def __init__(
        self,
        total: int,
        description: str = "Processing",
        width: int = 50,
        bar_char: str = "█",
        empty_char: str = " ",
        output: Optional[sys.stdout] = None,
    ):
        self.total = total
        self.description = description
        self.width = width
        self.bar_char = bar_char
        self.empty_char = empty_char
        self.output = output or sys.stdout
        self.start_time = time.time()
        self.current = 0
        self._displayed = False
    
    def update(self, n: int = 1) -> None:
        """Update progress by n."""
        self.current += n
        self._display()
    
    def _display(self) -> None:
        """Display the progress bar."""
        if self.total == 0:
            percent = 100
        else:
            percent = (self.current / self.total) * 100
        
        filled = int(self.width * percent / 100)
        bar = self.bar_char * filled + self.empty_char * (self.width - filled)
        
        elapsed = time.time() - self.start_time
        if self.current > 0:
            rate = self.current / elapsed
            eta = (self.total - self.current) / rate if rate > 0 else 0
            eta_str = self._format_time(eta)
        else:
            eta_str = "??:??"
        
        elapsed_str = self._format_time(elapsed)
        
        line = f"\r{self.description}: |{bar}| {self.current}/{self.total} "
        line += f"[{elapsed_str}<{eta_str}, {rate:.2f}it/s]"
        
        self.output.write(line)
        self.output.flush()
        self._displayed = True
    
    def _format_time(self, seconds: float) -> str:
        """Format time in MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def finish(self) -> None:
        """Finish the progress bar."""
        self.current = self.total
        self._display()
        self.output.write("\n")
        self.output.flush()
    
    def __enter__(self):
        self.start_time = time.time()
        self.current = 0
        self._displayed = False
        return self
    
    def __exit__(self, *args):
        if self._displayed:
            self.finish()


class Spinner:
    """Simple spinner for indeterminate progress."""
    
    def __init__(
        self,
        description: str = "Working",
        spinner_chars: str = "|/-\",
        interval: float = 0.1,
        output: Optional[sys.stdout] = None,
    ):
        self.description = description
        self.spinner_chars = spinner_chars
        self.interval = interval
        self.output = output or sys.stdout
        self._index = 0
        self._running = False
        self._thread = None
    
    def _spin(self) -> None:
        """Spin the spinner."""
        while self._running:
            char = self.spinner_chars[self._index % len(self.spinner_chars)]
            line = f"\r{self.description} {char}"
            self.output.write(line)
            self.output.flush()
            self._index += 1
            time.sleep(self.interval)
    
    def start(self) -> None:
        """Start the spinner."""
        if self._running:
            return
        
        self._running = True
        import threading
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the spinner."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        
        # Clear the spinner line
        self.output.write("\r" + " " * 80 + "\r")
        self.output.flush()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()


class ProgressTracker:
    """Track progress across multiple operations."""
    
    def __init__(self, total_operations: int = None):
        self.total_operations = total_operations
        self.completed_operations = 0
        self.start_time = time.time()
        self._current_pb: Optional[ProgressBar] = None
    
    def start_operation(self, description: str, total: int) -> ProgressBar:
        """Start a new operation with progress bar."""
        if self._current_pb:
            self._current_pb.finish()
        
        self._current_pb = ProgressBar(total, description)
        return self._current_pb
    
    def complete_operation(self) -> None:
        """Mark current operation as complete."""
        if self._current_pb:
            self._current_pb.finish()
            self._current_pb = None
        
        self.completed_operations += 1
        
        if self.total_operations:
            print(f"Completed operation {self.completed_operations}/{self.total_operations}")
    
    def get_elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time
    
    def get_rate(self) -> float:
        """Get operations per second."""
        elapsed = self.get_elapsed()
        if elapsed == 0:
            return 0
        return self.completed_operations / elapsed


def progress_bar(
    iterable=None,
    total: int = None,
    description: str = "Processing",
    **kwargs
):
    """Context manager for progress bar."""
    if iterable is not None:
        total = len(iterable)
    
    with ProgressBar(total, description, **kwargs) as pb:
        if iterable is not None:
            for item in iterable:
                yield item
                pb.update(1)
        else:
            yield pb
```

**Usage:**

```python
# Simple progress bar
with ProgressBar(total=100, description="Processing postings") as pb:
    for posting in postings:
        process(posting)
        pb.update(1)

# Iterate with progress bar
for posting in progress_bar(postings, description="Scoring"):
    score(posting)

# Spinner for indeterminate progress
with Spinner(description="Verifying seeds"):
    results = verify_seeds()

# Progress tracker for multiple operations
tracker = ProgressTracker(total_operations=5)

# Operation 1
pb = tracker.start_operation("Phase 1: Seed verification", total=len(seeds))
for seed in seeds:
    verify_seed(seed)
    pb.update(1)
tracker.complete_operation()

# Operation 2
pb = tracker.start_operation("Phase 2: Board pulls", total=len(boards))
# ...
```

---

## Summary

These code samples demonstrate:

1. **Error Handling:** Centralized error collection and circuit breaker pattern
2. **Performance:** Batch processing and caching utilities
3. **Architecture:** Repository and service patterns
4. **Testing:** Comprehensive test fixtures and examples
5. **Utilities:** Enhanced logging and progress tracking

Each sample is designed to be:
- **Practical:** Ready to use or adapt
- **Well-documented:** Clear purpose and usage
- **Type-safe:** Proper type hints
- **Testable:** Designed with testing in mind

---

*Last updated: 2026-10-07*
