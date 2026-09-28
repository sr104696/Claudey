from radar.ats.base import build_posting

BODY = ("We are looking for a lawyer to research and interpret financial regulation and write memos for decisions. "
        "J.D. required. Litigation experience welcome; judicial clerkship a plus. Financial services background "
        "a plus. Subject matter: credit, payments and AI. 3-5 years of experience.")


def posting(company="Acme Payments", title="Regulatory Counsel", location="New York, NY", body=BODY, job_id="1",
            ats="greenhouse", board="acme", posted=None, source="board:greenhouse", **kw):
    return build_posting(ats=ats, board=board, job_id=job_id, company=company, title=title,
                         url=f"https://boards.greenhouse.io/{board}/jobs/{job_id}", description_text=body,
                         locations=[location], posted=posted, source=source, **kw)
