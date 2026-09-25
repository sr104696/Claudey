# Implementation Plan: Enhanced Discovery Channels

## Overview

This plan outlines the **step-by-step implementation** of the recommendations from the comprehensive code review. The goal is to **expand discovery coverage** to include niche job boards, AI/legal tech platforms, and alumni networks.

---

## Phase 1: Foundation (Week 1)

### Day 1-2: Enhanced Search Queries

**Objective:** Expand web search coverage to capture more niche postings

#### Task 1.1: Update search_queries.csv

**File:** `seeds/search_queries.csv`

**Action:** Add 25+ new targeted search queries

```bash
# Backup existing file
cp seeds/search_queries.csv seeds/search_queries.csv.backup

# Add new queries (append to existing file)
cat >> seeds/search_queries.csv << 'EOF'
# AI/Legal Tech specific
"site:aistartupjobs.com legal counsel OR legal engineer OR ai policy OR ai governance",websearch:ats,0
"site:aistartupjobs.com regulatory counsel OR compliance OR ai ethics",websearch:ats,0
"site:legaloperationsjobboard.com legal operations OR legal tech OR legal engineer",websearch:aggregator,0
"site:goinhouse.com in-house counsel OR product counsel OR regulatory counsel fintech",websearch:aggregator,0
"site:legal.io general counsel OR legal analyst OR compliance",websearch:aggregator,0

# Penn Law specific
"site:law.upenn.edu career OR jobs OR employment OR alumni",websearch:alumni,0
"Penn Law JD hiring OR Penn Law graduate OR University of Pennsylvania Law School",websearch:alumni,0

# Additional aggregators
"site:angellist.com legal counsel OR regulatory OR compliance fintech",websearch:aggregator,0
"site:ycombinator.com/jobs legal OR counsel OR regulatory OR compliance",websearch:aggregator,0
"site:wellfound.com legal OR counsel OR regulatory OR compliance",websearch:aggregator,0

# Niche legal boards
"site:lawjobs.com OR site:lawcrossing.com regulatory counsel OR product counsel",websearch:aggregator,0
"site:legal500.com jobs OR careers regulatory OR compliance",websearch:aggregator,0

# Specialized finance/legal
"site:efinancialcareers.com legal OR counsel OR regulatory OR compliance",websearch:aggregator,0
"site:rigzone.com legal OR counsel OR regulatory OR compliance energy",websearch:aggregator,0

# Location expansion (Philadelphia, DC, Boston)
"site:job-boards.greenhouse.io legal analyst OR regulatory counsel Philadelphia OR DC OR Boston",websearch:ats,0
"site:jobs.ashbyhq.com legal analyst OR regulatory counsel Philadelphia OR DC OR Boston",websearch:ats,0
EOF
```

**Verification:**
```bash
# Count new queries
wc -l seeds/search_queries.csv
# Should be ~40-45 lines (original 15 + 25+ new)

# Validate CSV format
python3 -c "import csv; list(csv.DictReader(open('seeds/search_queries.csv')))"
```

#### Task 1.2: Update Common Crawl Patterns

**File:** `radar/discover/commoncrawl.py`

**Action:** Add more ATS patterns and legal board detection

```python
# Add to PATTERNS dict (around line 20)
PATTERNS = {
    "greenhouse": ["job-boards.greenhouse.io/*", "boards.greenhouse.io/*"],
    "lever": ["jobs.lever.co/*"],
    "ashby": ["jobs.ashbyhq.com/*"],
    "workday": ["*.wd*.myworkdayjobs.com/*"],  # NEW
    "workable": ["apply.workable.com/*"],     # NEW
    "bamboohr": ["*.bamboohr.com/careers/*"],  # NEW
    "recruitee": ["*.recruitee.com/*"],       # NEW
}

# Add legal board prioritization (around line 120)
LEGAL_BOARD_KEYWORDS = [
    "legal", "counsel", "attorney", "lawyer", "compliance", "regulatory",
    "policy", "risk", "finance", "fintech", "payments", "credit"
]

def prioritize_legal_boards(tokens: set[str]) -> list[str]:
    """Sort tokens to prioritize those likely to have legal roles."""
    scored = []
    for token in tokens:
        score = sum(1 for kw in LEGAL_BOARD_KEYWORDS if kw in token)
        scored.append((score, token))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [t for _, t in scored]

# Update sweep function to use prioritization
# Around line 85 in sweep():
# Change: due.sort(key=lambda t: (t not in fresh[ats], t))
# To: due.sort(key=lambda t: (t not in fresh[ats], prioritize_legal_boards(set(due)).index(t) if t in fresh[ats] else 0))
```

