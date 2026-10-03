# Red-team the method

TASK: I analysed one person's 7-month job search (about 4,400 applications). Find the five most likely ways my conclusions are wrong, and for each give a cheap test I could run on the data to check. Be specific and critical; do not reassure.

METHOD AND CLAIMS
- Data: one row per application, built from email confirmations and rejections, then corrected by re-reading Gmail. 4,427 rows; 1,865 rejections (74 only probable); 2,345 no response (53%); 35 verified interview processes since mid-July.
- Claim 1: counsel and regulatory roles produced 19 of the 30 interview processes that came from applications, about 2.2 per 100 applications, against 0.4 per 100 for all other roles (the intervals do not overlap).
- Claim 2: day of week and hour of application do not affect the chance of getting any reply (p = 0.45 and 0.76 across 1,588 dated applications through applicant-tracking systems, submitted before Sep 1). "Reply" means a rejection or an interview process.
- Claim 3: weekend applications got fewer replies (13 of 51, 25%) than weekday ones (677 of 1,537, 44%), p = 0.009.
- Claim 4: 64% of rejections arrive within 7 days; 90% within 28 days; the median is 5 days.
- Claim 5: recruiter-sourced processes stayed alive more often (3 of 4) than application-sourced ones (12 of 30). The sample is tiny.
- Known weaknesses: interview emails are sparse; roles were classified by a rule-based tagger; applications were sent in bursts (more than 150 in some days); the person changed targeting over time; some rejections are missing from the data.
Questions: (1) Which confounders could create Claims 1 and 3? (2) Is "any reply" a valid stand-in for interview likelihood? (3) What is wrong with comparing interview yield across role families when application effort differs? (4) What would you check first, and how?
