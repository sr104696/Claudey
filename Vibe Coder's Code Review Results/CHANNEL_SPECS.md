# Discovery Channel Specifications

This document provides **detailed technical specifications** for each proposed new discovery channel, including API endpoints, parsing logic, rate limiting, and error handling.

---

## 1. AI Startup Jobs Channel

### Overview
- **Website:** https://aistartupjobs.com
- **Focus:** AI/ML startup jobs, including Legal-AI, AI governance, policy roles
- **Relevance:** High for Legal-AI research/build seats

### Technical Details

#### Website Structure
```
URL Pattern: https://aistartupjobs.com/jobs
            https://aistartupjobs.com/remote-jobs
            https://aistartupjobs.com/jobs/{id}

Page Structure:
- Job listings are in <div class="job-card"> elements
- Each card contains: company, title, location, URL, description
- Pagination at bottom
```

#### API Endpoints (if available)
```
Primary: GET https://aistartupjobs.com/api/jobs
Params:
  - page: int (pagination)
  - per_page: int (default 20)
  - remote: bool (filter for remote jobs)
  - search: str (keyword search)

Example:
GET https://aistartupjobs.com/api/jobs?page=1&per_page=50&search=legal
```

#### Parsing Logic

**File:** `radar/discover/aistartupjobs.py`

```python
import re
from bs4 import BeautifulSoup  # or use selectolax

JOB_CARD_SELECTOR = "div.job-card, li.job-listing, .job-item"
COMPANY_SELECTOR = "span.company, .company-name, .employer"
TITLE_SELECTOR = "h2, h3, .title, .job-title"
LOCATION_SELECTOR = "span.location, .location, .job-location"
URL_SELECTOR = "a.job-link, a[href*='/jobs/']"


def parse_job_cards(html: str) -> list[dict]:
    """Parse job cards from AI Startup Jobs HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    
    for card in soup.select(JOB_CARD_SELECTOR):
        try:
            job = {
                'company': extract_text(card, COMPANY_SELECTOR),
                'title': extract_text(card, TITLE_SELECTOR),
                'location': extract_text(card, LOCATION_SELECTOR),
                'url': extract_href(card, URL_SELECTOR),
                'description': extract_text(card, '.description')[:500]  # First 500 chars
            }
            
            # Normalize URL
            if job['url'] and not job['url'].startswith('http'):
                job['url'] = f"https://aistartupjobs.com{job['url']}"
            
            jobs.append(job)
        except Exception as e:
            # Log parsing error but continue
            continue
    
    return jobs


def extract_text(element, selector: str) -> str:
    """Extract text from element using selector."""
    el = element.select_one(selector)
    return el.get_text(strip=True) if el else ""


def extract_href(element, selector: str) -> str:
    """Extract href from element using selector."""
    el = element.select_one(selector)
    return el['href'] if el and el.has_attr('href') else ""
```

#### Filtering Logic

```python
LEGAL_AI_KEYWORDS = re.compile(
    r"legal|ai governance|ai policy|compliance|regulatory|ethics|safety|"
    r"responsible ai|ai counsel|legal engineer|applied legal|research|"
    r"counsel|attorney|lawyer|general counsel|policy|risk|fintech|payments",
    re.I
)

EXCLUDE_KEYWORDS = re.compile(
    r"engineer|developer|software|data scientist|quant|ml engineer|"
    r"sales|marketing|business development|intern|summer",
    re.I
)


def is_relevant(job: dict) -> bool:
    """Check if job is relevant to our search."""
    text = f"{job['title']} {job['description']} {job.get('company', '')}"
    
    # Must match legal/AI keywords
    if not LEGAL_AI_KEYWORDS.search(text):
        return False
    
    # Must not match exclude keywords (unless legal context)
    if EXCLUDE_KEYWORDS.search(text):
        # Allow if legal context
        if not re.search(r"legal|law|counsel|attorney", text, re.I):
            return False
    
    return True
```

#### Rate Limiting
- **Requests per second:** 1 (respect robots.txt)
- **Delay between requests:** 1 second
- **Concurrent requests:** 1 (single-threaded)