**Verification:**
```bash
# Test syntax
python3 -m py_compile radar/discover/commoncrawl.py

# Check patterns are valid
python3 -c "from radar.discover.commoncrawl import PATTERNS; print(list(PATTERNS.keys()))"
```

#### Task 1.3: Add Source-Based Scoring Boosts

**File:** `radar/score.py`

**Action:** Add scoring boosts for niche sources

```python
# Add around line 30 (after EXCL dict)
SOURCE_BOOSTS = {
    "aistartupjobs": 1,  # AI/legal tech focus
    "legaltech": 1,       # Legal tech boards
    "alumni_pennlaw": 2,  # High relevance - Penn Law network
    "hn_whoishiring": 0.5,
    "public_sector": 0.5,
}

# Update score() function around line 150
# After: p.fit_score = len(sig)
# Add:
    # Add source-based boost
    source_boost = sum(SOURCE_BOOSTS.get(src.split(":")[0], 0) 
                       for src in p.sources if src in SOURCE_BOOSTS)
    p.fit_score += int(source_boost)
    
    # Add niche source signal
    niche_sources = [src for src in p.sources 
                     if src.startswith(("aistartupjobs", "legaltech", "alumni"))]
    if niche_sources:
        p.fit_signals.append(f"niche source: {', '.join(niche_sources)}")
```

**Verification:**
```bash
python3 -m py_compile radar/score.py
python3 -c "from radar.score import SOURCE_BOOSTS; print(SOURCE_BOOSTS)"
```

---

## Phase 2: Niche Job Boards (Week 2)

### Day 3-4: AI Startup Jobs Channel

**File:** `radar/discover/aistartupjobs.py` (NEW)

**Action:** Create new discovery channel

```python
"""AI Startup Jobs (aistartupjobs.com) - Specialized AI/ML startup job board.

High relevance for Legal-AI research/build seats, AI governance, policy roles.
"""
from __future__ import annotations

import re
from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from ..textutil import html_to_text
from .common import keep_location

AI_STARTUP_URLS = [
    "https://aistartupjobs.com/jobs",
    "https://aistartupjobs.com/remote-jobs",
]

LEGAL_AI_KEYWORDS = re.compile(
    r"legal|ai governance|ai policy|compliance|regulatory|ethics|safety|responsible ai|"
    r"ai counsel|legal engineer|applied legal|research|counsel|attorney|lawyer",
    re.I
)


def parse_job_cards(html: str) -> list[dict]:
    """Parse job cards from AI Startup Jobs HTML."""
    jobs = []
    # Implementation depends on actual page structure
    # Look for job card containers
    # Extract: company, title, location, URL, description (if available)
    
    # Example pattern (adapt to actual site):
    # job_cards = re.findall(r'class="job-card"[^>]*>(.*?)</div>', html, re.S)
    # for card in job_cards:
    #     company = extract_from_card(card, 'company')
    #     title = extract_from_card(card, 'title')
    #     location = extract_from_card(card, 'location')
    #     url = extract_from_card(card, 'url')
    #     jobs.append({'company': company, 'title': title, 'location': location, 'url': url})
    
    return jobs


def run() -> dict:
    leads = []
    queried = 0
    failures = []
    
    for url in AI_STARTUP_URLS:
        r = client().get(url)
        queried += 1
        if not r.ok:
            failures.append(f"{url}: {r.describe()}")
            continue
        
        # Parse job listings
        jobs = parse_job_cards(r.text)
        
        for job in jobs:
            title = job.get('title', '')
            company = job.get('company', '')
            location = job.get('location', '')
            url = job.get('url', '')
            
            # Check relevance
            if LEGAL_AI_KEYWORDS.search(title + " " + job.get('description', '')):
                if keep_location(location):
                    leads.append(Lead(
                        source="aistartupjobs",
                        url=url,
                        company=company,
                        title=title,
                        location=location,
                        note="AI Startup Jobs - Legal/AI roles"
                    ))
    
    written = add_leads(leads)
    record_channel("discover:aistartupjobs", queried=queried, candidates=len(leads),
                   failures=failures, notes=f"Found {len(leads)} legal/AI roles from {queried} URLs")
    return {"urls_checked": queried, "leads": written, "failures": failures}
```

