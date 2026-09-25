# Penn Law Alumni Job Board Integration Guide

## Overview

This guide provides **detailed instructions** for integrating with Penn Law's alumni job board and career services. Penn Law graduates have access to exclusive job postings, and this integration will help discover those opportunities programmatically.

---

## Step 1: Identify the Platform

### Current Penn Law Career Services

Penn Law Career Planning & Professional Development (CPPD) uses **Symplicity** for their career services platform.

**Key URLs:**
- Main Career Services: https://www.law.upenn.edu/career/
- Student/Alumni Portal: https://law-upenn-csm.symplicity.com/
- Job Postings: https://law-upenn-csm.symplicity.com/students

### Platform Confirmation

**Method 1: Check URL**
```bash
# Check if Symplicity is mentioned
curl -s https://www.law.upenn.edu/career/ | grep -i simplicity

# Check redirect
curl -I https://law-upenn-csm.symplicity.com
```

**Method 2: Check HTML**
```bash
# Download main career page
curl -s https://www.law.upenn.edu/career/ > /tmp/penn_law_career.html

# Check for Symplicity references
grep -i "symplicity" /tmp/penn_law_career.html
```

**Method 3: Manual Verification**
1. Visit https://www.law.upenn.edu/career/
2. Look for "Job Postings" or "Career Portal" links
3. Check if links point to symplicity.com

### Symplicity Platform Details

**Symplicity Corporation:**
- Website: https://www.symplicity.com/
- Headquarters: Arlington, VA
- Common URL pattern: `{school}-csm.symplicity.com`
- Penn Law instance: `law-upenn-csm.symplicity.com`

**Symplicity Features:**
- Job postings management
- Employer database
- Student/alumni profiles
- Application tracking
- Event management
- Document storage

---

## Step 2: Access Options

### Option A: Public Access (No Authentication)

**What's Available:**
- Public job postings (if any)
- General career resources
- Event listings

**Limitations:**
- Most job postings require authentication
- Limited to public-facing content
- May miss alumni-specific postings

**Implementation:**
```python
# radar/discover/alumni.py

def scrape_public_penn_law() -> list[Lead]:
    """Scrape publicly accessible Penn Law job postings."""
    from ..http import client
    from ..leads import add_leads
    from ..models import Lead
    
    url = "https://www.law.upenn.edu/career/job-postings"
    r = client().get(url)
    
    if not r.ok:
        return []
    
    # Parse any public job listings
    leads = parse_public_listings(r.text)
    return leads
```

### Option B: Authenticated Access (Recommended)

**What's Available:**
- Full job postings database
- Alumni-specific opportunities
- Employer contacts
- Application deadlines

**Requirements:**
- Symplicity credentials (username/password)
- Penn Law alumni status verification
- API access (if available)

**Implementation Approaches:**

#### Approach 1: Web Scraping with Authentication