#### Error Handling
```python
from ..http import client
from ..runlog import record_channel

def safe_get(url: str) -> tuple[bool, str, str]:
    """Safe GET request with error handling."""
    try:
        r = client().get(url)
        if r.ok:
            return True, r.text, ""
        else:
            return False, "", f"HTTP {r.status_code}: {r.reason}"
    except Exception as e:
        return False, "", f"{type(e).__name__}: {e}"
```

#### Expected Output
```json
{
  "urls_checked": 2,
  "leads": 15,
  "failures": [],
  "notes": "Found 15 legal/AI roles from 2 URLs"
}
```

---

## 2. Legal Tech Boards Channel

### Overview
- **Boards:** 
  - legaloperationsjobboard.com
  - goinhouse.com
  - legal.io
- **Focus:** Legal operations, in-house counsel, legal tech roles
- **Relevance:** High for legal tech and operations roles

### Technical Details

#### Website Structures

**legaloperationsjobboard.com:**
```
URL: https://legaloperationsjobboard.com/job-board
Structure: Table-based layout
  - <table class="job-table">
  - <tr class="job-row">
  - Columns: Company, Title, Location, Date, URL
```

**goinhouse.com:**
```
URL: https://www.goinhouse.com/jobs
Structure: Grid layout
  - <div class="job-grid">
  - <div class="job-card">
  - Elements: company, title, location, type, URL
```

**legal.io:**
```
URL: https://legal.io/jobs
Structure: List layout
  - <ul class="job-list">
  - <li class="job-item">
  - Elements: company, title, location, URL
```

#### Parsing Logic

**File:** `radar/discover/legaltech.py`

```python
from concurrent.futures import ThreadPoolExecutor
from ..http import client

BOARD_CONFIGS = {
    "legaloperationsjobboard.com": {
        "url": "https://legaloperationsjobboard.com/job-board",
        "job_selector": "tr.job-row, .job-listing",
        "company_selector": "td:first-child, .company",
        "title_selector": "td:nth-child(2), .title",
        "location_selector": "td:nth-child(3), .location",
        "url_selector": "a.job-link, a[href*='/jobs/']",
        "pagination": True,
        "pages": 5  # Check first 5 pages
    },
    "goinhouse.com": {
        "url": "https://www.goinhouse.com/jobs",
        "job_selector": ".job-card, .job-item",
        "company_selector": ".company-name",
        "title_selector": ".job-title",
        "location_selector": ".job-location",
        "url_selector": "a.job-link",
        "pagination": True,
        "pages": 3
    },
    "legal.io": {
        "url": "https://legal.io/jobs",
        "job_selector": ".job-item, li.job",
        "company_selector": ".company",
        "title_selector": ".title",
        "location_selector": ".location",
        "url_selector": "a[href*='/jobs/']",
        "pagination": False
    }
}


def scrape_board(board_name: str, config: dict) -> list[Lead]:
    """Scrape a single legal tech board."""
    leads = []
    base_url = config['url']
    
    # Handle pagination
    pages = [1] if not config.get('pagination') else range(1, config['pages'] + 1)
    
    for page in pages:
        url = f"{base_url}?page={page}" if page > 1 else base_url
        r = client().get(url)
        
        if not r.ok:
            continue
        
        # Parse jobs from this page
        jobs = parse_jobs(r.text, config)
        leads.extend(jobs)
    
    return leads


def parse_jobs(html: str, config: dict) -> list[Lead]:
    """Parse jobs from HTML using board-specific selectors."""
    from selectolax.parser import HTMLParser
    
    tree = HTMLParser(html)
    jobs = []
    
    for node in tree.css(config['job_selector']):
        try:
            company = extract_text(node, config['company_selector'])
            title = extract_text(node, config['title_selector'])
            location = extract_text(node, config['location_selector'])
            url = extract_href(node, config['url_selector'])
            
            if url and not url.startswith('http'):
                url = f"https://{board_name}{url}" if url.startswith('/') else f"https://{board_name}/{url}"
            
            jobs.append(Lead(
                source=f"legaltech:{board_name}",
                url=url,
                company=company,
                title=title,
                location=location,
                note=f"{board_name} - Legal tech roles"
            ))
        except Exception:
            continue
    
    return jobs
```

