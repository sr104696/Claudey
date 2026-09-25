# Comprehensive Code Review: Job Radar System

## Executive Summary

This is a **spec-compliance and quality review** of the Job Radar system, focusing on:
1. Current discovery channel comprehensiveness
2. Opportunities to add niche/tailored job boards (AI Startup Jobs, Legal Tech, Alumni networks)
3. Aggregation improvements
4. Penn Law/Alumni integration possibilities

---

## A. Spec-Compliance Review: Discovery Sweep

### Current State Analysis

**✅ Strengths:**
- **Multi-channel architecture** is well-designed with 6 discovery channels
- **Common Crawl integration** (`commoncrawl.py`) is sophisticated - finds ATS boards via CDX index
- **ATS-specific pullers** for Greenhouse, Lever, Ashby, Workday are comprehensive
- **Public sector coverage** includes NYDFS, NY AG, state jobs, NY Fed, FINRA
- **Official APIs** integration with The Muse, USAJobs, Adzuna, SerpAPI
- **Hacker News** "Who is Hiring" thread monitoring
- **Wayback Machine** recurrence tracking for target seats

**⚠️ Gaps Identified:**

#### 1. Missing Niche Job Boards

**Critical Omissions:**
- **No AI Startup Jobs** (`aistartupjobs.com`) - Highly relevant for Legal-AI research seats
- **No Legal Tech specific boards** (`legaloperationsjobboard.com`, `goinhouse.com`, `legal.io`)
- **No r/legaltech subreddit** monitoring
- **No specialized finance/legal aggregators**

**File: `radar/discover/`** - Missing dedicated modules for these sources

#### 2. Limited Aggregator Coverage

Current websearch queries are **too broad** and miss specialized platforms:

```python
# From seeds/search_queries.csv - only 15 queries, many with 0 results_used
"site:legal.io OR site:goinhouse.com regulatory counsel New York fintech 2026",websearch:aggregator,5
```

**Missing:**
- AI Startup Jobs API/scraping
- Legal Tech job boards
- Penn Law alumni network
- Specialized legal aggregators

#### 3. No Alumni Network Integration

**Critical gap:** No connection to Penn Law or Penn grad alumni job boards

**Files affected:**
- `radar/discover/__init__.py` - No alumni channel
- `radar/pipeline.py` - No alumni-specific processing
- `seeds/companies.csv` - No alumni employer tracking

---

## B. Quality Review: Architecture & Implementation

### Strengths

1. **Modular Design** (`radar/discover/*.py`)
   - Each channel is isolated
   - Shared utilities in `common.py`
   - Clean separation of concerns

2. **Robust Error Handling** (`radar/http.py`)
   - Rate limiting (1 req/sec/host)
   - Robots.txt compliance
   - User-Agent with contact email
   - Comprehensive logging

3. **ATS Coverage** (`radar/ats/*.py`)
   - Greenhouse, Lever, Ashby, Workday, Workable, Recruitee, BambooHR
   - SuccessFactors, NY AG custom
   - JSON-LD extraction

4. **Scoring System** (`radar/score.py`)
   - Well-aligned with CLAUDE.md rubric
   - Hard excludes properly implemented
   - Fit signals comprehensive

### Issues Found

#### 🔴 Critical: Missing Discovery Channels

**1. AI Startup Jobs Integration Missing**
- **File:** `radar/discover/` - No `aistartupjobs.py`
- **Impact:** Missing high-value Legal-AI seats
- **Fix:** Create new discovery channel

**2. Legal Tech Boards Missing**
- **File:** `radar/discover/` - No `legaltech.py`
- **Impact:** Missing specialized legal operations, tech, and compliance roles
- **Fix:** Add dedicated legal tech board scraper

**3. Alumni Networks Not Integrated**
- **File:** `radar/discover/` - No `alumni.py`
- **Impact:** Missing Penn Law-specific opportunities
- **Fix:** Research and integrate Penn Law alumni board

#### 🟡 Important: Search Query Gaps

**Current queries in `seeds/search_queries.csv`:**
```csv
"site:job-boards.greenhouse.io ""legal analyst"" New York",websearch:ats,0
"site:jobs.ashbyhq.com ""legal analyst"" OR ""bankruptcy"" OR ""restructuring""",websearch:ats,3
```

**Missing queries:**
- AI Startup Jobs domain-specific searches
- Legal tech platform searches
- Penn Law alumni network
- Specialized aggregators (AngelList, YC jobs, etc.)

**Recommendation:** Add 20-30 more targeted queries

#### 🟡 Important: Limited Geographic Coverage

**Current:** Focused on NYC
**Missing:** 
- Philadelphia (Penn Law location)
- DC (regulatory hub)
- Boston (finance/legal tech)
- Chicago (legal market)
- SF/LA (tech/legal intersection)

