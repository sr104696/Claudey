# Debugging Guide for Claudey Job Radar

## Table of Contents
1. [Common Issues](#common-issues)
2. [Debugging Techniques](#debugging-techniques)
3. [Logging & Tracing](#logging--tracing)
4. [Testing Strategies](#testing-strategies)
5. [Performance Profiling](#performance-profiling)
6. [Error Patterns](#error-patterns)
7. [Quick Fixes](#quick-fixes)

---

## Common Issues

### 1. Discovery Channels Failing Silently

**Symptoms:**
- No jobs from a specific channel in output
- Channel process exits with code 124 (timeout)
- No error in main run log

**Root Cause:**
- In `pipeline.py:run_discovery()`, channel failures are logged but not propagated
- The main process continues even if critical channels fail

**Debug Steps:**
```bash
# Check individual channel output
cat data/runs/<run_id>/discover_commoncrawl.out

# Run channel manually
python -m radar discover commoncrawl

# Check for exceptions in channel code
python -c "from radar.discover import commoncrawl; commoncrawl.run()"
```

**Fix:**
```python
# In pipeline.py
def run_discovery(channels: list[str]) -> dict[str, int]:
    # ... existing code ...
    
    # Add explicit error propagation
    failed_channels = [ch for ch, c in codes.items() if c != 0]
    if failed_channels:
        raise ChannelFailure(
            f"Discovery channels failed: {failed_channels}. "
            f"See data/runs/{config.run_id()}/discover_<channel>.out for details"
        )
```

---

### 2. Rate Limiting Not Working

**Symptoms:**
- Getting 429 errors from hosts
- Requests going faster than 1 per second
- Hosts blocking the client

**Root Cause:**
- Rate limiting in `http.py:_HostGate` uses file-based locks
- Multiple processes might not coordinate properly
- Some hosts have Crawl-delay > 1 second

**Debug Steps:**
```bash
# Check rate limit logs
python -c "
from radar.http import client
from radar import config
import time

c = client()
start = time.time()
for i in range(10):
    r = c.get('https://example.com')
    print(f'Request {i}: {r.elapsed_ms}ms')
    time.sleep(0.5)  # Should still be rate-limited to 1/s
print(f'Total: {time.time() - start}s')
"

# Check crawl delay
python -c "
from radar.http import client
from radar import robots

c = client()
rules = c.robots_for('https://example.com')
print(f'Crawl delay: {rules.crawl_delay}s')
"
```

**Fix:**
```python
# In http.py, improve rate limiting
class _HostGate:
    def wait_turn(self, host: str, delay: float) -> None:
        # Use a shared lock across processes
        with self._lock(host):
            last_request = self._get_last_request_time(host)
            gap = last_request + delay - time.time()
            if gap > 0:
                time.sleep(gap)
            self._record_request(host)
```

---

### 3. ATS API Failures

**Symptoms:**
- Specific ATS (Greenhouse, Lever, etc.) not returning jobs
- Getting 404 for valid job IDs
- API returning unexpected data format

**Root Cause:**
- ATS API changed
- Rate limiting by ATS
- Authentication issues

**Debug Steps:**
```bash
# Test individual ATS adapter
python -c "
from radar.ats import greenhouse
result = greenhouse.pull('example-board', 'Example Company', 'test')
print(result)
"

# Check raw API response
python -c "
from radar.http import client
c = client()
response = c.get('https://boards.greenhouse.io/v1/boards/example-board/jobs')
print(f'Status: {response.status}')
print(f'Headers: {response.headers}')
print(f'Body: {response.text[:500]}...')
"

# Check if board exists
python -c "
from radar.ats import greenhouse
print(greenhouse.probe('example-board'))
"
```

**Fix:**
```python
# Add better error handling in ATS adapters
class GreenhouseAdapter:
    def pull(self, board: str, company: str, source: str) -> tuple[str, list[Posting]]:
        try:
            # ... existing code ...
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return "rate_limited", []
            elif e.response.status_code == 404:
                return "board_not_found", []
            else:
                return f"api_error:{e.response.status_code}", []
        except Exception as e:
            return f"error:{type(e).__name__}", []
```

---

### 4. Seed Verification Problems

**Symptoms:**
- Seed rows showing as "unverified" when they should be "open"
- Seed rows not being updated
- Incorrect pay/location information

**Root Cause:**
- URL changed but not detected as repost
- ATS API not returning job
- Verification logic bug

**Debug Steps:**
```bash
# Check seed verification report
cat out/seed_verification_<date>.md

# Verify a specific seed URL
python -c "
from radar.verify import verify_url
result = verify_url('https://example.com/job', 'Example Company')
print(f'Status: {result.status}')
print(f'Evidence: {result.evidence}')
if result.posting:
    print(f'Posting: {result.posting.title}')
"

# Check if job exists on employer board
python -c "
from radar.ats import greenhouse
print(greenhouse.verify('example-board', 'job-id', 'Example Company', 'test'))
"
```

**Fix:**
```python
# Improve seed verification logic
class SeedVerifier:
    def verify_row(self, row: SeedRow) -> SeedResult:
        # Try direct URL first
        result = verify_url(row.url, row.company)
        
        if result.status == "unverified":
            # Try to find on employer board
            board_info = self._find_employer_board(row.company)
            if board_info:
                result = self._search_board(board_info, row.title)
        
        if result.status == "unverified":
            # Try aggregator URL
            result = verify_url(row.url, row.company)
        
        return result
```

---

### 5. Scoring Issues

**Symptoms:**
- Postings with wrong fit score
- Postings in wrong bucket
- Hard excludes not being applied

**Root Cause:**
- Regex pattern not matching
- Logic error in scoring
- Cached judgment not being used

**Debug Steps:**
```bash
# Check scoring for a specific posting
python -c "
from radar.score import score
from radar.models import Posting

p = Posting(
    title='Legal Counsel',
    company='Example Company',
    description='JD required, 3-5 years experience...',
    # ... other fields
)
scored = score(p)
print(f'Fit score: {scored.fit_score}')
print(f'Fit signals: {scored.fit_signals}')
print(f'Hard exclude: {scored.hard_exclude_reason}')
print(f'Bucket: {scored.bucket}')
"

# Check regex patterns
python -c "
from radar.score import RX
import re

text = 'JD required and 3-5 years of experience'
for name, pattern in RX.items():
    if pattern.search(text):
        print(f'{name}: MATCHED - {pattern.search(text).group()}')
    else:
        print(f'{name}: no match')
"

# Check judgments
python -c "
from radar.score import judgments, judgment_for
from radar.models import Posting

p = Posting(key='test:123', title='Test', company='Test', description='...')
j = judgment_for(p)
print(f'Judgment: {j}')
print(f'All judgments: {list(judgments().keys())[:10]}...')
"
```

**Fix:**
```python
# Add scoring debug mode
import logging
logger = logging.getLogger('radar.score')

def score(p: Posting) -> Posting:
    logger.debug(f'Scoring posting: {p.company} - {p.title}')
    
    # ... existing scoring logic ...
    
    logger.debug(f'Final score: {p.fit_score}, bucket: {p.bucket}')
    return p
```

---

### 6. Deduplication Problems

**Symptoms:**
- Duplicate postings in output
- Different postings being merged
- Postings missing from output

**Root Cause:**
- `dedupe_key()` not unique enough
- Deduplication logic not handling edge cases
- Race condition in deduplication

**Debug Steps:**
```bash
# Check deduplication keys
python -c "
from radar.models import Posting
from radar.phase4 import dedupe

# Create test postings
p1 = Posting(
    key='ats1:board1:job1',
    company='Example Company',
    title='Legal Counsel',
    location='New York, NY',
    # ...
)
p2 = Posting(
    key='ats2:board2:job2', 
    company='Example Company',
    title='Legal Counsel',
    location='New York, NY',
    # ...
)

print(f'Key 1: {p1.dedupe_key()}')
print(f'Key 2: {p2.dedupe_key()}')
print(f'Same key: {p1.dedupe_key() == p2.dedupe_key()}')

# Test deduplication
result = dedupe([p1, p2])
print(f'Deduplicated: {len(result)} postings')
"
```

**Fix:**
```python
# Improve deduplication key
def dedupe_key(self) -> str:
    from .textutil import norm_company, norm_title
    
    # Include job_id if available for better uniqueness
    identifier = self.job_id or self.url or ""
    area = self.loc_bucket or "unknown"
    return f"{norm_company(self.company)}|{norm_title(self.title)}|{area}|{identifier[:50]}"
```

---

## Debugging Techniques

### 1. Interactive Debugging with IPython

```bash
# Start debug shell
python -m radar debug

# Or manually
python -c "
from radar import db, config, http
from IPython import embed

client = http.client()
embed(user_ns={'db': db, 'config': config, 'client': client})
"
```

### 2. Logging Enhancement

```python
# Add verbose logging
import logging

# In your script
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Or via environment variable
RADAR_LOG_LEVEL=DEBUG python -m radar refresh
```

### 3. Conditional Breakpoints

```python
# Add conditional breakpoints
import pdb

def verify_url(url: str, company: str, source: str = "verify") -> Outcome:
    if "example.com" in url:
        pdb.set_trace()  # Breakpoint only for specific URL
    # ... rest of function
```

### 4. Profiling

```bash
# Profile a run
python -m cProfile -s time python -m radar refresh > profile.txt

# Analyze profile
python -c "
import pstats
p = pstats.Stats('profile.txt')
p.sort_stats('time').print_stats(20)
"
```

---

## Logging & Tracing

### 1. Structured Logging Setup

```python
# radar/logging.py
import logging
import json
import sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        })

def setup_logging(level=logging.INFO, json_format=False):
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if json_format:
        handlers[0].setFormatter(JSONFormatter())
    else:
        handlers[0].setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    logging.basicConfig(
        level=level,
        handlers=handlers
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
```

### 2. Add Logging to Critical Paths

```python
# In http.py
import logging
logger = logging.getLogger('radar.http')

class PoliteClient:
    def request(self, method, url, **kwargs):
        logger.debug(f'Request: {method} {url}')
        start = time.time()
        try:
            result = self._one(method, url, **kwargs)
            logger.debug(f'Response: {result.status} in {result.elapsed_ms}ms')
            return result
        except Exception as e:
            logger.error(f'Request failed: {method} {url}: {e}')
            raise
```

### 3. Trace System

```python
# radar/trace.py
import functools
import time
import uuid
from contextlib import contextmanager

class TraceContext:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.events = []
        self.start_time = time.time()
    
    def add_event(self, name, data=None):
        self.events.append({
            'timestamp': time.time(),
            'name': name,
            'data': data,
            'elapsed': time.time() - self.start_time,
        })
    
    def get_trace(self):
        return {
            'trace_id': self.id,
            'start_time': self.start_time,
            'duration': time.time() - self.start_time,
            'events': self.events,
        }

_trace_context = None

@contextmanager
def trace_operation(operation_name):
    global _trace_context
    if _trace_context is None:
        _trace_context = TraceContext()
    
    _trace_context.add_event('start', {'operation': operation_name})
    start = time.time()
    try:
        yield
        _trace_context.add_event('end', {
            'operation': operation_name,
            'duration': time.time() - start,
        })
    except Exception as e:
        _trace_context.add_event('error', {
            'operation': operation_name,
            'error': str(e),
            'duration': time.time() - start,
        })
        raise

def get_current_trace():
    return _trace_context.get_trace() if _trace_context else None

def reset_trace():
    global _trace_context
    _trace_context = None

# Usage example
@trace_operation('phase1')
def verify_seeds():
    # ... existing code ...
```

---

## Testing Strategies

### 1. Unit Testing

```python
# tests/test_score.py
import pytest
from radar.score import score, FIT_MIN
from radar.models import Posting

class TestScoring:
    def test_jd_required_signal(self):
        p = Posting(
            title='Legal Counsel',
            description='JD required',
            jd_required='Y',
        )
        scored = score(p)
        assert scored.fit_score >= 1
        assert 'JD required/preferred' in scored.fit_signals
    
    def test_hard_exclude_sales(self):
        p = Posting(
            title='Sales Engineer',
            description='Must meet quota',
        )
        scored = score(p)
        assert scored.hard_exclude_reason
        assert 'Sales' in scored.hard_exclude_reason
    
    def test_fit_minimum(self):
        p = Posting(
            title='Test',
            description='',
        )
        scored = score(p)
        # Should not be fit with 0 signals
        assert scored.bucket != 'fit' or scored.fit_score >= FIT_MIN
```

### 2. Integration Testing

```python
# tests/test_pipeline.py
import tempfile
import shutil
from pathlib import Path
from radar import pipeline

class TestPipeline:
    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_data = Path.cwd() / 'data'
        shutil.copytree(self.original_data, self.temp_dir / 'data')
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_pipeline(self, monkeypatch):
        # Mock environment
        monkeypatch.setenv('RADAR_RUN_ID', 'test_run')
        
        # Run pipeline
        with monkeypatch.context() as m:
            m.setattr('radar.config.DATA', self.temp_dir / 'data')
            m.setattr('radar.config.OUT', self.temp_dir / 'out')
            
            summary = pipeline.refresh(skip_discovery=True)
        
        # Verify outputs
        assert (self.temp_dir / 'out' / 'open_positions_test_run.md').exists()
        assert summary['fit'] >= 0
```

### 3. Mock HTTP Client

```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch
from radar.http import Result

@pytest.fixture
def mock_client():
    """Mock HTTP client for testing."""
    with patch('radar.http.client') as mock:
        client = MagicMock()
        
        # Default response
        default_response = Result(
            url='https://example.com',
            status=200,
            text='<html></html>',
            headers={'Content-Type': 'text/html'},
        )
        client.get.return_value = default_response
        client.post_json.return_value = default_response
        
        mock.return_value = client
        yield client

@pytest.fixture
def mock_failing_client():
    """Mock HTTP client that fails."""
    with patch('radar.http.client') as mock:
        client = MagicMock()
        client.get.return_value = Result(
            url='https://example.com',
            status=None,
            error='Connection refused',
        )
        mock.return_value = client
        yield client
```

### 4. Property-Based Testing

```python
# tests/test_extraction.py
from hypothesis import given, strategies as st
from radar.extract import pay_from_text, years_required

class TestExtraction:
    @given(st.text(min_size=1, max_size=1000))
    def test_pay_extraction_never_crashes(self, text):
        result = pay_from_text(text)
        assert result is not None
        assert hasattr(result, 'min')
        assert hasattr(result, 'max')
    
    @given(st.text(min_size=1, max_size=500))
    def test_years_extraction_never_crashes(self, text):
        years, context = years_required(text)
        assert years is None or isinstance(years, int)
        assert isinstance(context, str)
    
    @given(st.floats(min_value=50000, max_value=500000))
    def test_pay_display_formatting(self, salary):
        from radar.extract import Pay, pay_display
        p = Pay(min=salary, max=salary * 1.2, type='base')
        display = pay_display(p)
        assert '$' in display
        assert isinstance(display, str)
```

---

## Performance Profiling

### 1. Time Specific Operations

```python
# Add timing decorator
import time
from functools import wraps

def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f'{func.__name__} took {elapsed:.2f}s')
        return result
    return wrapper

# Usage
@timed
def verify_seeds():
    # ... existing code ...
```

### 2. Memory Profiling

```bash
# Install memory profiler
pip install memory-profiler

# Profile memory usage
python -m memory_profiler python -m radar refresh
```

### 3. Custom Metrics

```python
# radar/metrics.py
import time
from contextlib import contextmanager

class MetricsCollector:
    def __init__(self):
        self.counters = {}
        self.timers = {}
        self.start_time = time.time()
    
    def incr(self, name, value=1):
        self.counters[name] = self.counters.get(name, 0) + value
    
    def time(self, name, duration):
        if name not in self.timers:
            self.timers[name] = []
        self.timers[name].append(duration)
    
    def get_stats(self):
        return {
            'counters': self.counters,
            'timers': {
                name: {
                    'count': len(times),
                    'total': sum(times),
                    'avg': sum(times) / len(times) if times else 0,
                    'min': min(times) if times else 0,
                    'max': max(times) if times else 0,
                }
                for name, times in self.timers.items()
            },
            'total_time': time.time() - self.start_time,
        }
    
    def print_stats(self):
        stats = self.get_stats()
        print("\n=== Metrics ===")
        print(f"Total time: {stats['total_time']:.2f}s")
        print("\nCounters:")
        for name, count in stats['counters'].items():
            print(f"  {name}: {count}")
        print("\nTimers:")
        for name, timer_stats in stats['timers'].items():
            print(f"  {name}:")
            print(f"    count: {timer_stats['count']}")
            print(f"    avg: {timer_stats['avg']:.3f}s")
            print(f"    total: {timer_stats['total']:.3f}s")

# Global metrics collector
metrics = MetricsCollector()

@contextmanager
def timed_operation(name):
    start = time.time()
    try:
        yield
    finally:
        metrics.time(name, time.time() - start)

# Usage in pipeline
with timed_operation('phase1'):
    results, closed = phase1.verify_seeds()
```

---

## Error Patterns

### 1. Common Error Types

| Error | Cause | Solution |
|-------|-------|----------|
| `httpx.TimeoutException` | Request timeout | Increase timeout, add retry |
| `httpx.HTTPStatusError: 429` | Rate limited | Respect Retry-After header |
| `httpx.HTTPStatusError: 403` | Access denied | Check robots.txt, user agent |
| `JSONDecodeError` | Invalid JSON | Check response content, improve parsing |
| `KeyError` | Missing field | Add validation, use .get() with defaults |
| `ValueError` | Invalid value | Add input validation |

### 2. Error Handling Patterns

```python
# Consistent error handling pattern
from dataclasses import dataclass
from typing import Optional

@dataclass
class Result:
    success: bool
    value: Optional[any] = None
    error: Optional[str] = None
    
    @classmethod
    def ok(cls, value):
        return cls(success=True, value=value)
    
    @classmethod
    def error(cls, error):
        return cls(success=False, error=error)

def safe_operation() -> Result:
    try:
        value = do_operation()
        return Result.ok(value)
    except Exception as e:
        return Result.error(str(e))

# Usage
result = safe_operation()
if result.success:
    process(result.value)
else:
    log_error(result.error)
```

### 3. Retry Logic

```python
# Enhanced retry with exponential backoff
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception,
    RetryError,
)
import httpx

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception(lambda e: isinstance(e, (
        httpx.TimeoutException,
        httpx.HTTPStatusError,
    ))),
)
def fetch_with_retry(url):
    response = client().get(url)
    if response.status == 429:
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            time.sleep(int(retry_after))
        raise httpx.HTTPStatusError("Rate limited", request=None, response=response)
    response.raise_for_status()
    return response
```

---

## Quick Fixes

### 1. Fix CommonCrawl Timeout

```python
# In pipeline.py
CHANNEL_TIMEOUT_S = 50 * 60  # Reduce from 50 minutes
# Or make it configurable
CHANNEL_TIMEOUT_S = float(os.getenv('RADAR_CHANNEL_TIMEOUT', 30 * 60))
```

### 2. Improve Error Reporting

```python
# In __main__.py
import traceback

def main(argv: list[str] | None = None) -> int:
    try:
        # ... existing code ...
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        print("\nFull traceback:", file=sys.stderr)
        traceback.print_exc()
        
        # Also save to file
        with open(f"data/runs/{config.run_id()}/error.log", "w") as f:
            traceback.print_exc(file=f)
        
        return 1
```

### 3. Add Validation for Inputs

```python
# In leads.py
from pydantic import ValidationError, field_validator

class Lead(BaseModel):
    # ... existing fields ...
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v:
            raise ValueError('URL cannot be empty')
        if not v.startswith(('http://', 'https://')):
            raise ValueError(f'Invalid URL scheme: {v}')
        return v
    
    @field_validator('company')
    @classmethod
    def validate_company(cls, v):
        if v and len(v) > 200:
            raise ValueError(f'Company name too long: {len(v)} chars')
        return v
```

### 4. Add Health Check Endpoint

```python
# radar/health.py (add)
def check_health() -> dict:
    """Check health of all critical components."""
    checks = {
        'database': check_database(),
        'cache': check_cache(),
        'http_client': check_http_client(),
        'ats_adapters': check_ats_adapters(),
    }
    
    all_healthy = all(c['status'] == 'healthy' for c in checks.values())
    
    return {
        'status': 'healthy' if all_healthy else 'degraded',
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat(),
    }

def check_database() -> dict:
    try:
        conn = db.conn()
        conn.execute('SELECT 1')
        return {'status': 'healthy'}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}
```

---

## 🎯 Debugging Checklist

### Before Reporting a Bug

1. [ ] Check the run log: `cat out/run_log.md`
2. [ ] Check individual channel outputs: `cat data/runs/<run_id>/discover_<channel>.out`
3. [ ] Run the failing component in isolation
4. [ ] Check for recent changes in git history
5. [ ] Verify environment variables are set correctly
6. [ ] Check disk space and permissions
7. [ ] Try with a fresh cache: `rm -rf cache/`

### When Debugging

1. [ ] Add logging to trace the execution path
2. [ ] Check intermediate data (JSONL files in data/runs/)
3. [ ] Verify network connectivity to failing hosts
4. [ ] Check robots.txt for blocked hosts
5. [ ] Test with a minimal example
6. [ ] Check for race conditions in concurrent code
7. [ ] Verify database integrity

### After Fixing

1. [ ] Add a test case for the bug
2. [ ] Add logging for future debugging
3. [ ] Update documentation if needed
4. [ ] Clean up any temporary debug code
5. [ ] Verify the fix with the original reproduction case

---

## 📚 Additional Resources

- [Python Debugging Guide](https://realpython.com/python-debugging-pdb/)
- [HTTPX Documentation](https://www.python-httpx.org/)
- [Pydantic Documentation](https://pydantic.dev/)
- [Testing with pytest](https://docs.pytest.org/)
- [Profiling Python](https://realpython.com/python-profiling/)

---

*Last updated: 2026-10-07*