#### Rate Limiting
- **Requests per second:** 1 per board
- **Delay between board requests:** 2 seconds (to avoid overwhelming)
- **Concurrent boards:** 3 (ThreadPoolExecutor)

#### Error Handling
```python
def scrape_all_boards() -> tuple[list[Lead], list[str]]:
    """Scrape all legal tech boards with error handling."""
    leads = []
    failures = []
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            board: executor.submit(scrape_board, board, config)
            for board, config in BOARD_CONFIGS.items()
        }
        
        for board, future in futures.items():
            try:
                leads.extend(future.result())
            except Exception as e:
                failures.append(f"{board}: {type(e).__name__}: {e}")
    
    return leads, failures
```

#### Expected Output
```json
{
  "boards_scraped": 3,
  "leads": 45,
  "failures": [],
  "notes": "Scraped 3 boards, found 45 leads"
}
```

---

## 3. Reddit r/legaltech Channel

### Overview
- **Subreddit:** r/legaltech
- **Focus:** Legal technology discussions and job postings
- **API:** Reddit JSON API (no authentication required for public data)
- **Relevance:** Medium-high for legal tech roles, startups, and innovative legal practices

### Technical Details

#### API Endpoints
```
Primary: GET https://www.reddit.com/r/legaltech/new.json
        GET https://www.reddit.com/r/legaltech/hot.json
        GET https://www.reddit.com/r/legaltech/top.json?t=week

Params:
  - limit: int (1-100, default 25)
  - t: str (hour, day, week, month, year, all)
  - after: str (pagination, fullname of last post)
  - before: str (pagination)

Headers:
  - User-Agent: Must be unique and descriptive

Example:
GET https://www.reddit.com/r/legaltech/new.json?limit=100&t=week
```

#### Parsing Logic

**File:** `radar/discover/reddit_legaltech.py`

```python
import json
import re
from datetime import datetime, timedelta
from ..http import client

SUBREDDIT = "legaltech"
BASE_URL = f"https://www.reddit.com/r/{SUBREDDIT}"
API_URL = f"{BASE_URL}/new.json"

JOB_INDICATORS = re.compile(
    r"hiring|job|position|opening|role|career|employment|"
    r"recruiting|we're hiring|join us|work with us|now hiring",
    re.I
)


def get_reddit_posts(limit: int = 100, time_range: str = "week") -> list[dict]:
    """Get posts from r/legaltech."""
    params = {
        "limit": limit,
        "t": time_range
    }
    
    headers = {
        "User-Agent": "JobRadar/1.0 (personal job-search tool; read-only)"
    }
    
    r = client().get(API_URL, params=params, headers=headers)
    
    if not r.ok:
        return []
    
    try:
        data = r.json()
        return data.get('data', {}).get('children', [])
    except json.JSONDecodeError:
        return []


def is_job_post(post_data: dict) -> bool:
    """Check if a Reddit post is a job posting."""
    title = post_data.get('title', '')
    text = post_data.get('selftext', '')
    
    # Check title
    if JOB_INDICATORS.search(title):
        return True
    
    # Check for hiring flair
    if post_data.get('link_flair_text') and JOB_INDICATORS.search(post_data['link_flair_text']):
        return True
    
    # Check text for job indicators
    if JOB_INDICATORS.search(text[:500]):  # First 500 chars
        return True
    
    return False


def extract_job_details(post_data: dict) -> dict:
    """Extract job details from a Reddit post."""
    title = post_data.get('title', '')
    text = post_data.get('selftext', '')
    url = f"https://reddit.com{post_data.get('permalink', '')}"
    author = post_data.get('author', '')
    created = post_data.get('created_utc', 0)
    
    # Extract company
    company = extract_company_from_text(title + " " + text)
    
    # Extract location
    location = extract_location_from_text(title + " " + text)
    
    # Check if remote
    is_remote = bool(re.search(r"\bremote\b|\bwfh\b|anywhere", text, re.I))
    
    return {
        'title': title,
        'company': company,
        'location': location or ("Remote" if is_remote else ""),
        'url': url,
        'text': text,
        'author': author,
        'created': created,
        'is_remote': is_remote
    }


def extract_company_from_text(text: str) -> str:
    """Try to extract company name from Reddit post text."""
    # Look for patterns
    patterns = [
        # "at [Company]"
        r"at\s+([A-Z][a-zA-Z\s&]+(?:\s+(?:Inc|LLC|Corp|Group|Labs|Ltd|LP))?)",
        # "[Company] is hiring"
        r"([A-Z][a-zA-Z\s&]+(?:\s+(?:Inc|LLC|Corp|Group|Labs|Ltd|LP))?)\s+is hiring",
        # "[Company] is looking for"
        r"([A-Z][a-zA-Z\s&]+(?:\s+(?:Inc|LLC|Corp|Group|Labs|Ltd|LP))?)\s+is looking",
        # "Join [Company]"
        r"join\s+([A-Z][a-zA-Z\s&]+(?:\s+(?:Inc|LLC|Corp|Group|Labs|Ltd|LP))?)",
        # "Work at [Company]"
        r"work\s+at\s+([A-Z][a-zA-Z\s&]+(?:\s+(?:Inc|LLC|Corp|Group|Labs|Ltd|LP))?)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            company = match.group(1).strip()
            # Clean up
            company = re.sub(r"[\n\r\t]+", " ", company)
            company = re.sub(r"\s+", " ", company)
            return company
    
    return ""


def extract_location_from_text(text: str) -> str:
    """Try to extract location from Reddit post text."""
    # Common location patterns
    patterns = [
        # Remote indicators
        (r"\bremote\b|\bwfh\b|\banywhere\b", "Remote"),
        # US cities
        (r"\bnew york\b|\bnyc\b|\bmanhattan\b", "New York, NY"),
        (r"\bphiladelphia\b|\bphilly\b", "Philadelphia, PA"),
        (r"\bboston\b", "Boston, MA"),
        (r"\bwashington\s+dc\b|\bdc\b", "Washington, DC"),
        (r"\bsan francisco\b|\bsf\b|\bbay area\b", "San Francisco, CA"),
        (r"\blos angeles\b|\bla\b", "Los Angeles, CA"),
        (r"\bchicago\b", "Chicago, IL"),
        # Generic city, state
        (r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b", r"\1, \2"),
        # Just state
        (r"\b([A-Z]{2})\b", r"\1"),
    ]
    
    for pattern, replacement in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            if callable(replacement):
                return replacement(match)
            return replacement
    
    return ""
```