**Update pipeline.py:**
```python
# Line 12: Update CHANNELS list
CHANNELS = ["public_sector", "official_apis", "hn", "commoncrawl", "websearch", "wayback", "aistartupjobs"]
```

**Verification:**
```bash
# Test syntax
python3 -m py_compile radar/discover/aistartupjobs.py

# Test import
python3 -c "from radar.discover import aistartupjobs; print('Import OK')"

# Test channel registration
python3 -c "from radar.pipeline import CHANNELS; print('aistartupjobs' in CHANNELS)"
```

### Day 4-5: Legal Tech Boards Channel

**File:** `radar/discover/legaltech.py` (NEW)

**Action:** Create legal tech job boards scraper

```python
"""Legal Tech and Legal Operations job boards.

Covers: legaloperationsjobboard.com, goinhouse.com, legal.io, and similar.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from ..textutil import html_to_text
from .common import keep_location

LEGAL_TECH_BOARDS = {
    "legaloperationsjobboard.com": {
        "url": "https://legaloperationsjobboard.com/job-board",
        "legal_only": True
    },
    "goinhouse.com": {
        "url": "https://www.goinhouse.com/jobs",
        "legal_only": True
    },
    "legal.io": {
        "url": "https://legal.io/jobs",
        "legal_only": True
    }
}


def scrape_board(board_name: str, config: dict) -> list[Lead]:
    """Scrape a single legal tech job board."""
    leads = []
    r = client().get(config['url'])
    
    if not r.ok:
        return leads
    
    # Parse job listings
    jobs = parse_jobs(r.text)
    
    for job in jobs:
        title = job.get('title', '')
        company = job.get('company', '')
        location = job.get('location', '')
        url = job.get('url', '')
        
        # All these boards are legal-focused, minimal filtering needed
        if keep_location(location):
            leads.append(Lead(
                source=f"legaltech:{board_name}",
                url=url,
                company=company,
                title=title,
                location=location,
                note=f"{board_name} - Legal tech roles"
            ))
    
    return leads


def parse_jobs(html: str) -> list[dict]:
    """Parse job listings from HTML (implementation depends on site structure)."""
    jobs = []
    # Implement based on actual site structure
    # Look for job containers and extract details
    return jobs


def run() -> dict:
    leads = []
    failures = []
    queried = 0
    
    with ThreadPoolExecutor(3) as executor:
        futures = {board: executor.submit(scrape_board, board, config) 
                  for board, config in LEGAL_TECH_BOARDS.items()}
        
        for board, future in futures.items():
            try:
                leads.extend(future.result())
                queried += 1
            except Exception as e:
                failures.append(f"{board}: {type(e).__name__}: {e}")
    
    written = add_leads(leads)
    record_channel("discover:legaltech", queried=queried, candidates=len(leads),
                   failures=failures, notes=f"Scraped {len(LEGAL_TECH_BOARDS)} boards, found {len(leads)} leads")
    return {"boards_scraped": len(LEGAL_TECH_BOARDS), "leads": written, "failures": failures}
```

**Update pipeline.py:**
```python
# Line 12: Update CHANNELS list
CHANNELS = ["public_sector", "official_apis", "hn", "commoncrawl", "websearch", "wayback", "aistartupjobs", "legaltech"]
```