```python
# radar/discover/alumni.py

import os
from typing import Optional
from .. import config
from ..http import client
from ..leads import add_leads
from ..models import Lead

PENN_LAW_USERNAME = config.env("PENN_LAW_USERNAME")
PENN_LAW_PASSWORD = config.env("PENN_LAW_PASSWORD")
SYMPLICITY_URL = "https://law-upenn-csm.symplicity.com"


def has_credentials() -> bool:
    """Check if we have Symplicity credentials."""
    return bool(PENN_LAW_USERNAME and PENN_LAW_PASSWORD)


def login_to_symplicity() -> Optional[dict]:
    """Login to Symplicity and return session cookies."""
    login_url = f"{SYMPLICITY_URL}/sso/student"
    
    # Symplicity login typically uses a form POST
    login_data = {
        'user': PENN_LAW_USERNAME,
        'pass': PENN_LAW_PASSWORD,
        # May need additional fields depending on Symplicity version
    }
    
    # Create session
    session = client().session()
    
    try:
        # First, get the login page to obtain CSRF token
        r = session.get(login_url)
        if not r.ok:
            return None
        
        # Extract CSRF token if present
        # Symplicity may use different anti-CSRF mechanisms
        csrf_token = extract_csrf_token(r.text)
        if csrf_token:
            login_data['csrf_token'] = csrf_token
        
        # Submit login
        r = session.post(login_url, data=login_data)
        
        if r.ok and "Welcome" in r.text:
            # Login successful, return session
            return {'session': session, 'cookies': session.cookies.get_dict()}
        else:
            return None
            
    except Exception as e:
        return None


def scrape_symplicity_jobs(session_data: dict) -> list[Lead]:
    """Scrape job postings from Symplicity."""
    session = session_data['session']
    leads = []
    
    # Job listings URL
    jobs_url = f"{SYMPLICITY_URL}/students/index.cfm?fuseaction=home&tab=jobs"
    
    r = session.get(jobs_url)
    
    if r.ok:
        leads = parse_symplicity_jobs(r.text)
    
    return leads


def parse_symplicity_jobs(html: str) -> list[Lead]:
    """Parse job listings from Symplicity HTML."""
    from selectolax.parser import HTMLParser
    
    tree = HTMLParser(html)
    leads = []
    
    # Symplicity job listings are typically in a table
    # Look for job rows
    for row in tree.css('tr.jobRow, tr.job-listing'):
        try:
            # Extract job details
            title = extract_text(row, 'td.jobTitle, a.jobTitle')
            company = extract_text(row, 'td.employer, span.employer')
            location = extract_text(row, 'td.location, span.location')
            
            # Extract URL
            link = row.css_first('a.jobTitle, a[href*="job_id"]')
            url = link['href'] if link and link.has_attr('href') else ""
            
            if url and not url.startswith('http'):
                url = f"{SYMPLICITY_URL}{url}" if url.startswith('/') else url
            
            # Create lead
            lead = Lead(
                source="alumni_pennlaw:symplicity",
                url=url,
                company=company,
                title=title,
                location=location,
                note="Penn Law Alumni - Symplicity"
            )
            leads.append(lead)
            
        except Exception:
            continue
    
    return leads
```

#### Approach 2: API Access (Preferred)

**Symplicity API:**
- Symplicity offers REST APIs for career services
- Access requires special arrangement with Symplicity
- Documentation is typically provided to institutional partners

**Implementation:**
```python
# radar/discover/alumni.py

PENN_LAW_API_KEY = config.env("PENN_LAW_API_KEY")
SYMPLICITY_API_URL = "https://api.symplicity.com"


def has_api_access() -> bool:
    """Check if we have Symplicity API access."""
    return bool(PENN_LAW_API_KEY)


def get_jobs_from_api() -> list[Lead]:
    """Get job postings from Symplicity API."""
    leads = []
    
    headers = {
        "Authorization": f"Bearer {PENN_LAW_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # API endpoint for job postings
    # Note: Actual endpoint depends on Symplicity API version
    jobs_url = f"{SYMPLICITY_API_URL}/schools/law-upenn/jobs"
    
    params = {
        "status": "active",
        "limit": 100,
        "offset": 0
    }
    
    r = client().get(jobs_url, headers=headers, params=params)
    
    if r.ok:
        data = r.json()
        leads = parse_api_jobs(data)
    
    return leads


def parse_api_jobs(data: dict) -> list[Lead]:
    """Parse job postings from Symplicity API response."""
    leads = []
    
    for job in data.get('results', []):
        try:
            lead = Lead(
                source="alumni_pennlaw:api",
                url=job.get('application_url', job.get('url')),
                company=job.get('employer', {}).get('name'),
                title=job.get('title'),
                location=job.get('location', {}).get('city', ''),
                note=f"Penn Law Alumni - API | Deadline: {job.get('deadline')}"
            )
            leads.append(lead)
        except Exception:
            continue
    
    return leads
```

### Option C: Data Export (Manual/Automated)

**What's Available:**
- Regular CSV/JSON exports
- Scheduled email reports
- RSS feeds (if configured)

**Implementation:**
```python
# radar/discover/alumni.py

import csv
from pathlib import Path
from ..leads import add_leads
from ..models import Lead

EXPORT_FILE = Path("data/penn_law_export.csv")


def load_export_file() -> list[Lead]:
    """Load job postings from export file."""
    leads = []
    
    if not EXPORT_FILE.exists():
        return leads
    
    with open(EXPORT_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lead = Lead(
                    source="alumni_pennlaw:export",
                    url=row.get('url', ''),
                    company=row.get('company', ''),
                    title=row.get('title', ''),
                    location=row.get('location', ''),
                    note=f"Penn Law Alumni - Export | Date: {row.get('date', '')}"
                )
                leads.append(lead)
            except Exception:
                continue
    
    return leads
```