#### Filtering Logic

```python
LEGAL_KEYWORDS = re.compile(
    r"legal|law|counsel|attorney|lawyer|compliance|regulatory|"
    r"policy|risk|fintech|payments|contracts|governance|ethics",
    re.I
)


def is_relevant_job(job_details: dict) -> bool:
    """Check if job is relevant to our search."""
    title = job_details['title']
    text = job_details['text']
    
    # Must have some legal/tech context
    if not LEGAL_KEYWORDS.search(title + " " + text):
        return False
    
    # Check location
    location = job_details['location']
    if location and not is_acceptable_location(location):
        # Unless remote
        if not job_details.get('is_remote'):
            return False
    
    return True


def is_acceptable_location(location: str) -> bool:
    """Check if location is acceptable (NYC, US remote, or US other)."""
    if not location:
        return True  # Will be handled by keep_location later
    
    # NYC area
    if re.search(r"new york|nyc|manhattan|brooklyn|queens|bronx|staten island", location, re.I):
        return True
    
    # US remote
    if re.search(r"remote|anywhere|wfh", location, re.I):
        return True
    
    # US cities
    if re.search(r"philadelphia|philly|boston|dc|washington|san francisco|los angeles|chicago", location, re.I):
        return True
    
    # US states
    if re.search(r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b", location, re.I):
        return True
    
    return False
```

#### Rate Limiting
- **Requests per minute:** Reddit allows 60 requests/minute for unauthenticated
- **Our rate:** 1 request per minute (conservative)
- **User-Agent:** Must be unique and descriptive

