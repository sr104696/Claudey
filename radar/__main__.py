"""CLI: python -m radar <command>

  verify-seeds              Phase 1: re-check seeds/current_list.md -> out/seed_verification_<date>.md
  boards [--company NAME]   Phase 2: detect ATS for every registry company, pull full boards
  discover CHANNEL          Phase 3: run one discovery channel (module radar/discover/CHANNEL.py)
  import-leads FILE         Append leads from a JSONL file (web-search results gathered by Claude)
  import-inbox              Turn saved alumni-board alert emails (data/inbox/) into leads
  refresh                   Phases 1-5 end to end
  decide ID DECISION        Record that you applied to / dismissed / ruled on a posting; no run presents it again
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify-seeds", help="Phase 1: re-verify the seed list")
    b = sub.add_parser("boards", help="Phase 2: detect ATS and pull full boards")
    b.add_argument("--company", action="append", help="limit to these registry companies (repeatable)")
    b.add_argument("--redetect", action="store_true", help="probe ATS again even when already detected")
    d = sub.add_parser("discover", help="Phase 3: run one discovery channel")
    d.add_argument("channel")
    il = sub.add_parser("import-leads", help="append leads from a JSONL file")
    il.add_argument("file")
    il.add_argument("--source", help="override the source field on every lead")
    sub.add_parser("aggregate", help="rebuild out/all_positions.md from every run's snapshot")
    dc = sub.add_parser("decide", help="record a decision so no later run presents the posting again")
    dc.add_argument("id", nargs="?", help="posting URL, ats:board:job_id, or 'Company|Title'")
    dc.add_argument("decision", nargs="?", choices=("applied", "dismissed", "right_call", "fit"),
                    help="applied/dismissed: never shown again; right_call: not asked about in the digest again; fit: the rule was wrong")
    dc.add_argument("-n", "--note", default="")
    dc.add_argument("--from-tracker", metavar="FILE", help="JSON list of application-tracker rows (url, company, title, stages); every row with an applied stage becomes 'applied'")
    rf = sub.add_parser("refresh", help="phases 1-5 end to end")
    rf.add_argument("--skip-discovery", action="store_true", help="reuse leads already gathered today")
    rf.add_argument("--channels", nargs="*", help="discovery channels to run (default: all)")
    rf.add_argument("--skip", nargs="*", help="discovery channels to leave out of the default set (e.g. commoncrawl)")
    sub.add_parser("score", help="phases 4-5 only, reusing today's seed check, board pulls and leads")
    sub.add_parser("import-inbox", help="turn saved alumni-board alert emails in data/inbox/ into leads")
    sub.add_parser("apply-judgments", help="merge data/judgments/results/*.json into data/judgments.jsonl")
    args = ap.parse_args(argv)

    if args.cmd in ("refresh", "score"):
        from . import pipeline

        if args.cmd == "refresh":
            channels = args.channels or ([c for c in pipeline.CHANNELS if c not in args.skip] if args.skip else None)
            summary = pipeline.refresh(args.skip_discovery, channels)
        else:
            from . import phase1

            with __import__("radar.http", fromlist=["channel"]).channel("phase1:seed-verify"):
                results, closed = phase1.verify_seeds()
            summary = pipeline.finish(results, closed)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "import-inbox":
        from .inbox import import_inbox

        print(json.dumps(import_inbox(), indent=2))
        return 0
    if args.cmd == "apply-judgments":
        from .phase4 import apply_judgments

        print(f"applied {apply_judgments()} judgments")
        return 0

    if args.cmd == "verify-seeds":
        from . import phase1, runlog

        results, closed = phase1.verify_seeds()
        path = phase1.write_report(results, closed)
        runlog.write_run_log()
        print(f"wrote {path}")
        for r in results:
            print(f"{r.status:10} {r.row.company[:28]:28} {r.row.title[:60]:60} {r.posting.pay_display if r.posting else ''}")
        for c in closed:
            print(f"{c.status:13} {c.label[:80]}")

    elif args.cmd == "decide":
        from . import seen

        if args.from_tracker:
            rows = json.load(open(args.from_tracker, encoding="utf-8"))
            n = 0
            for r in rows if isinstance(rows, list) else rows.get("docs", []):
                if (r.get("stages") or {}).get("applied") and (r.get("url") or r.get("company")):
                    seen.record_decision(r.get("url") or f"{r['company']}|{r.get('title', '')}", "applied",
                                         note="from tracker", company=r.get("company", ""), title=r.get("title", ""))
                    n += 1
            print(f"recorded {n} applied postings from {args.from_tracker}")
        elif args.id and args.decision:
            seen.record_decision(args.id, args.decision, args.note)
            print(f"recorded {args.decision}: {args.id}")
        else:
            ap.error("decide needs ID and DECISION, or --from-tracker FILE")
    elif args.cmd == "aggregate":
        from . import aggregate

        print(json.dumps(aggregate.write(), indent=1))
    elif args.cmd == "boards":
        from . import phase2, runlog

        summary = phase2.run(companies=args.company, redetect=args.redetect)
        runlog.write_run_log()
        print(json.dumps(summary, indent=2))

    elif args.cmd == "discover":
        from .http import channel

        mod = importlib.import_module(f"radar.discover.{args.channel}")
        with channel(f"discover:{args.channel}"):
            result = mod.run()
        print(json.dumps(result, indent=2, default=str))

    elif args.cmd == "import-leads":
        from .leads import add_leads
        from .models import Lead

        from pydantic import ValidationError

        leads = []
        with open(args.file, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if line.strip():
                    try:  # one bad row is skipped, not fatal to the whole import
                        d = json.loads(line)
                        if not isinstance(d, dict):
                            raise ValueError("not a JSON object")
                        if args.source:
                            d["source"] = args.source
                        leads.append(Lead(**{k: v for k, v in d.items() if k in Lead.model_fields}))
                    except (ValueError, TypeError, ValidationError) as e:
                        print(f"warning: {args.file}:{n}: skipped malformed lead: {e}", file=sys.stderr)
        print(f"added {add_leads(leads)} of {len(leads)} leads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