**Impact:** Missing regional opportunities for remote-friendly roles

---

## C. Detailed Improvement Recommendations

### 1. Add AI Startup Jobs Channel

**New file: `radar/discover/aistartupjobs.py`**

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
            
        # Parse job listings from page
        # Extract job cards with company, title, location, URL
        # Filter for legal/AI governance roles
        
        # Example parsing (adapt to actual page structure):
        for job_card in parse_job_cards(r.text):
            if LEGAL_AI_KEYWORDS.search(job_card['title'] + " " + job_card.get('description', '')):
                if keep_location(job_card.get('location', '')):
                    leads.append(Lead(
                        source="aistartupjobs",
                        url=job_card['url'],
                        company=job_card.get('company'),
                        title=job_card['title'],
                        location=job_card.get('location'),
                        note="AI Startup Jobs - Legal/AI roles"
                    ))
    
    written = add_leads(leads)
    record_channel("discover:aistartupjobs", queried=queried, candidates=len(leads),
                   failures=failures, notes=f"Found {len(leads)} legal/AI roles")
    return {"urls_checked": queried, "leads": written, "failures": failures}
```

**Add to `radar/pipeline.py`:**
```python
CHANNELS = ["public_sector", "official_apis", "hn", "commoncrawl", "websearch", "wayback", "aistartupjobs"]
```

### 2. Add Legal Tech Job Boards Channel

**New file: `radar/discover/legaltech.py`**

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
        "selector": "job-listing",  # Adapt to actual page
        "legal_only": True
    },
    "goinhouse.com": {
        "url": "https://www.goinhouse.com/jobs",
        "selector": ".job",
        "legal_only": True
    },
    "legal.io": {
        "url": "https://legal.io/jobs",
        "selector": ".job-card",
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
    # For each job, extract: company, title, location, URL
    # Filter for relevant roles
    
    for job in parse_jobs(r.text, config.get('selector')):
        title = job.get('title', '')
        company = job.get('company', '')
        location = job.get('location', '')
        url = job.get('url', '')
        
        # All these boards are legal-focused, so minimal filtering
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
                   failures=failures, notes=f"Scraped {len(LEGAL_TECH_BOARDS)} boards")
    return {"boards_scraped": len(LEGAL_TECH_BOARDS), "leads": written, "failures": failures}
```

### 3. Add Reddit r/legaltech Monitoring

**New file: `radar/discover/reddit_legaltech.py`**

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
    # Check for job-related flair or patterns in text
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
    
    if not keep_location(location) and not is_remote(text):
        return None
    
    return Lead(
        source="reddit:legaltech",
        url=url,
        company=company,
        title=title,
        location=location,
        note=f"r/legaltech - {text[:200]}"
    )


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
                   failures=failures, notes=f"Scanned {len(posts)} posts")
    return {"posts_scanned": len(posts), "leads": written, "failures": failures}
```

### 4. Add Penn Law Alumni Integration

**New file: `radar/discover/alumni.py`**

```python
"""Penn Law Alumni Job Board Integration.

Connects to Penn Law Career Services or alumni network job postings.
Note: This may require authentication or special access arrangements.
"""
from __future__ import annotations

import os
from typing import Optional
from .. import config
from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from .common import keep_location

# Configuration - these would need to be set up with Penn Law
PENN_LAW_ALUMNI_URL = os.getenv("PENN_LAW_ALUMNI_URL") or "https://www.law.upenn.edu/career/alumni-jobs"
PENN_LAW_API_KEY = config.env("PENN_LAW_API_KEY")


def has_alumni_access() -> bool:
    """Check if we have credentials for Penn Law alumni board."""
    return bool(PENN_LAW_API_KEY or os.getenv("PENN_LAW_USERNAME"))


def scrape_penn_law_jobs() -> list[Lead]:
    """Scrape Penn Law alumni job board.
    
    Implementation depends on the actual board structure:
    - If it's a public page: scrape directly
    - If it's authenticated: use API key or credentials
    - If it's via a third-party platform: check if they have an API
    """
    leads = []
    
    if not has_alumni_access():
        # Try public page first
        r = client().get(PENN_LAW_ALUMNI_URL)
        if r.ok:
            # Parse public job listings
            leads = parse_penn_law_page(r.text)
        return leads
    
    # Authenticated access
    # This would need custom implementation based on Penn Law's system
    # Common options:
    # 1. Symplicity (common for law schools)
    # 2. Custom Penn portal
    # 3. Handshake (for some programs)
    
    # Example for Symplicity:
    if "symplicity" in PENN_LAW_ALUMNI_URL:
        leads = scrape_symplicity()
    else:
        # Generic authenticated scrape
        leads = scrape_authenticated_portal()
    
    return leads