#### Error Handling
```python
def safe_reddit_request(url: str, params: dict = None) -> tuple[bool, dict, str]:
    """Safe Reddit API request with error handling."""
    headers = {
        "User-Agent": "JobRadar/1.0 (personal job-search tool; read-only; contact: sethnrosenberg@gmail.com)"
    }
    
    try:
        r = client().get(url, params=params, headers=headers)
        
        if r.status_code == 429:  # Rate limited
            return False, {}, "Rate limited - waiting 60 seconds"
        
        if r.status_code == 403:  # Forbidden
            return False, {}, "Access forbidden - check User-Agent"
        
        if not r.ok:
            return False, {}, f"HTTP {r.status_code}: {r.reason}"
        
        try:
            data = r.json()
            return True, data, ""
        except json.JSONDecodeError as e:
            return False, {}, f"JSON decode error: {e}"
            
    except Exception as e:
        return False, {}, f"{type(e).__name__}: {e}"
```

#### Expected Output
```json
{
  "posts_scanned": 100,
  "leads": 15,
  "failures": [],
  "notes": "Scanned 100 posts, found 15 job postings"
}
```

---

## 4. Penn Law Alumni Channel

### Overview
- **Platform:** TBD (likely Symplicity)
- **Focus:** Penn Law alumni job postings
- **Access:** Requires coordination with Penn Law Career Services
- **Relevance:** Very high (targeted to Penn Law graduates)

### Technical Details

#### Platform Detection

```python
import re
from ..http import client

KNOWN_PLATFORMS = {
    'symplicity': {
        'patterns': [
            r'symplicity\.com',
            r'csm\.symplicity\.com',
            r'law-upenn-csm\.symplicity\.com'
        ],
        'api': 'Symplicity API (if available)',
        'scraping': 'Possible with authentication'
    },
    'handshake': {
        'patterns': [
            r'joinhandshake\.com',
            r'app\.joinhandshake\.com'
        ],
        'api': 'Handshake API (restricted)',
        'scraping': 'Difficult without partnership'
    },
    '12twenty': {
        'patterns': [
            r'12twenty\.com',
            r'app\.12twenty\.com'
        ],
        'api': '12Twenty API',
        'scraping': 'Possible with authentication'
    },
    'custom': {
        'patterns': [],
        'api': 'Custom Penn portal',
        'scraping': 'Depends on implementation'
    }
}


def detect_platform(url: str = None) -> dict:
    """Detect which platform Penn Law uses."""
    if url is None:
        url = "https://www.law.upenn.edu/career/alumni-jobs"
    
    try:
        r = client().get(url)
        if not r.ok:
            return {'platform': 'unknown', 'error': f'Failed to fetch {url}'}
        
        html = r.text.lower()
        
        for platform, config in KNOWN_PLATFORMS.items():
            for pattern in config['patterns']:
                if re.search(pattern, url.lower()) or re.search(pattern, html):
                    return {
                        'platform': platform,
                        'url': url,
                        'config': config
                    }
        
        return {'platform': 'custom', 'url': url}
        
    except Exception as e:
        return {'platform': 'unknown', 'error': str(e)}
```

#### Symplicity Implementation (if detected)

```python
SYMPLICITY_BASE = "https://law-upenn-csm.symplicity.com"


def scrape_symplicity() -> list[Lead]:
    """Scrape Symplicity job board."""
    leads = []
    
    # Symplicity typically requires authentication
    # Options:
    # 1. Use provided credentials
    # 2. Check for public job listings
    # 3. Use API if available
    
    # Try public listings first
    public_url = f"{SYMPLICITY_BASE}/students"
    r = client().get(public_url)
    
    if r.ok:
        # Parse public job listings
        leads = parse_symplicity_public(r.text)
    
    return leads


def parse_symplicity_public(html: str) -> list[Lead]:
    """Parse public Symplicity job listings."""
    from selectolax.parser import HTMLParser
    
    tree = HTMLParser(html)
    leads = []
    
    # Symplicity job listings are typically in a table
    for row in tree.css('tr.job-row, .job-listing'):
        try:
            title = extract_text(row, 'td.job-title, .title')
            company = extract_text(row, 'td.company, .employer')
            location = extract_text(row, 'td.location, .location')
            url = extract_href(row, 'a.job-link')
            
            if url and not url.startswith('http'):
                url = f"{SYMPLICITY_BASE}{url}" if url.startswith('/') else url
            
            leads.append(Lead(
                source="alumni_pennlaw:symplicity",
                url=url,
                company=company,
                title=title,
                location=location,
                note="Penn Law Alumni - Symplicity"
            ))
        except Exception:
            continue
    
    return leads
```

