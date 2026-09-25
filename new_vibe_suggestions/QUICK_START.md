# Quick Start Guide: Expanding Job Radar Discovery

This guide provides immediate, actionable steps to expand your job radar's coverage within the next 1-2 weeks.

---

## WEEK 1: HIGH-IMPACT EXPANSIONS

### Day 1: Add High-Priority Job Boards (2-4 hours)

#### 1. Add eFinancialCareers Scraper
**Why**: eFinancialCareers is the #1 source for finance jobs with legal/compliance roles.

**Implementation**:
```bash
# Create new file
cp /workspace/github__sr104696__Claudey/new_vibe_suggestions/IMPLEMENTATION_CODE.md radar/discover/efinancialcareers.py
```

Then edit `radar/discover/efinancialcareers.py` with:
```python
"""eFinancialCareers job board scraping."""
from __future__ import annotations

import re

from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from ..textutil import html_to_text
from .common import keep_location

EFIN_URL = "https://www.efinancialcareers.com"


def run() -> dict:
    leads = []
    queried = 0
    failures = []
    
    # Search for legal/compliance roles in NYC
    search_params = {
        "q": "legal OR compliance OR counsel OR attorney OR regulatory OR risk",
        "l": "New York",
        "sort": "date"
    }
    
    r = client().get(f"{EFIN_URL}/jobs", params=search_params)
    queried += 1
    
    if r.ok:
        # Parse job cards - look for job listing elements
        job_cards = re.findall(r'<article[^>]*job[^>]*>(.*?)</article>', r.text, re.S)
        
        for card in job_cards:
            try:
                title_match = re.search(r'<h2[^>]*>(.*?)</h2>', card, re.S)
                company_match = re.search(r'<span[^>]*class=["\']?company[^"\']*["\']][^>]*>(.*?)</span>', card, re.S)
                location_match = re.search(r'<span[^>]*class=["\']?location[^"\']*["\']][^>]*>(.*?)</span>', card, re.S)
                url_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', card)
                
                if title_match and company_match and url_match:
                    title = html_to_text(title_match.group(1)).strip()
                    company = html_to_text(company_match.group(1)).strip()
                    location = html_to_text(location_match.group(1)).strip() if location_match else "New York"
                    url = url_match.group(1)
                    
                    # Check relevance
                    ok, why = relevance(title, card)
                    if ok and keep_location(location):
                        leads.append(Lead(
                            source="efinancialcareers",
                            url=url,
                            company=company,
                            title=title,
                            location=location,
                            note=why
                        ))
            except Exception as e:
                failures.append(f"Error parsing job card: {e}")
    else:
        failures.append(f"eFinancialCareers request failed: {r.describe()}")
    
    written = add_leads(leads)
    record_channel("discover:efinancialcareers", queried=queried, 
                   candidates=len(leads), failures=failures,
                   notes=f"Found {len(leads)} relevant postings")
    return {"leads": written, "failures": failures}
```

**Test**:
```bash
python -m radar discover efinancialcareers
```

#### 2. Add AngelList/Wellfound Scraper
**Why**: High concentration of startup jobs, many fintech and legal tech companies.