**Verification:**
```bash
python3 -m py_compile radar/discover/legaltech.py
python3 -c "from radar.discover import legaltech; print('Import OK')"
```

---

## Phase 3: Community & Alumni (Week 3)

### Day 6-7: Reddit r/legaltech Monitoring

**File:** `radar/discover/reddit_legaltech.py` (NEW)

**Action:** Create Reddit subreddit monitor

```python
"""Reddit r/legaltech subreddit monitoring for job postings.

Uses Reddit JSON API (no auth required for public subreddits).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from .common import keep_location

SUBREDDIT = "legaltech"
REDIT_URL = f"https://www.reddit.com/r/{SUBREDDIT}/new.json"

JOB_TITLES = re.compile(
    r"hiring|job|position|opening|role|career|employment|recruiting|"
    r"we're hiring|join us|work with us",
    re.I
)


def is_job_post(title: str, text: str) -> bool:
    """Check if a Reddit post is a job posting."""
    if JOB_TITLES.search(title):
        return True
    # Check for job-related flair
    return bool(re.search(r"\[hiring\]|\[job\]|\[career\]", text, re.I))


def extract_job_info(post: dict) -> Lead | None:
    """Extract job information from a Reddit post."""
    title = post.get('title', '')
    text = post.get('selftext', '')
    url = f"https://reddit.com{post.get('permalink', '')}"
    
    if not is_job_post(title, text):
        return None
    
    # Try to extract company from title or text
    company = extract_company(title + " " + text)
    location = extract_location(title + " " + text)
    
    if not keep_location(location) and "remote" not in text.lower():
        return None
    
    return Lead(
        source="reddit:legaltech",
        url=url,
        company=company,
        title=title,
        location=location or "Remote" if "remote" in text.lower() else "",
        note=f"r/legaltech - {text[:200]}"
    )


def extract_company(text: str) -> str:
    """Try to extract company name from text."""
    # Look for patterns like "at [Company]" or "[Company] is hiring"
    patterns = [
        r"at\s+([A-Z][a-zA-Z\s]+)",
        r"([A-Z][a-zA-Z\s]+)\s+is hiring",
        r"([A-Z][a-zA-Z\s]+)\s+is looking",
        r"\[([A-Z][a-zA-Z\s]+)\]",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).strip()
    
    return ""


def extract_location(text: str) -> str:
    """Try to extract location from text."""
    patterns = [
        r"\b(remote|anywhere|wfh)\b",
        r"\b(new york|nyc|philadelphia|philly|boston|dc|washington\s+dc)\b",
        r"\b([A-Z][a-z]+,\s*[A-Z]{2})\b",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            loc = match.group(0)
            if loc.lower() in ['remote', 'anywhere', 'wfh']:
                return "Remote"
            return loc
    
    return ""


def run() -> dict:
    leads = []
    queried = 0
    failures = []
    
    # Get new posts from last 7 days
    params = {
        "limit": 100,
        "t": "week"
    }
    
    r = client().get(REDIT_URL, params=params)
    queried += 1
    
    if not r.ok:
        failures.append(f"Reddit API: {r.describe()}")
        return {"error": "API failure", "leads": 0, "failures": failures}
    
    try:
        data = r.json()
        posts = data.get('data', {}).get('children', [])
        
        for post in posts:
            post_data = post.get('data', {})
            lead = extract_job_info(post_data)
            if lead:
                leads.append(lead)
    except json.JSONDecodeError as e:
        failures.append(f"JSON parse error: {e}")
    
    written = add_leads(leads)
    record_channel("discover:reddit_legaltech", queried=queried, candidates=len(leads),
                   failures=failures, notes=f"Scanned {len(posts)} posts, found {len(leads)} job postings")
    return {"posts_scanned": len(posts), "leads": written, "failures": failures}
```

**Update pipeline.py:**
```python
# Line 12: Update CHANNELS list
CHANNELS = ["public_sector", "official_apis", "hn", "commoncrawl", "websearch", "wayback", "aistartupjobs", "legaltech", "reddit_legaltech"]
```