#### Custom Portal Implementation

```python
PENN_LAW_URL = "https://www.law.upenn.edu/career/alumni-jobs"


def scrape_penn_law_custom() -> list[Lead]:
    """Scrape custom Penn Law job portal."""
    leads = []
    
    r = client().get(PENN_LAW_URL)
    
    if r.ok:
        leads = parse_penn_law_page(r.text)
    
    return leads


def parse_penn_law_page(html: str) -> list[Lead]:
    """Parse Penn Law custom job portal page."""
    from selectolax.parser import HTMLParser
    
    tree = HTMLParser(html)
    leads = []
    
    # Look for job listing containers
    # Common patterns:
    # - <div class="job"> or <div class="job-listing">
    # - <article class="job-post">
    # - <li class="job-item">
    
    for container in tree.css('.job, .job-listing, .job-post, .job-item'):
        try:
            title = extract_text(container, 'h2, h3, .title')
            company = extract_text(container, '.company, .employer')
            location = extract_text(container, '.location')
            url = extract_href(container, 'a[href]')
            
            if url and not url.startswith('http'):
                if url.startswith('/'):
                    url = f"https://www.law.upenn.edu{url}"
                else:
                    url = f"{PENN_LAW_URL}/{url}"
            
            leads.append(Lead(
                source="alumni_pennlaw:custom",
                url=url,
                company=company,
                title=title,
                location=location,
                note="Penn Law Alumni - Custom Portal"
            ))
        except Exception:
            continue
    
    return leads
```

#### Rate Limiting
- **Requests per second:** 1 (conservative)
- **Delay between requests:** 2 seconds (to be respectful)
- **Authentication:** If required, use provided credentials

#### Error Handling
```python
def safe_alumni_request(url: str, auth: dict = None) -> tuple[bool, str, str]:
    """Safe request to alumni board with optional authentication."""
    try:
        if auth:
            r = client().get(url, auth=auth)
        else:
            r = client().get(url)
        
        if r.status_code == 403:
            return False, "", "Access forbidden - authentication may be required"
        
        if r.status_code == 401:
            return False, "", "Unauthorized - invalid credentials"
        
        if not r.ok:
            return False, "", f"HTTP {r.status_code}: {r.reason}"
        
        return True, r.text, ""
        
    except Exception as e:
        return False, "", f"{type(e).__name__}: {e}"
```

#### Expected Output
```json
{
  "board": "penn_law_alumni",
  "platform": "symplicity",
  "access_level": "public",
  "leads": 25,
  "recommendation": "Contact Penn Law Career Services for API access"
}
```

---

## Common Utilities

### Location Classification

**File:** `radar/discover/common.py` (enhance existing)

```python
from ..extract import classify_location, best_bucket
from .common import KEEP


def is_acceptable_location(location: str) -> bool:
    """Check if location is in our acceptable buckets."""
    if not location:
        return True  # Will be handled later
    
    bucket = classify_location(location)
    return bucket in KEEP


def normalize_location(location: str) -> str:
    """Normalize location string for consistent storage."""
    if not location:
        return ""
    
    # Common normalizations
    location = location.strip()
    location = re.sub(r"\s+", " ", location)
    location = re.sub(r"\bNY\b", "New York", location)
    location = re.sub(r"\bDC\b", "Washington, DC", location)
    location = re.sub(r"\bSF\b", "San Francisco", location)
    location = re.sub(r"\bLA\b", "Los Angeles", location)
    
    return location
```

### Company Normalization

```python
from ..textutil import norm_company


def normalize_company(company: str) -> str:
    """Normalize company name for deduplication."""
    if not company:
        return ""
    
    # Use existing norm_company
    return norm_company(company)


def extract_company_domain(url: str) -> str:
    """Extract domain from URL for company matching."""
    from urllib.parse import urlparse
    
    if not url:
        return ""
    
    try:
        domain = urlparse(url).netloc
        # Remove www. prefix
        domain = re.sub(r"^www\.", "", domain)
        return domain
    except:
        return ""
```