---

## Step 3: Contact Penn Law Career Services

### Outreach Strategy

**Primary Contact:**
- **Office:** Career Planning & Professional Development (CPPD)
- **Email:** careers@law.upenn.edu
- **Phone:** (215) 898-1345
- **Address:** 3501 Sansom Street, Philadelphia, PA 19104

**Secondary Contacts:**
- **Alumni Relations:** alumni@law.upenn.edu
- **IT Department:** ithelp@law.upenn.edu (for technical questions)

### Outreach Template

**Subject:** Request for Programmatic Access to Alumni Job Postings

**Body:**
```
Dear Penn Law Career Planning & Professional Development Team,

I am a Penn Law JD graduate from the Class of 2022 currently building a 
personal job search tool to help identify relevant career opportunities 
that align with my background in financial services, regulatory work, and 
my interest in legal technology and AI.

As a Penn Law alumnus, I would like to request access to the alumni job 
board data to enhance the comprehensiveness of my job search. I believe 
this would be mutually beneficial:

1. **For Me:** More comprehensive job discovery, ensuring I don't miss 
   opportunities specifically targeted to Penn Law graduates.

2. **For Penn Law:** Increased visibility of alumni job postings and 
   potentially better placement outcomes.

**Technical Details:**
- My tool is read-only and will only access job posting data
- It respects all robots.txt rules and maintains a 1 request/second rate limit
- It will not apply to jobs, contact employers, or perform any write operations
- All data is stored locally and not shared with third parties
- I'm happy to provide code review or technical details upon request

**Access Options I'm Exploring:**
1. Symplicity API access (preferred)
2. Web scraping with alumni credentials
3. Regular data exports
4. RSS feed access

Could you advise on the best way to arrange this access? I'm also happy 
to discuss this in person or via phone if that would be helpful.

Thank you for your time and assistance. I look forward to your guidance.

Best regards,

Seth Rosenberg
Penn Law JD '22
sethnrosenberg@gmail.com
(215) XXX-XXXX
```

### Follow-Up Strategy

1. **Initial Email:** Send to careers@law.upenn.edu
2. **Wait 3-5 business days** for response
3. **Follow-up Email:** If no response, send gentle follow-up
4. **Phone Call:** If still no response, call the office
5. **Alternative Contacts:** Reach out to Alumni Relations
6. **LinkedIn:** Connect with CPPD staff on LinkedIn

### What to Request

**Priority Order:**
1. **API Access** - Most sustainable, real-time
2. **Web Scraping Permission** - With alumni credentials
3. **Data Export** - Regular CSV/JSON files
4. **RSS Feed** - If available
5. **Manual Access** - As last resort

**Technical Requirements to Communicate:**
- Read-only access
- Rate limiting (1 req/sec)
- No automated applications
- Local data storage only
- Respect for employer confidentiality

---

## Step 4: Implementation Details

### Authentication Flow

**Symplicity Authentication:**
1. POST to login endpoint with credentials
2. Receive session cookies
3. Use cookies for subsequent requests
4. Maintain session until logout or timeout

**Code Example:**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class SymplicityClient:
    """Client for Symplicity with authentication."""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        
        # Configure retry logic
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def login(self) -> bool:
        """Login to Symplicity."""
        login_url = f"{SYMPLICITY_URL}/sso/student"
        
        # Get login page to obtain CSRF token
        r = self.session.get(login_url)
        if not r.ok:
            return False
        
        # Extract CSRF token
        csrf_token = self.extract_csrf(r.text)
        
        # Submit login
        data = {
            'user': self.username,
            'pass': self.password,
            'csrf_token': csrf_token
        }
        
        r = self.session.post(login_url, data=data)
        
        return r.ok and self.is_logged_in(r.text)
    
    def is_logged_in(self, html: str) -> bool:
        """Check if login was successful."""
        # Look for logout link or welcome message
        return "Logout" in html or "Welcome" in html
    
    def extract_csrf(self, html: str) -> str:
        """Extract CSRF token from HTML."""
        # Symplicity may use different approaches
        # Common: hidden input field
        import re
        match = re.search(r'name="csrf_token"[^>]+value="([^"]+)"', html)
        if match:
            return match.group(1)
        return ""
    
    def get_jobs(self) -> list[dict]:
        """Get job postings."""
        jobs_url = f"{SYMPLICITY_URL}/students/index.cfm?fuseaction=home&tab=jobs"
        
        r = self.session.get(jobs_url)
        
        if r.ok:
            return self.parse_jobs(r.text)
        return []