**Verification:**
```bash
python3 -m py_compile radar/discover/reddit_legaltech.py
python3 -c "from radar.discover import reddit_legaltech; print('Import OK')"

# Test Reddit API access
python3 -c "from radar.http import client; r = client().get('https://www.reddit.com/r/legaltech/new.json', params={'limit': 1}); print(r.ok)"
```

### Day 7-8: Penn Law Alumni Research

**Task:** Research Penn Law alumni job board access

**Actions:**

1. **Identify the platform:**
   ```bash
   # Check if Penn Law uses a known platform
   curl -I https://www.law.upenn.edu/career/alumni-jobs
   
   # Look for common career platform indicators
   # Symplicity, Handshake, 12Twenty, etc.
   ```

2. **Check robots.txt:**
   ```bash
   curl https://www.law.upenn.edu/robots.txt
   curl https://law-upenn-csm.symplicity.com/robots.txt  # If Symplicity
   ```

3. **Document findings:**
   - Platform used
   - Public vs authenticated access
   - API availability
   - Contact information

4. **Create alumni.py stub:**

**File:** `radar/discover/alumni.py` (NEW - STUB)

```python
"""Penn Law Alumni Job Board Integration.

Status: RESEARCH PHASE
Platform: TBD (likely Symplicity)
Access: TBD (requires coordination with Penn Law Career Services)
"""
from __future__ import annotations

import os
from typing import Optional
from .. import config
from ..http import client
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel

# Configuration - to be populated after research
PENN_LAW_ALUMNI_URL = os.getenv("PENN_LAW_ALUMNI_URL") or "https://www.law.upenn.edu/career/alumni-jobs"
PENN_LAW_API_KEY = config.env("PENN_LAW_API_KEY")
PENN_LAW_USERNAME = config.env("PENN_LAW_USERNAME")
PENN_LAW_PASSWORD = config.env("PENN_LAW_PASSWORD")

# Research findings to be documented here
PLATFORM_DETECTED = None  # Will be: "symplicity", "handshake", "custom", etc.
API_AVAILABLE = False
AUTH_REQUIRED = True


def has_alumni_access() -> bool:
    """Check if we have credentials for Penn Law alumni board."""
    return bool(PENN_LAW_API_KEY or (PENN_LAW_USERNAME and PENN_LAW_PASSWORD))


def detect_platform() -> str:
    """Try to detect which platform Penn Law uses."""
    # Check for common patterns
    if "symplicity" in PENN_LAW_ALUMNI_URL:
        return "symplicity"
    if "handshake" in PENN_LAW_ALUMNI_URL:
        return "handshake"
    
    # Try to fetch and check HTML
    try:
        r = client().get(PENN_LAW_ALUMNI_URL)
        if r.ok:
            html = r.text.lower()
            if "symplicity" in html:
                return "symplicity"
            if "handshake" in html:
                return "handshake"
            if "12twenty" in html:
                return "12twenty"
    except:
        pass
    
    return "unknown"


def run() -> dict:
    """Placeholder - will be implemented after platform detection."""
    global PLATFORM_DETECTED
    
    if PLATFORM_DETECTED is None:
        PLATFORM_DETECTED = detect_platform()
    
    leads = []
    
    if not has_alumni_access():
        # Try public page
        r = client().get(PENN_LAW_ALUMNI_URL)
        if r.ok:
            # Attempt to parse public listings
            leads = parse_public_page(r.text)
    else:
        # Authenticated access - to be implemented
        pass
    
    written = add_leads(leads)
    
    access_note = "authenticated" if has_alumni_access() else "public page only"
    platform_note = f"platform: {PLATFORM_DETECTED}" if PLATFORM_DETECTED else "platform: unknown"
    
    record_channel("discover:alumni_pennlaw", queried=1, candidates=len(leads),
                   notes=f"Penn Law alumni board ({access_note}, {platform_note})")
    
    return {
        "board": "penn_law_alumni",
        "platform": PLATFORM_DETECTED,
        "access_level": access_note,
        "leads": written,
        "recommendation": "Contact Penn Law Career Services at careers@law.upenn.edu to arrange access"
    }


def parse_public_page(html: str) -> list[Lead]:
    """Try to parse public job listings (if any exist)."""
    leads = []
    # Implementation depends on what's available publicly
    return leads
```