### Lead Deduplication

```python
def is_duplicate(new_lead: Lead, existing_leads: list[Lead]) -> bool:
    """Check if a lead is a duplicate of an existing one."""
    for existing in existing_leads:
        # Same URL
        if new_lead.url == existing.url:
            return True
        
        # Same company and title (normalized)
        if (normalize_company(new_lead.company) == normalize_company(existing.company) and
            normalize_title(new_lead.title) == normalize_title(existing.title)):
            return True
    
    return False


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    if not title:
        return ""
    
    title = title.lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    
    # Remove common prefixes/suffixes
    title = re.sub(r"\b(senior|junior|mid-level|associate|lead|principal)\b", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    
    return title
```

---

## Testing Specifications

### Unit Tests

Each channel should have unit tests for:
1. URL parsing
2. Job extraction
3. Relevance filtering
4. Location classification
5. Error handling

**Example test structure:**
```python
# test_aistartupjobs.py
import pytest
from radar.discover.aistartupjobs import parse_job_cards, is_relevant


def test_parse_job_cards():
    html = """
    <div class="job-card">
        <span class="company">Harvey</span>
        <h3 class="title">Legal Engineer</h3>
        <span class="location">New York, NY</span>
        <a href="/jobs/123">Apply</a>
    </div>
    """
    jobs = parse_job_cards(html)
    assert len(jobs) == 1
    assert jobs[0]['company'] == 'Harvey'
    assert jobs[0]['title'] == 'Legal Engineer'
    assert jobs[0]['location'] == 'New York, NY'


def test_is_relevant():
    job = {
        'title': 'Legal Engineer',
        'description': 'Build AI legal research tools',
        'company': 'Harvey'
    }
    assert is_relevant(job) == True
    
    job['title'] = 'Software Engineer'
    assert is_relevant(job) == False
```

### Integration Tests

Test each channel in isolation:
```bash
# Test AI Startup Jobs
python -m pytest tests/test_aistartupjobs.py -v

# Test Legal Tech
python -m pytest tests/test_legaltech.py -v

# Test Reddit
python -m pytest tests/test_reddit_legaltech.py -v
```

### End-to-End Tests

Test full pipeline with new channels:
```bash
# Run full refresh
python -m radar refresh --channels aistartupjobs legaltech reddit_legaltech

# Check outputs
python -m pytest tests/test_pipeline_integration.py -v
```

---

## Monitoring Specifications

### Metrics to Track

1. **Channel Performance:**
   - Number of leads discovered per run
   - Number of leads that pass relevance filtering
   - Number of leads that result in verified postings

2. **Quality Metrics:**
   - Percentage of leads that become fit postings
   - Percentage that become poor match
   - Percentage that are duplicates

3. **Error Metrics:**
   - Number of failed requests
   - Types of errors (timeout, 404, 403, etc.)
   - Time spent on each channel

### Monitoring Implementation

**File:** `radar/monitoring.py` (NEW)

```python
import json
from pathlib import Path
from datetime import datetime

MONITORING_FILE = Path("data/monitoring.jsonl")


def log_channel_metrics(channel: str, metrics: dict):
    """Log metrics for a discovery channel."""
    record = {
        'timestamp': datetime.utcnow().isoformat(),
        'channel': channel,
        **metrics
    }
    
    with open(MONITORING_FILE, 'a') as f:
        f.write(json.dumps(record) + '\n')


def get_channel_performance(channel: str, days: int = 30) -> dict:
    """Get performance metrics for a channel over time."""
    if not MONITORING_FILE.exists():
        return {}
    
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    metrics = []
    with open(MONITORING_FILE) as f:
        for line in f:
            record = json.loads(line)
            if record['channel'] == channel:
                ts = datetime.fromisoformat(record['timestamp'])
                if ts >= cutoff:
                    metrics.append(record)
    
    return aggregate_metrics(metrics)


def aggregate_metrics(metrics: list[dict]) -> dict:
    """Aggregate metrics over time."""
    if not metrics:
        return {}
    
    total_leads = sum(m.get('leads', 0) for m in metrics)
    total_verified = sum(m.get('verified_open', 0) for m in metrics)
    total_failures = sum(m.get('failures', 0) for m in metrics)
    
    return {
        'total_runs': len(metrics),
        'avg_leads_per_run': total_leads / len(metrics),
        'avg_verified_per_run': total_verified / len(metrics),
        'avg_failures_per_run': total_failures / len(metrics),
        'success_rate': total_verified / total_leads if total_leads > 0 else 0
    }
```