Create `radar/discover/angellist.py`:
```python
"""AngelList/Wellfound job board scraping."""
from __future__ import annotations

import re

from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from ..textutil import html_to_text
from .common import keep_location

WELLFOUND_URL = "https://wellfound.com"


def run() -> dict:
    leads = []
    queried = 0
    failures = []
    
    # Search for legal/compliance/fintech roles
    search_params = {
        "q": "legal OR compliance OR counsel OR attorney OR regulatory OR policy OR fintech OR payments",
        "location": "New York",
        "remote": "true"
    }
    
    r = client().get(f"{WELLFOUND_URL}/jobs", params=search_params)
    queried += 1
    
    if r.ok:
        # Parse job listings
        job_items = re.findall(r'<div[^>]*class=["\']?job[^"\']*["\']][^>]*>(.*?)</div>', r.text, re.S)
        
        for item in job_items:
            try:
                title_match = re.search(r'<h3[^>]*>(.*?)</h3>', item, re.S)
                company_match = re.search(r'<span[^>]*class=["\']?company[^"\']*["\']][^>]*>(.*?)</span>', item, re.S)
                location_match = re.search(r'<span[^>]*class=["\']?location[^"\']*["\']][^>]*>(.*?)</span>', item, re.S)
                url_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', item)
                
                if title_match and company_match and url_match:
                    title = html_to_text(title_match.group(1)).strip()
                    company = html_to_text(company_match.group(1)).strip()
                    location = html_to_text(location_match.group(1)).strip() if location_match else "Remote"
                    url = url_match.group(1)
                    
                    # Check relevance
                    ok, why = relevance(title, item)
                    if ok and (keep_location(location) or "Remote" in location):
                        leads.append(Lead(
                            source="angellist",
                            url=url,
                            company=company,
                            title=title,
                            location=location,
                            note=f"Startup; {why}"
                        ))
            except Exception as e:
                failures.append(f"Error parsing AngelList job: {e}")
    else:
        failures.append(f"AngelList request failed: {r.describe()}")
    
    written = add_leads(leads)
    record_channel("discover:angellist", queried=queried, 
                   candidates=len(leads), failures=failures,
                   notes=f"Found {len(leads)} startup jobs")
    return {"leads": written, "failures": failures}
```

**Test**:
```bash
python -m radar discover angellist
```

### Day 2: Add New ATS Adapters (3-5 hours)

#### 1. Add Jobvite Adapter
Copy from `new_vibe_suggestions/IMPLEMENTATION_CODE.md` to `radar/ats/jobvite.py`

**Register in `radar/ats/__init__.py`**:
```python
from .jobvite import Jobvite, pull as jobvite_pull
```

**Update ATS detection in `radar/ats/base.py`**:
Add `Jobvite` to the ATS list.

**Test**:
```bash
python -c "from radar.ats import Jobvite; print(Jobvite.detect('https://apply.jobvite.com/company/job/abc'))"
```

#### 2. Add iCIMS and Taleo Adapters
Similar to Jobvite adapter. Focus on iCIMS first as it's widely used.

### Day 3: Expand Common Crawl Coverage (2 hours)

Edit `radar/discover/commoncrawl.py`:

Add to PATTERNS:
```python
PATTERNS = {
    "greenhouse": ["job-boards.greenhouse.io/*", "boards.greenhouse.io/*"],
    "lever": ["jobs.lever.co/*"],
    "ashby": ["jobs.ashbyhq.com/*"],
    "workday": ["*.wd*.myworkdayjobs.com/*"],
    "jobvite": ["*.jobvite.com/*"],
    "icims": ["*.icims.com/*"],
}
```

Add to PULL:
```python
from ..ats import jobvite, icims
PULL = {"greenhouse": greenhouse.pull, "lever": lever.pull, "ashby": ashby.pull,
        "jobvite": jobvite.pull, "icims": icims.pull}
```

**Test**:
```bash
python -m radar discover commoncrawl
```

### Day 4: Add RSS Feed Monitoring (2 hours)

Create `radar/discover/rss_feeds.py`:
```python
"""RSS feed monitoring for job postings."""
from __future__ import annotations

import feedparser
import json
from pathlib import Path

from .. import config
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from .common import keep_location

RSS_FEEDS = {
    "builtin_nyc": "https://www.builtinnyc.com/feed/jobs",
    "we_work_remotely": "https://weworkremotely.com/jobs.rss",
    "remote_ok": "https://remoteok.com/rss",
    "stack_overflow": "https://stackoverflow.com/jobs/feed",
}

FEED_STATE = config.DATA / "rss_feed_state.json"


def run() -> dict:
    leads = []
    queried = 0
    failures = []
    new_entries = 0
    
    # Load previous state
    state = {}
    if FEED_STATE.exists():
        state = json.loads(FEED_STATE.read_text(encoding="utf-8"))
    
    for feed_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            queried += 1
            
            if feed.bozo:
                failures.append(f"{feed_name}: Parse error - {feed.bozo_exception}")
                continue
            
            prev_entries = state.get(feed_name, {})
            current_entries = {}
            
            for entry in feed.entries:
                entry_id = entry.get("id", entry.link)
                
                if entry_id in prev_entries:
                    continue
                
                new_entries += 1
                current_entries[entry_id] = True
                
                # Check if this is a job posting
                title = entry.get("title", "").lower()
                description = entry.get("description", "").lower()
                
                if ("job" in title or "hiring" in title or "career" in title or 
                    "position" in title or "role" in title or
                    "job" in description or "hiring" in description):
                    
                    company = entry.get("author", "") or ""
                    location = getattr(entry, 'location', "") or ""
                    
                    from ..keywords import relevance
                    ok, why = relevance(entry.title, entry.description or "")
                    
                    if ok and keep_location(location):
                        leads.append(Lead(
                            source=f"rss:{feed_name}",
                            url=entry.link,
                            company=company,
                            title=entry.title,
                            location=location,
                            note=f"RSS feed; {why}"
                        ))
            
            state[feed_name] = current_entries
            
        except Exception as e:
            failures.append(f"{feed_name}: {type(e).__name__}: {e}")
    
    # Save state
    FEED_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    
    written = add_leads(leads)
    record_channel("discover:rss", queried=queried, candidates=len(leads),
                   failures=failures, notes=f"Monitored {len(RSS_FEEDS)} feeds, {new_entries} new entries")
    
    return {"leads": written, "new_entries": new_entries, "failures": failures}
```