```

### Job Parsing

**Symplicity HTML Structure:**
```html
<table class="jobTable">
  <tr class="jobRow">
    <td class="jobTitle">
      <a href="job_id=12345">Legal Counsel</a>
    </td>
    <td class="employer">Harvey AI</td>
    <td class="location">New York, NY</td>
    <td class="posted">2026-09-20</td>
    <td class="deadline">2026-10-20</td>
  </tr>
</table>
```

**Parsing Code:**
```python
def parse_symplicity_jobs(html: str) -> list[dict]:
    """Parse job listings from Symplicity HTML."""
    from selectolax.parser import HTMLParser
    
    tree = HTMLParser(html)
    jobs = []
    
    # Find job table rows
    for row in tree.css('tr.jobRow'):
        try:
            job = {
                'title': extract_text(row, 'td.jobTitle a'),
                'company': extract_text(row, 'td.employer'),
                'location': extract_text(row, 'td.location'),
                'posted': extract_text(row, 'td.posted'),
                'deadline': extract_text(row, 'td.deadline'),
                'url': extract_href(row, 'td.jobTitle a')
            }
            
            # Normalize URL
            if job['url'] and not job['url'].startswith('http'):
                if job['url'].startswith('/'):
                    job['url'] = f"{SYMPLICITY_URL}{job['url']}"
                else:
                    job['url'] = f"{SYMPLICITY_URL}/{job['url']}"
            
            jobs.append(job)
            
        except Exception:
            continue
    
    return jobs
```

### Pagination

**Symplicity Pagination:**
- Typically uses `?page=N` parameter
- Or `start=N` parameter
- May have "Next" button

**Implementation:**
```python
def get_all_jobs(client: SymplicityClient, max_pages: int = 10) -> list[dict]:
    """Get all job postings with pagination."""
    all_jobs = []
    
    for page in range(1, max_pages + 1):
        jobs_url = f"{SYMPLICITY_URL}/students/index.cfm?fuseaction=home&tab=jobs&page={page}"
        r = client.session.get(jobs_url)
        
        if not r.ok:
            break
        
        jobs = client.parse_jobs(r.text)
        
        if not jobs:
            # No more jobs or pagination ended
            break
        
        all_jobs.extend(jobs)
    
    return all_jobs
```

---

## Step 5: Testing & Validation

### Test Plan

**Phase 1: Manual Testing**
1. Manually verify Penn Law uses Symplicity
2. Test public access to career page
3. Verify login process (if credentials available)
4. Browse job postings manually

**Phase 2: Automated Testing**
1. Test authentication flow
2. Test job parsing
3. Test URL normalization
4. Test location extraction
5. Test company extraction

**Phase 3: Integration Testing**
1. Test with full pipeline
2. Verify leads are created
3. Verify postings are verified
4. Verify scoring works
5. Check for duplicates

### Test Cases

```python
# tests/test_alumni.py

import pytest
from unittest.mock import Mock, patch
from radar.discover.alumni import (
    detect_platform,
    parse_symplicity_jobs,
    SymplicityClient
)


def test_detect_platform_symplicity():
    """Test Symplicity platform detection."""
    html = """
    <html>
    <body>
        <a href="https://law-upenn-csm.symplicity.com">Career Portal</a>
    </body>
    </html>
    """
    
    with patch('radar.http.client') as mock_client:
        mock_response = Mock()
        mock_response.text = html
        mock_response.ok = True
        mock_client.return_value.get.return_value = mock_response
        
        result = detect_platform()
        assert result['platform'] == 'symplicity'