### Dashboard

**File:** `docs/CHANNEL_DASHBOARD.md` (generated)

```markdown
# Discovery Channel Performance Dashboard

Generated: {date}

## Channel Summary

| Channel | Runs (30d) | Avg Leads/Run | Avg Verified/Run | Success Rate | Failures/Run |
|---------|------------|---------------|------------------|--------------|--------------|
| aistartupjobs | {runs} | {avg_leads:.1f} | {avg_verified:.1f} | {success_rate:.1%} | {avg_failures:.1f} |
| legaltech | {runs} | {avg_leads:.1f} | {avg_verified:.1f} | {success_rate:.1%} | {avg_failures:.1f} |
| reddit_legaltech | {runs} | {avg_leads:.1f} | {avg_verified:.1f} | {success_rate:.1%} | {avg_failures:.1f} |
| alumni_pennlaw | {runs} | {avg_leads:.1f} | {avg_verified:.1f} | {success_rate:.1%} | {avg_failures:.1f} |

## Recent Activity

### Last 7 Days
- **Total leads discovered:** {total_leads}
- **Total verified postings:** {total_verified}
- **Total failures:** {total_failures}

### Channel Breakdown
{channel_details}

## Alerts

{alerts}
```

---

## Deployment Checklist

### Before Deployment

- [ ] All new channels have unit tests
- [ ] All new channels pass integration tests
- [ ] Rate limiting is properly configured
- [ ] Error handling is comprehensive
- [ ] Logging is in place
- [ ] Monitoring is configured

### Deployment Steps

1. **Add new files:**
   ```bash
   cp radar/discover/aistartupjobs.py radar/discover/
   cp radar/discover/legaltech.py radar/discover/
   cp radar/discover/reddit_legaltech.py radar/discover/
   cp radar/discover/alumni.py radar/discover/
   ```

2. **Update pipeline.py:**
   ```python
   CHANNELS = ["public_sector", "official_apis", "hn", "commoncrawl", "websearch", "wayback", "aistartupjobs", "legaltech", "reddit_legaltech", "alumni"]
   ```

3. **Update requirements.txt:**
   ```
   # Add any new dependencies
   beautifulsoup4==4.12.2
   ```

4. **Run tests:**
   ```bash
   python -m pytest tests/ -v
   ```

5. **Deploy:**
   ```bash
   git add -A
   git commit -m "Add niche discovery channels: AI Startup Jobs, Legal Tech, Reddit, Alumni"
   git push
   ```

### Post-Deployment

- [ ] Monitor first run closely
- [ ] Check for errors in run log
- [ ] Verify leads are being discovered
- [ ] Verify postings are being created
- [ ] Check scoring is working correctly
- [ ] Monitor performance for 1 week

---

## Maintenance Guide

### Regular Maintenance

1. **Weekly:**
   - Check channel performance metrics
   - Review failures and errors
   - Update search queries as needed

2. **Monthly:**
   - Review and update board URLs
   - Check for website structure changes
   - Update parsing logic if needed

3. **Quarterly:**
   - Review channel effectiveness
   - Consider adding new boards
   - Remove underperforming channels
   - Update dependencies

### Troubleshooting

**Issue: Channel returns 0 leads**
- Check if website structure changed
- Verify URL is still valid
- Test manually in browser
- Check for CAPTCHA or bot protection

**Issue: High failure rate**
- Check rate limiting
- Verify authentication (if required)
- Test network connectivity
- Review error messages

**Issue: Low relevance rate**
- Review filtering logic
- Check keyword patterns
- Sample discovered leads
- Adjust relevance criteria

**Issue: Duplicates**
- Check deduplication logic
- Review company/title normalization
- Check URL matching
- Verify across channels

---

*Channel Specifications created by: Vibe Coder*
*Date: 2026-09-25*
*Repository: sr104696/Claudey*