**Register in `radar/discover/__init__.py`**:
```python
from .rss_feeds import run as rss_run
```

**Add to pipeline**: In `radar/pipeline.py`, add `rss_run` to discovery channels.

**Test**:
```bash
python -m radar discover rss
```

### Day 5: Add Search Queries (1 hour)

Edit `seeds/search_queries.csv` and add the high-priority queries from `SEARCH_QUERIES.md`:

```csv
source,query,location,notes
websearch,"legal counsel OR attorney OR compliance OR regulatory site:efinancialcareers.com",New York,eFinancialCareers
websearch,"legal OR compliance OR fintech" site:wellfound.com,New York,AngelList
websearch,"legal OR compliance OR regulatory" site:ycombinator.com/jobs,New York,Y Combinator
websearch,"in-house counsel OR corporate counsel" site:acc.com,New York,ACC Jobs
websearch,"legal OR compliance" site:majorlindsey.com,New York,MLA Jobs
websearch,"legal OR compliance OR counsel" site:weworkremotely.com,Remote,We Work Remotely
```

These will be used by Claude's WebSearch tool during `/refresh-jobs`.

---

## WEEK 2: MEDIUM-PRIORITY EXPANSIONS

### Day 6: Add Y Combinator Jobs Scraper
Create `radar/discover/ycombinator.py`:
```python
"""Y Combinator Jobs scraping."""
from __future__ import annotations

import re

from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from ..textutil import html_to_text
from .common import keep_location

YC_URL = "https://www.ycombinator.com"


def run() -> dict:
    leads = []
    queried = 0
    failures = []
    
    r = client().get(f"{YC_URL}/jobs")
    queried += 1
    
    if r.ok:
        job_rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.S)
        
        for row in job_rows:
            try:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                if len(cells) >= 3:
                    company = html_to_text(cells[0]).strip()
                    role = html_to_text(cells[1]).strip()
                    location = html_to_text(cells[2]).strip()
                    
                    url_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', row)
                    url = url_match.group(1) if url_match else f"{YC_URL}/jobs"
                    
                    ok, why = relevance(role, row)
                    if ok and keep_location(location):
                        leads.append(Lead(
                            source="ycombinator",
                            url=url,
                            company=company,
                            title=role,
                            location=location,
                            note=f"YC company; {why}"
                        ))
            except Exception as e:
                failures.append(f"Error parsing YC job row: {e}")
    else:
        failures.append(f"YC Jobs request failed: {r.describe()}")
    
    written = add_leads(leads)
    record_channel("discover:ycombinator", queried=queried, 
                   candidates=len(leads), failures=failures,
                   notes=f"Found {len(leads)} YC company jobs")
    return {"leads": written, "failures": failures}
```

**Test**:
```bash
python -m radar discover ycombinator
```

### Day 7: Enhance WayBack Machine Monitoring
Edit `radar/discover/wayback.py`:

Add more employers to TARGETS list from `seeds/companies.csv`:
```python
# Load companies from seeds/companies.csv
import csv
from .. import config

COMPANIES_FILE = config.SEEDS / "companies.csv"

# Add function to load companies
def load_companies():
    companies = []
    if COMPANIES_FILE.exists():
        with open(COMPANIES_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = row.get('company', '')
                board = row.get('board', '')
                if company and board:
                    companies.append((company, board))
    return companies

# Then add these to TARGETS or create a separate monitoring list
```

### Day 8: Add ACC Job Board Scraper
Create `radar/discover/acc_jobs.py`:
```python
"""ACC (Association of Corporate Counsel) job board scraping."""
from __future__ import annotations

import re

from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from ..textutil import html_to_text
from .common import keep_location

ACC_URL = "https://www.acc.com"


def run() -> dict:
    leads = []
    queried = 0
    failures = []
    
    # Search for in-house counsel jobs
    r = client().get(f"{ACC_URL}/jobs", params={"q": "in-house OR corporate OR general"})
    queried += 1
    
    if r.ok:
        job_items = re.findall(r'<div[^>]*class=["\']?job[^"\']*["\']][^>]*>(.*?)</div>', r.text, re.S)
        
        for item in job_items:
            try:
                title_match = re.search(r'<h3[^>]*>(.*?)</h3>', item, re.S)
                company_match = re.search(r'<span[^>]*class=["\']?company[^"\']*["\']][^>]*>(.*?)</span>', item, re.S)
                location_match = re.search(r'<span[^>]*class=["\']?location[^"\']*["\']][^>]*>(.*?)</span>', item, re.S)
                url_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', item)
                
                if title_match and url_match:
                    title = html_to_text(title_match.group(1)).strip()
                    company = html_to_text(company_match.group(1)).strip() if company_match else ""
                    location = html_to_text(location_match.group(1)).strip() if location_match else ""
                    url = url_match.group(1)
                    
                    ok, why = relevance(title, item)
                    if ok and keep_location(location):
                        leads.append(Lead(
                            source="acc_jobs",
                            url=url,
                            company=company,
                            title=title,
                            location=location,
                            note=f"In-house counsel; {why}"
                        ))
            except Exception as e:
                failures.append(f"Error parsing ACC job: {e}")
    else:
        failures.append(f"ACC Jobs request failed: {r.describe()}")
    
    written = add_leads(leads)
    record_channel("discover:acc_jobs", queried=queried, 
                   candidates=len(leads), failures=failures,
                   notes=f"Found {len(leads)} in-house counsel jobs")
    return {"leads": written, "failures": failures}
```

### Day 9: Add We Work Remotely Scraper
Create `radar/discover/weworkremotely.py`:
```python
"""We Work Remotely job board scraping."""
from __future__ import annotations

import re

from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from ..textutil import html_to_text
from .common import keep_location

WWR_URL = "https://weworkremotely.com"


def run() -> dict:
    leads = []
    queried = 0
    failures = []
    
    # Search for legal/compliance/finance roles
    r = client().get(f"{WWR_URL}/remote-jobs", params={
        "q": "legal OR compliance OR counsel OR attorney OR finance OR fintech"
    })
    queried += 1
    
    if r.ok:
        job_cards = re.findall(r'<article[^>]*>(.*?)</article>', r.text, re.S)
        
        for card in job_cards:
            try:
                title_match = re.search(r'<h2[^>]*>(.*?)</h2>', card, re.S)
                company_match = re.search(r'<span[^>]*class=["\']?company[^"\']*["\']][^>]*>(.*?)</span>', card, re.S)
                url_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', card)
                
                if title_match and company_match and url_match:
                    title = html_to_text(title_match.group(1)).strip()
                    company = html_to_text(company_match.group(1)).strip()
                    url = url_match.group(1)
                    
                    # Location is remote for all WWR jobs
                    location = "Remote"
                    
                    ok, why = relevance(title, card)
                    if ok:
                        leads.append(Lead(
                            source="weworkremotely",
                            url=url,
                            company=company,
                            title=title,
                            location=location,
                            note=f"Remote; {why}"
                        ))
            except Exception as e:
                failures.append(f"Error parsing WWR job: {e}")
    else:
        failures.append(f"We Work Remotely request failed: {r.describe()}")
    
    written = add_leads(leads)
    record_channel("discover:weworkremotely", queried=queried, 
                   candidates=len(leads), failures=failures,
                   notes=f"Found {len(leads)} remote jobs")
    return {"leads": written, "failures": failures}
```