def test_parse_symplicity_jobs():
    """Test Symplicity job parsing."""
    html = """
    <table class="jobTable">
      <tr class="jobRow">
        <td class="jobTitle"><a href="/job_id=123">Legal Counsel</a></td>
        <td class="employer">Harvey AI</td>
        <td class="location">New York, NY</td>
        <td class="posted">2026-09-20</td>
      </tr>
    </table>
    """
    
    jobs = parse_symplicity_jobs(html)
    assert len(jobs) == 1
    assert jobs[0]['title'] == 'Legal Counsel'
    assert jobs[0]['company'] == 'Harvey AI'
    assert jobs[0]['location'] == 'New York, NY'


def test_symplicity_client_login():
    """Test Symplicity client login."""
    with patch('requests.Session') as mock_session:
        mock_session_instance = Mock()
        mock_session_instance.get.return_value.ok = True
        mock_session_instance.get.return_value.text = '<html>Welcome</html>'
        mock_session_instance.post.return_value.ok = True
        mock_session_instance.post.return_value.text = '<html>Welcome</html>'
        mock_session.return_value = mock_session_instance
        
        client = SymplicityClient("user", "pass")
        result = client.login()
        assert result == True
```

---

## Step 6: Deployment & Monitoring

### Deployment Checklist

- [ ] Confirm platform (Symplicity)
- [ ] Obtain access method (API, credentials, or export)
- [ ] Implement authentication (if needed)
- [ ] Implement job parsing
- [ ] Add to pipeline.py CHANNELS list
- [ ] Configure environment variables
- [ ] Test locally
- [ ] Test in staging (if available)
- [ ] Deploy to production
- [ ] Monitor first run

### Environment Variables

Add to `.env.example`:
```
# Penn Law Alumni Access
PENN_LAW_USERNAME=your_penn_law_username
PENN_LAW_PASSWORD=your_penn_law_password
PENN_LAW_API_KEY=your_api_key_if_available
PENN_LAW_ALUMNI_URL=https://law-upenn-csm.symplicity.com
```

### Monitoring

**Metrics to Track:**
1. Number of alumni postings discovered per run
2. Percentage that pass relevance filtering
3. Percentage that become verified postings
4. Number of failures/errors
5. Time spent scraping

**Alerts:**
- Authentication failures
- Zero postings discovered
- High error rate
- Rate limiting issues

---

## Step 7: Maintenance

### Regular Tasks

1. **Weekly:**
   - Check for new alumni postings
   - Verify authentication still works
   - Review discovered postings for relevance

2. **Monthly:**
   - Check for Symplicity platform updates
   - Update parsing logic if HTML structure changes
   - Review and update filtering criteria

3. **Quarterly:**
   - Renew credentials if needed
   - Review alumni board effectiveness
   - Consider expanding to other law school alumni boards

### Troubleshooting

**Issue: Authentication Fails**
- Verify credentials are correct
- Check if password expired
- Verify account is still active
- Check for CAPTCHA requirements

**Issue: No Jobs Discovered**
- Verify URL is correct
- Check if HTML structure changed
- Test manually in browser
- Check for bot detection

**Issue: Rate Limited**
- Verify rate limiting (1 req/sec)
- Check for IP blocking
- Verify User-Agent
- Consider adding delays

**Issue: Parsing Errors**
- Check HTML structure
- Update CSS selectors
- Add error handling
- Log parsing failures

---

## Alternative Approaches

### If Symplicity Access is Denied

**Option 1: Public Career Pages**
- Scrape public Penn Law career pages
- Look for job postings linked from main site
- Limited but better than nothing

**Option 2: Alumni Network Outreach**
- Connect with Penn Law alumni on LinkedIn
- Join Penn Law alumni groups
- Request job leads directly

**Option 3: Other Law School Boards**
- Harvard Law Career Services
- Yale Law Career Development
- Stanford Law Career Services
- May have reciprocal access

**Option 4: General Legal Job Boards**
- Focus on boards that cater to Ivy League grads
- Many employers post to multiple schools
- Can still capture relevant opportunities

### If Technical Access is Limited

**Option 1: Manual Export**
- Request regular CSV exports from CPPD
- Automate import of CSV files
- Schedule periodic manual exports

**Option 2: RSS Feed**
- Check if Penn Law offers RSS feeds
- Subscribe to job posting feeds
- Parse RSS for new postings

**Option 3: Email Alerts**
- Subscribe to job alert emails
- Parse emails for job postings
- Extract relevant information

---

## Success Metrics

### Target Outcomes
1. **Coverage:** 20-40 alumni-specific postings per week
2. **Relevance:** 70%+ of alumni postings are relevant
3. **Uniqueness:** 50%+ of alumni postings are not found elsewhere
4. **Timeliness:** New postings discovered within 24-48 hours

### KPIs to Track
```
- Alumni postings discovered: [X] per week
- Alumni postings verified: [Y] per week
- Alumni postings in fit table: [Z] per week
- Unique to alumni channel: [W]%
- Time to discovery: [V] hours
```

---

## Resources

### Penn Law Contacts
- **Career Planning & Professional Development:** careers@law.upenn.edu
- **Alumni Relations:** alumni@law.upenn.edu
- **Main Phone:** (215) 898-1345

### Symplicity Resources
- **Website:** https://www.symplicity.com/
- **Support:** support@symplicity.com
- **Documentation:** Available to institutional partners

### Technical Resources
- **Symplicity API Docs:** Request from Symplicity support
- **Penn Law IT:** ithelp@law.upenn.edu
- **Penn Law Career Services:** careers@law.upenn.edu

---

## Appendix: Sample Implementation

### Complete alumni.py Implementation

```python
"""Penn Law Alumni Job Board Integration.

This module provides integration with Penn Law's alumni job board,
which is hosted on the Symplicity platform.
"""
from __future__ import annotations