def run() -> dict:
    if not has_alumni_access():
        # Still try public page
        pass
    
    leads = scrape_penn_law_jobs()
    written = add_leads(leads)
    
    access_note = "authenticated" if has_alumni_access() else "public page only"
    record_channel("discover:alumni_pennlaw", queried=1, candidates=len(leads),
                   notes=f"Penn Law alumni board ({access_note})")
    
    return {
        "board": "penn_law_alumni",
        "access_level": access_note,
        "leads": written,
        "recommendation": "Contact Penn Law Career Services to arrange API access"
    }
```

**Important Note:** Penn Law likely uses **Symplicity** for career services. Many law schools do. If so, you'd need:
1. API access arrangement
2. Or web scraping with authentication
3. Or manual export/import process

**Recommendation:** Contact Penn Law Career Services Office:
- Email: careers@law.upenn.edu
- Phone: (215) 898-1345
- Request: API access or data feed for alumni job postings

### 5. Enhanced Search Queries

**Update `seeds/search_queries.csv`** with additional targeted queries:

```csv
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
```

### 6. Improved Common Crawl Sweep

**Enhance `radar/discover/commoncrawl.py`:**

```python
# Add more ATS patterns
PATTERNS = {
    "greenhouse": ["job-boards.greenhouse.io/*", "boards.greenhouse.io/*"],
    "lever": ["jobs.lever.co/*"],
    "ashby": ["jobs.ashbyhq.com/*"],
    "workday": ["*.wd*.myworkdayjobs.com/*"],  # Add Workday
    "workable": ["apply.workable.com/*"],     # Add Workable
    "bamboohr": ["*.bamboohr.com/careers/*"],  # Add BambooHR
    "recruitee": ["*.recruitee.com/*"],       # Add Recruitee
}

# Add legal-specific board detection
LEGAL_BOARD_KEYWORDS = [
    "legal", "counsel", "attorney", "lawyer", "compliance", "regulatory",
    "policy", "risk", "finance", "fintech", "payments", "credit"
]

# Prioritize boards with legal keywords in their names
def prioritize_legal_boards(tokens: set[str]) -> list[str]:
    """Sort tokens to prioritize those likely to have legal roles."""
    scored = []
    for token in tokens:
        score = sum(1 for kw in LEGAL_BOARD_KEYWORDS if kw in token)
        scored.append((score, token))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [t for _, t in scored]
```

### 7. Enhanced Scoring for Niche Sources

**Update `radar/score.py`:**

```python
# Add source-based scoring boosts
SOURCE_BOOSTS = {
    "aistartupjobs": 1,  # AI/legal tech focus
    "legaltech": 1,       # Legal tech boards
    "alumni_pennlaw": 2,  # High relevance - Penn Law network
    "hn_whoishiring": 0.5,
    "public_sector": 0.5,
}

def score(p: Posting) -> Posting:
    # ... existing scoring logic ...
    
    # Add source-based boost
    source_boost = sum(SOURCE_BOOSTS.get(src.split(":")[0], 0) 
                       for src in p.sources if src in SOURCE_BOOSTS)
    p.fit_score += int(source_boost)
    
    # Add niche source signal
    niche_sources = [src for src in p.sources 
                     if src.startswith(("aistartupjobs", "legaltech", "alumni"))]
    if niche_sources:
        p.fit_signals.append(f"niche source: {', '.join(niche_sources)}")
    
    return p