### Day 10: Test & Validate All New Sources

Run full pipeline to test all new sources:
```bash
python -m radar refresh
```

Check outputs:
1. `out/run_log.md` - Look for errors from new sources
2. `out/open_positions_<date>.md` - Verify new relevant postings
3. `data/leads.jsonl` - Check new leads are being captured

Fix any issues and retry.

---

## EXPECTED RESULTS

### After Week 1
- **New Sources**: eFinancialCareers, AngelList, Jobvite, iCIMS, RSS feeds
- **New Leads**: 50-100+ new relevant postings per run
- **Coverage**: 30-50% increase in relevant job discovery

### After Week 2
- **New Sources**: Y Combinator, ACC, We Work Remotely, Taleo
- **New Leads**: 100-200+ new relevant postings per run
- **Coverage**: 50-100% increase in relevant job discovery

### Key Metrics to Track
1. Number of new leads per source
2. Number of relevant postings per source
3. Number of duplicates (should be < 10%)
4. Processing time (should not exceed current baseline by > 20%)
5. Error rates (should be < 5%)

---

## TROUBLESHOOTING

### Common Issues

1. **403 Forbidden Errors**
   - Check if site has robots.txt restrictions
   - Add to blocked list if persistent
   - Try using Common Crawl data instead

2. **429 Too Many Requests**
   - Increase delay for that domain
   - Implement adaptive rate limiting
   - Check if API key is available

3. **No Results Found**
   - Verify URL patterns are correct
   - Check HTML structure hasn't changed
   - Test with browser to confirm jobs exist

4. **Parsing Errors**
   - Update regex patterns to match current HTML
   - Add error handling for missing fields
   - Log sample HTML for debugging

5. **Slow Performance**
   - Check for synchronous requests that could be parallel
   - Add caching for repeated requests
   - Optimize regex patterns

### Debugging Commands

```bash
# Test individual source
python -m radar discover efinancialcareers --verbose

# Check run log for specific source
grep efinancialcareers out/run_log.md

# Test URL directly
curl -A "JobRadarBot (contact: sethnrosenberg@gmail.com)" https://www.efinancialcareers.com/jobs

# Check robots.txt
curl https://www.efinancialcareers.com/robots.txt

# Test with browser
open https://www.efinancialcareers.com/jobs
```

---

## MAINTENANCE TIPS

1. **Daily**: Check run log for errors
2. **Weekly**: Review new postings for relevance
3. **Monthly**: Update seed list and search queries
4. **Quarterly**: Review and update all scrapers
5. **As needed**: Fix broken sources promptly

---

## NEXT STEPS

After completing Weeks 1-2:

1. **Monitor effectiveness** of new sources for 1-2 weeks
2. **Add more sources** from the medium-priority list
3. **Implement incremental crawling** to reduce request volume
4. **Add caching** to improve performance
5. **Enhance data enrichment** with company and location data
6. **Implement alerts** for high-priority new postings

---

## RESOURCES

- **Full Strategy**: See `EXPANSION_STRATEGY.md` for comprehensive expansion ideas
- **Search Queries**: See `SEARCH_QUERIES.md` for additional search query suggestions
- **Implementation Code**: See `IMPLEMENTATION_CODE.md` for more adapter implementations
- **Current Code**: Review existing adapters in `radar/ats/` and `radar/discover/`
- **Documentation**: See `README.md` and `CLAUDE.md` for project details

---

## SUCCESS CRITERIA

✅ **Week 1 Complete**: 5+ new sources implemented and working
✅ **Week 2 Complete**: 10+ new sources implemented and working
✅ **Relevance Maintained**: > 80% of new postings are relevant
✅ **Performance Maintained**: Pipeline runs in < 10 minutes
✅ **Reliability Maintained**: < 5% error rate across all sources

---

**Note**: Always respect robots.txt, rate limits, and website terms of service. If a site blocks your requests, stop immediately and use alternative methods (Common Crawl, Wayback Machine, social media monitoring).