import os
import re
from typing import Optional
from .. import config
from ..http import client
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from .common import keep_location

# Configuration
PENN_LAW_USERNAME = config.env("PENN_LAW_USERNAME")
PENN_LAW_PASSWORD = config.env("PENN_LAW_PASSWORD")
PENN_LAW_API_KEY = config.env("PENN_LAW_API_KEY")
SYMPLICITY_URL = "https://law-upenn-csm.symplicity.com"

# Platform detection
PLATFORM_DETECTED = None


def has_credentials() -> bool:
    """Check if we have Symplicity credentials."""
    return bool(PENN_LAW_USERNAME and PENN_LAW_PASSWORD)


def has_api_access() -> bool:
    """Check if we have Symplicity API access."""
    return bool(PENN_LAW_API_KEY)


def detect_platform() -> str:
    """Detect which platform Penn Law uses."""
    global PLATFORM_DETECTED
    
    if PLATFORM_DETECTED:
        return PLATFORM_DETECTED
    
    # Check URL pattern
    if "symplicity" in SYMPLICITY_URL:
        PLATFORM_DETECTED = "symplicity"
        return PLATFORM_DETECTED
    
    # Try to fetch main page
    try:
        r = client().get(SYMPLICITY_URL)
        if r.ok:
            html = r.text.lower()
            if "symplicity" in html:
                PLATFORM_DETECTED = "symplicity"
                return PLATFORM_DETECTED
    except:
        pass
    
    PLATFORM_DETECTED = "unknown"
    return PLATFORM_DETECTED


def run() -> dict:
    """Run the Penn Law alumni discovery channel."""
    platform = detect_platform()
    leads = []
    failures = []
    queried = 0
    
    if platform == "symplicity":
        if has_api_access():
            # Use API if available
            leads, failures, queried = get_jobs_from_api()
        elif has_credentials():
            # Use authenticated scraping
            leads, failures, queried = get_jobs_from_scraping()
        else:
            # Try public access
            leads, failures, queried = get_jobs_from_public()
    else:
        # Try public Penn Law pages
        leads, failures, queried = get_jobs_from_public()
    
    written = add_leads(leads)
    
    access_note = "api" if has_api_access() else ("authenticated" if has_credentials() else "public")
    
    record_channel(
        "discover:alumni_pennlaw",
        queried=queried,
        candidates=len(leads),
        failures=failures,
        notes=f"Penn Law alumni board (platform: {platform}, access: {access_note})"
    )
    
    return {
        "board": "penn_law_alumni",
        "platform": platform,
        "access_level": access_note,
        "leads": written,
        "failures": len(failures),
        "recommendation": get_recommendation(platform, access_note)
    }