**Update pipeline.py:**
```python
# Line 12: Update CHANNELS list
CHANNELS = ["public_sector", "official_apis", "hn", "commoncrawl", "websearch", "wayback", "aistartupjobs", "legaltech", "reddit_legaltech", "alumni"]
```

**Action Items:**
- [ ] Research Penn Law's career platform
- [ ] Contact Penn Law Career Services
- [ ] Request API access or data feed
- [ ] Document platform details in `alumni.py`
- [ ] Implement parsing logic based on platform

---

## Phase 4: Integration & Testing (Week 4)

### Day 9: Integration Testing

**Test each new channel individually:**

```bash
# Test AI Startup Jobs
python -m radar discover aistartupjobs

# Test Legal Tech
python -m radar discover legaltech

# Test Reddit
python -m radar discover reddit_legaltech

# Test Alumni (research mode)
python -m radar discover alumni
```

**Check outputs:**
```bash
# Check leads generated
cat data/leads.jsonl | python3 -m json.tool | grep -A5 "aistartupjobs"

# Check run log
cat out/run_log.md | grep -A10 "aistartupjobs"
```

### Day 10: Full Pipeline Test

**Run complete refresh:**
```bash
# Full refresh with all new channels
python -m radar refresh

# Check results
cat out/open_positions_*.md
cat out/jobs.csv
```

**Verify new sources are contributing:**
```bash
# Count postings from new sources
grep -c "aistartupjobs\|legaltech\|reddit" out/jobs.csv

# Check scoring
grep "niche source" out/jobs.csv | head -5
```

### Day 11: Penn Law Outreach

**Draft email to Penn Law Career Services:**

```
Subject: Request for Job Posting Data Access - Penn Law Alumni Network

Dear Penn Law Career Services Team,

I am a Penn Law JD graduate (Class of 2022) currently building a job search 
tool to help identify relevant opportunities for legal professionals with 
my background in financial services and regulatory work.

I would like to request access to Penn Law's alumni job board data to 
enhance the comprehensiveness of my search. Specifically, I'm interested in:

1. API access to job postings (preferred)
2. Regular data exports
3. Or guidance on how to programmatically access public postings

My tool is read-only, respects robots.txt, and maintains a 1 request/second
rate limit. It would only access Penn Law's job board, not apply or contact
anyone on my behalf.

Could you advise on the best way to arrange this access? I'm happy to
provide more details about my project and its safeguards.

Thank you for your time and assistance.

Best regards,
Seth Rosenberg
Penn Law JD '22
sethnrosenberg@gmail.com
```

**Send to:** careers@law.upenn.edu

### Day 12: Documentation & Monitoring

**Update README.md:**
```markdown
## Additional Discovery Channels

### AI Startup Jobs
Monitors [aistartupjobs.com](https://aistartupjobs.com) for Legal-AI, 
AI governance, and policy roles.

### Legal Tech Boards
Scrapes specialized legal tech job boards including:
- legaloperationsjobboard.com
- goinhouse.com
- legal.io

### Reddit r/legaltech
Monitors the r/legaltech subreddit for job postings.

### Penn Law Alumni
Connects to Penn Law's alumni job board (access pending).
```

**Create monitoring dashboard:**
```bash
# Track new channel performance
echo "=== Channel Performance ===" >> out/channel_performance.md
echo "Date: $(date)" >> out/channel_performance.md
python3 -c "
import json
from pathlib import Path

# Load latest run log
run_log = Path('out/run_log.md')
if run_log.exists():
    content = run_log.read_text()
    # Extract channel stats
    # ... parsing logic ...
    print('Channel performance tracked')
"
```

---

## Phase 5: Optimization (Week 5+)

### Ongoing Improvements