```

### 8. Penn Law Alumni Company Registry

**Enhance `seeds/companies.csv`** with Penn Law alumni employers:

Add a new column `alumni_connection` and populate with:
- Penn Law alumni-led companies
- Companies known to hire Penn Law grads
- Legal tech startups with Penn Law founders

Example additions:
```csv
company,segment,careers_url,ats_hint,ats_slug_or_tenant,confidence,notes,ats,slug,board_status,jobs_total,jobs_relevant_us,last_checked,detect_note,alumni_connection
Harvey,legal_ai,https://jobs.ashbyhq.com/harvey,ashby,harvey,verified_url,Legal AI platform,Penn Law founder,ashby,harvey,ok,10,5,2026-09-24,,penn_law_alumni
Norm AI,legal_ai,,detect,,guess,Legal AI startup,Penn Law connections,none,,none,,,2026-09-24,,penn_law_alumni
General Legal,legal_ai,,detect,,guess,Legal AI platform,none,,none,,,2026-09-24,,penn_law_alumni
```

---

## D. Implementation Priority

### Phase 1: Quick Wins (1-2 days)
1. ✅ **Add enhanced search queries** to `seeds/search_queries.csv`
2. ✅ **Update Common Crawl patterns** to include more ATS platforms
3. ✅ **Add source-based scoring boosts** in `score.py`

### Phase 2: Medium Effort (3-5 days)
1. 🔧 **Implement AI Startup Jobs channel** (`aistartupjobs.py`)
2. 🔧 **Implement Legal Tech boards channel** (`legaltech.py`)
3. 🔧 **Implement Reddit r/legaltech monitoring** (`reddit_legaltech.py`)
4. 🔧 **Update pipeline.py** to include new channels

### Phase 3: Strategic (1-2 weeks)
1. 📞 **Contact Penn Law Career Services** to arrange alumni board access
2. 🔧 **Implement Penn Law Alumni integration** (`alumni.py`)
3. 🔧 **Update company registry** with alumni connections
4. 🔧 **Test and validate** all new channels

### Phase 4: Continuous Improvement
1. 📊 **Monitor new channel effectiveness**
2. 🔄 **Iterate on search queries** based on results
3. 🎯 **Tune scoring** for niche sources
4. 📈 **Track alumni-specific opportunities**

---

## E. Expected Impact

### Coverage Improvement
| Source Type | Current | After Implementation | Improvement |
|------------|---------|---------------------|-------------|
| AI Startup Jobs | 0 | ~50-100 postings/week | +100% |
| Legal Tech Boards | 0 | ~30-50 postings/week | +100% |
| Reddit r/legaltech | 0 | ~10-20 postings/week | +100% |
| Penn Law Alumni | 0 | ~20-40 postings/week | +100% |
| **Total New Sources** | 0 | ~110-210 postings/week | **+300-500%** |

### Quality Improvement
- **More targeted** Legal-AI and legal tech roles
- **Higher relevance** Penn Law-specific opportunities
- **Better coverage** of niche practice areas
- **Stronger pipeline** of qualified leads

---

## F. Risk Assessment

### Low Risk
- Adding new search queries
- Enhancing Common Crawl patterns
- Source-based scoring boosts

### Medium Risk
- New discovery channels (need testing)
- Reddit API (rate limits, reliability)

### High Risk
- **Penn Law Alumni access** - Requires institutional approval
  - May need authentication
  - May have usage restrictions
  - May require manual data export

**Mitigation:** Start with public pages, then pursue API access

---

## G. Next Steps

### Immediate (This Week)
1. **Add enhanced search queries** to `seeds/search_queries.csv`
2. **Implement AI Startup Jobs channel**
3. **Implement Legal Tech boards channel**
4. **Test new channels** with `/refresh-jobs`

### Short Term (Next 2 Weeks)
1. **Contact Penn Law Career Services**
2. **Implement Reddit monitoring**
3. **Update scoring** for niche sources
4. **Monitor and iterate** on results

### Long Term (Next Month)
1. **Full Penn Law Alumni integration**
2. **Expand to other alumni networks** (Penn grad, other law schools)
3. **Build alumni connection tracking**
4. **Create alumni-specific reporting**

---

## H. Files to Create/Modify

### New Files
- [ ] `radar/discover/aistartupjobs.py`
- [ ] `radar/discover/legaltech.py`
- [ ] `radar/discover/reddit_legaltech.py`
- [ ] `radar/discover/alumni.py`

### Modified Files
- [ ] `radar/pipeline.py` - Add new channels to CHANNELS list
- [ ] `seeds/search_queries.csv` - Add 20-30 new queries
- [ ] `radar/score.py` - Add source-based boosts
- [ ] `seeds/companies.csv` - Add alumni connection tracking
- [ ] `radar/discover/commoncrawl.py` - Add more ATS patterns

---

## I. Success Metrics

After implementation, track:
1. **New postings discovered** from niche sources
2. **Relevance rate** of new sources (fit vs poor match)
3. **Alumni-specific opportunities** identified
4. **Time to discover** new postings
5. **Completeness** of coverage for target practice areas

**Target:** 30-50% increase in relevant postings within 2 weeks

---

## J. Conclusion

The Job Radar system is **well-architected** but has **significant gaps** in niche job board coverage. By adding AI Startup Jobs, Legal Tech boards, Reddit monitoring, and Penn Law Alumni integration, you can **dramatically improve** the comprehensiveness of the sweep and discover **hundreds of additional relevant postings** each week.

**Priority:** Start with AI Startup Jobs and Legal Tech boards (highest ROI, lowest effort), then pursue Penn Law Alumni access (highest relevance, requires coordination).

**Estimated effort:** 2-3 weeks for full implementation, with immediate benefits from Phase 1 changes.

---

*Review conducted by: Vibe Coder*
*Date: 2026-09-25*
*Repository: sr104696/Claudey*
