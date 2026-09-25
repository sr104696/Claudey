# Job Radar Expansion Strategy

## Overview
This document provides comprehensive strategies to expand job radar coverage across orthogonal, adjacent, and tangential industries, role types, and sources while respecting rate limits and CORS restrictions.

---

## 1. INDUSTRY EXPANSION STRATEGIES

### 1.1 Financial Services Beyond Traditional
**Credit & Risk Adjacent:**
- Credit rating agencies (S&P, Moody's, Fitch)
- Payment processors (Adyen, Square, Paystand, Dwolla, Finix)
- Alternative lending (Kiva, Funding Circle, Fundbox, Bluevine)
- InsurTech (Lemonade, Hippo, Next Insurance, Embroker)
- PropTech (Compass, Redfin, Zillow, Matterport)

**Investment & Asset Management:**
- Alternative investment platforms (Moonfare, iCapital, CAIS)
- Crypto infrastructure (Chainalysis, TRM Labs, Elliptic)
- ESG investing (Arabesque, Sustainalytics, Truvalue Labs)
- Family offices and MFOs

### 1.2 Legal Tech & AI Adjacent
**Legal AI Platforms:**
- Casetext, ROSS Intelligence, Luminance, Judicata
- Contract lifecycle management (Ironclad, LinkSquares, Lawgeex)
- eDiscovery (Relativity, Everlaw, Logikcull, Disco)
- Legal analytics (Lex Machina, Bloomberg Law)

**AI Governance:**
- Conduit, HyperComply, RegScale
- AI policy research at OpenAI, Anthropic, Cohere

### 1.3 Regulatory & Compliance Adjacent
**Expanded Financial Regulation:**
- All 12 Federal Reserve Banks
- State regulatory bodies (CA DFPI, TX Banking, IL DFPR)
- International regulators (UK FCA, Singapore MAS, HK SFC)

**Industry-Specific Regulators:**
- Healthcare (CMS, state insurance commissioners)
- Energy (FERC, state PUCs)
- Telecom (FCC)
- Transportation (DOT)

### 1.4 Professional Services
**Big 4 Legal Arms:** Deloitte Legal, PwC Legal, EY Law, KPMG Law
**ALSPs:** UnitedLex, Axiom, Elevate, QuisLex
**Legal Ops Tech:** SimpleLegal, LegalTrack, BusyLamp, Apperio

### 1.5 Public Sector & Non-Profit
**Think Tanks:** Brookings, Urban Institute, Pew, NBER, Mercatus Center
**Advocacy:** Americans for Financial Reform, Better Markets, CDT
**International Orgs:** FSB, BIS, IMF, World Bank

### 1.6 Technology Sector
**AI Research:** OpenAI policy/legal, Anthropic, AI21 Labs
**Privacy Tech:** OneTrust, TrustArc, WireWheel, BigID
**Cloud Compliance:** AWS Legal, Google Cloud Trust & Safety

---

## 2. ROLE TYPE EXPANSION

### 2.1 Legal & Compliance Variants
- Specialized counsel: Payments Counsel, Crypto Counsel, AI Counsel
- Compliance: AML, BSA, Sanctions, Privacy, Financial Crime
- Regulatory affairs: Government Affairs, Public Policy

### 2.2 Finance-Adjacent for JDs
- Credit analysis and underwriting
- Investment research and due diligence
- Treasury and capital markets
- Risk management variants

### 2.3 Technology & Data Roles
- Legal tech implementation (Solutions Architect, Product Manager)
- Legal analytics and data analysis
- Regulatory reporting

### 2.4 Consulting & Advisory
- Financial services consulting
- Legal transformation consulting
- Strategy and change management

---

## 3. JOB BOARD & AGGREGATOR EXPANSION

### 3.1 Niche Job Boards
**Legal:** LawJobs.com, LawCrossing, InHouseJobs, Corporate Counsel Jobs
**Compliance:** ComplianceJobs.com, ACAMS Career Center, SCC Career Center
**Finance:** eFinancialCareers (HIGH PRIORITY), Rigzone, RiskJobs
**Tech:** AngelList/Wellfound (HIGH PRIORITY), Y Combinator Jobs

### 3.2 Aggregators
- Remote: We Work Remotely (HIGH PRIORITY), Remote.co, Remote OK
- Startups: Startup Jobs, VentureLoop
- Diversity: DiversityJobs, Jopwell, PowerToFly

### 3.3 Professional Associations
- ACC (HIGH PRIORITY), ABA Career Center
- ACAMS, SCCE, GARP, PRMIA
- FinTech Association

### 3.4 Recruitment Agencies
- Major Lindsey & Africa (HIGH PRIORITY)
- BarkerGilmore, Special Counsel
- Selby Jennings, Options Group

### 3.5 University Networks
- All top law school career portals
- Penn Law, Harvard, Yale, Columbia, NYU
- Alumni networks and Symplicity

### 3.6 International
- UK: TotalJobs, JobSite, Reed
- Europe: StepStone, Monster Germany
- Canada: Workopolis, Job Bank
- Australia: Seek, Jora

---

## 4. SCRAPING & CRAWLING STRATEGIES

### 4.1 New ATS Adapters Needed
- Jobvite (URL: *.jobvite.com/*)
- iCIMS (URL: *.icims.com/*)
- Taleo (URL: *.taleo.net/*)
- Kenexa, BrassRing, SilkRoad
- BambooHR, Workable, Recruitee (enhance existing)

### 4.2 Enhanced Discovery
**Common Crawl:** Add Workday, Jobvite, iCIMS, Taleo patterns
**Wayback Machine:** Monitor all companies from seeds/companies.csv
**RSS Feeds:** Monitor company career pages and job boards
**Sitemap.xml:** Track new job URLs from sitemaps

### 4.3 Social Media Monitoring
- Twitter/X: Monitor job posting hashtags and company accounts
- Reddit: Monitor r/legalcareers, r/fintech, r/compliance
- LinkedIn: Monitor company career pages (without scraping)

### 4.4 Search Engine Integration
- Google Custom Search JSON API
- Bing Search API
- DuckDuckGo API
- Programmable Search Engine for job sites

---

## 5. API INTEGRATION

### 5.1 Free APIs
- The Muse (already implemented)
- AngelList API
- Authentic Jobs API
- Stack Overflow Jobs API
- GitHub Jobs (if returns)

### 5.2 Paid APIs (Consider)
- SerpAPI ($50/month for 5000 searches)
- ScraperAPI ($29/month for 100K requests)
- Apify ($49/month for 100 actor runs)
- Clearbit ($0.10 per company lookup)

---

## 6. IMPLEMENTATION ROADMAP

### Phase 1: Quick Wins (1-2 weeks)
1. Add eFinancialCareers scraping
2. Add AngelList/Wellfound scraping
3. Add Y Combinator Jobs scraping
4. Add ACC job board scraping
5. Add We Work Remotely scraping
6. Add Jobvite, iCIMS, Taleo adapters
7. Expand Common Crawl patterns
8. Enhance WayBack Machine monitoring
9. Add RSS feed monitoring
10. Add sitemap.xml monitoring

### Phase 2: Medium-Term (2-4 weeks)
1. Add BuiltIn city pages scraping
2. Add ComplianceJobs.com scraping
3. Add Major Lindsey & Africa job board
4. Implement incremental crawling
5. Add adaptive scheduling
6. Enhance caching
7. Add data validation
8. Implement data enrichment
9. Add Twitter/X monitoring

### Phase 3: Long-Term (1-3 months)
1. Add LinkedIn monitoring (without scraping)
2. Add Reddit monitoring
3. Add email monitoring
4. Implement posting classification (ML)
5. Add similarity search
6. Add distributed crawling
7. Implement monitoring and alerting
8. Add dashboard and visualization
9. Implement REST API
10. Add mobile and desktop apps

---

## 7. RATE LIMIT & CORS STRATEGIES

### Current Implementation
- 1 request/second/host
- Respects Crawl-delay in robots.txt
- Cross-process request tracking

### Enhancements Needed
- Adaptive rate limiting based on response patterns
- Per-domain rate limits (some allow faster crawling)
- Exponential backoff with jitter for retries
- User-Agent rotation
- CORS proxy server for problematic sites

### Blocked Sites Workarounds
- Cloudflare: Use Common Crawl, Wayback Machine, social media
- ag.ny.gov: Use statejobs.ny.gov mirror
- robots.txt: Use Common Crawl data or official APIs

---

## 8. DATA STORAGE ENHANCEMENTS

### Enhanced Schema Suggestions
- Companies table with industry, size, ATS info
- Postings table with role type, seniority, pay info
- Discovery sources table with rate limits
- Alerts table for user notifications
- User feedback table for continuous improvement

---

## 9. TESTING & QUALITY

### Test Coverage Needed
- Unit tests for all ATS adapters
- Integration tests for pipeline
- Performance tests for concurrent operations
- Data quality validation tests

---

## 10. SPECIFIC CODE IMPLEMENTATIONS

See separate files in this directory for:
- New ATS adapters (jobvite.py, icims.py, taleo.py)
- New discovery channels (efinancialcareers.py, angellist.py, ycombinator.py)
- Enhanced discovery (rss_feeds.py, sitemap.py)
- Rate limiting enhancements
- Database migrations

---

## 11. SEARCH QUERY EXPANSION

Add these search queries to seeds/search_queries.csv:

```csv
source,query,location,notes
websearch,"legal counsel OR attorney OR compliance OR regulatory site:efinancialcareers.com",New York,eFinancialCareers
websearch,"legal OR compliance OR fintech" site:wellfound.com,New York,AngelList
websearch,"legal OR compliance OR regulatory" site:ycombinator.com/jobs,New York,Y Combinator
websearch,"in-house counsel OR corporate counsel" site:acc.com,New York,ACC Jobs
websearch,"legal OR compliance OR fintech" site:weworkremotely.com,Remote,We Work Remotely
websearch,"legal counsel OR attorney OR compliance OR regulatory site:greenhouse.io",New York,Greenhouse
websearch,"legal counsel OR attorney OR compliance OR regulatory site:lever.co",New York,Lever
websearch,"compliance" site:compliancejobs.com,New York,ComplianceJobs
websearch,"legal OR compliance OR counsel" site:majorlindsey.com,New York,MLA Jobs
```

---

## 12. RECOMMENDATIONS

### Immediate Actions
1. Implement eFinancialCareers and AngelList scrapers (highest ROI)
2. Add Jobvite, iCIMS, Taleo ATS adapters
3. Expand Common Crawl to include more ATS platforms
4. Add RSS feed monitoring for major job boards

### Continuous Improvement
1. Regularly update seed list with new companies
2. Monitor discovery effectiveness and adjust sources
3. Review and update scoring rubric quarterly
4. Optimize performance and add caching

### Principles to Maintain
- Always respect robots.txt and rate limits
- Prioritize relevance to candidate profile
- Ensure data quality through verification
- Maintain comprehensive logging
- Iterate continuously based on results

---

## Conclusion

This document outlines comprehensive strategies to expand the Job Radar's coverage while maintaining compliance with website policies. The recommendations are organized by priority, with immediate actions that can significantly increase relevant job discovery within 1-2 weeks of implementation.

For detailed implementation code, see the other files in this directory.