1. **Tune search queries** based on results
2. **Adjust scoring weights** for niche sources
3. **Expand alumni network** to other schools
4. **Add more niche boards** as discovered
5. **Monitor and iterate** continuously

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Update `seeds/search_queries.csv` with 25+ new queries
- [ ] Enhance `radar/discover/commoncrawl.py` with more ATS patterns
- [ ] Add source-based scoring boosts to `radar/score.py`
- [ ] Test all Phase 1 changes

### Phase 2: Niche Job Boards
- [ ] Create `radar/discover/aistartupjobs.py`
- [ ] Create `radar/discover/legaltech.py`
- [ ] Update `radar/pipeline.py` to include new channels
- [ ] Test AI Startup Jobs channel
- [ ] Test Legal Tech channel

### Phase 3: Community & Alumni
- [ ] Create `radar/discover/reddit_legaltech.py`
- [ ] Create `radar/discover/alumni.py` (stub)
- [ ] Update `radar/pipeline.py` to include reddit and alumni
- [ ] Research Penn Law's platform
- [ ] Contact Penn Law Career Services
- [ ] Test Reddit channel
- [ ] Test Alumni channel (research mode)

### Phase 4: Integration & Testing
- [ ] Test all channels individually
- [ ] Run full pipeline test
- [ ] Verify new sources in outputs
- [ ] Check scoring for niche sources
- [ ] Monitor for errors

### Phase 5: Optimization
- [ ] Tune search queries
- [ ] Adjust scoring weights
- [ ] Update documentation
- [ ] Create monitoring dashboard
- [ ] Plan next iterations

---

## Success Criteria

### Phase 1 Complete
✅ 25+ new search queries added
✅ Common Crawl patterns enhanced
✅ Source-based scoring implemented
✅ All syntax tests pass

### Phase 2 Complete
✅ AI Startup Jobs channel functional
✅ Legal Tech channel functional
✅ New channels integrated into pipeline
✅ Each channel discovers 10+ leads/week

### Phase 3 Complete
✅ Reddit channel functional
✅ Alumni channel stub created
✅ Penn Law platform researched
✅ Outreach email sent
✅ Each channel discovers 5+ leads/week

### Phase 4 Complete
✅ Full pipeline runs without errors
✅ New sources contribute to outputs
✅ 30-50% increase in relevant postings
✅ All tests pass

### Phase 5 Complete
✅ Documentation updated
✅ Monitoring in place
✅ Continuous improvement plan documented
✅ 50%+ increase in relevant postings sustained

---

## Resources Needed

### Time Estimate
- Phase 1: 2 days
- Phase 2: 3 days
- Phase 3: 3 days
- Phase 4: 2 days
- Phase 5: Ongoing
- **Total: 10 days for full implementation**

### Skills Required
- Python web scraping
- API integration
- Regular expressions
- Testing and debugging
- Institutional coordination (for Penn Law access)

### External Dependencies
- Penn Law Career Services cooperation
- Access to alumni job board
- Reddit API (no auth needed for public data)
- AI Startup Jobs website structure
- Legal tech board website structures

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Website structure changes | High | Medium | Use robust selectors, handle errors gracefully |
| Rate limiting | Medium | Medium | Respect robots.txt, maintain 1 req/sec rate |
| Penn Law access denied | Medium | High | Start with public data, pursue multiple contact paths |
| New channels produce low-quality leads | Medium | Low | Implement relevance filtering, monitor closely |
| Integration breaks existing functionality | Low | High | Test thoroughly, use feature flags if needed |

---

## Next Steps

1. **Start with Phase 1** - Quick wins, immediate impact
2. **Proceed to Phase 2** - High-value niche boards
3. **Coordinate with Penn Law** - Strategic alumni access
4. **Monitor and iterate** - Continuous improvement

**Recommended start date:** Immediately
**Expected completion:** 2 weeks for core functionality
**Full implementation:** 4-6 weeks (including Penn Law coordination)

---

*Implementation Plan created by: Vibe Coder*
*Date: 2026-09-25*
*Repository: sr104696/Claudey*