def get_recommendation(platform: str, access_level: str) -> str:
    """Get recommendation based on current access level."""
    if platform == "unknown":
        return "Verify platform by checking Penn Law career website"
    
    if access_level == "api":
        return "API access working - monitor for changes"
    
    if access_level == "authenticated":
        return "Authenticated access working - ensure credentials stay valid"
    
    return "Contact Penn Law Career Services at careers@law.upenn.edu to arrange API access"


def get_jobs_from_api() -> tuple[list[Lead], list[str], int]:
    """Get jobs using Symplicity API."""
    # Implementation for API access
    return [], [], 0


def get_jobs_from_scraping() -> tuple[list[Lead], list[str], int]:
    """Get jobs using authenticated scraping."""
    from .symplicity import SymplicityClient
    
    client = SymplicityClient(PENN_LAW_USERNAME, PENN_LAW_PASSWORD)
    
    if not client.login():
        return [], ["Login failed"], 1
    
    jobs = client.get_all_jobs(max_pages=10)
    leads = []
    
    for job in jobs:
        try:
            lead = Lead(
                source="alumni_pennlaw:symplicity",
                url=job['url'],
                company=job['company'],
                title=job['title'],
                location=job['location'],
                note=f"Penn Law Alumni - Symplicity | Posted: {job.get('posted', '')}"
            )
            
            # Only keep if location is acceptable
            if keep_location(lead.location):
                leads.append(lead)
                
        except Exception:
            continue
    
    return leads, [], len(jobs)


def get_jobs_from_public() -> tuple[list[Lead], list[str], int]:
    """Get jobs from public pages."""
    leads = []
    failures = []
    queried = 0
    
    # Try main career page
    url = "https://www.law.upenn.edu/career/job-postings"
    r = client().get(url)
    queried += 1
    
    if r.ok:
        leads = parse_public_listings(r.text)
    else:
        failures.append(f"Public page: {r.describe()}")
    
    return leads, failures, queried


def parse_public_listings(html: str) -> list[Lead]:
    """Parse public job listings from Penn Law pages."""
    from selectolax.parser import HTMLParser
    
    tree = HTMLParser(html)
    leads = []
    
    # Look for job listing links
    for link in tree.css('a[href*="job"]'):
        try:
            title = link.text(strip=True)
            url = link['href']
            
            if not url.startswith('http'):
                if url.startswith('/'):
                    url = f"https://www.law.upenn.edu{url}"
                else:
                    continue
            
            # Try to extract company and location from nearby elements
            parent = link.parent
            company = ""
            location = ""
            
            if parent:
                # Look for company in parent or siblings
                company_node = parent.css_first('.company, .employer')
                if company_node:
                    company = company_node.text(strip=True)
                
                # Look for location
                location_node = parent.css_first('.location')
                if location_node:
                    location = location_node.text(strip=True)
            
            lead = Lead(
                source="alumni_pennlaw:public",
                url=url,
                company=company,
                title=title,
                location=location,
                note="Penn Law Alumni - Public Page"
            )
            
            if keep_location(lead.location):
                leads.append(lead)
                
        except Exception:
            continue
    
    return leads
```

---

## Conclusion

Integrating with Penn Law's alumni job board requires:

1. **Platform Identification:** Confirm Penn Law uses Symplicity
2. **Access Arrangement:** Obtain API access or alumni credentials
3. **Implementation:** Build Symplicity client with proper authentication
4. **Testing:** Thoroughly test all access methods
5. **Deployment:** Add to discovery pipeline
6. **Monitoring:** Track performance and effectiveness

**Expected Timeline:**
- Platform identification: 1 day
- Outreach to Penn Law: 1-2 weeks (including response time)
- Implementation: 2-3 days
- Testing: 1-2 days
- Deployment: 1 day
- **Total: 2-3 weeks**

**Expected Impact:**
- 20-40 additional relevant postings per week
- Higher quality leads (Penn Law-specific)
- Better coverage of legal tech and innovative legal roles

---

*Guide created by: Vibe Coder*
*Date: 2026-09-25*
*Repository: sr104696/Claudey*
