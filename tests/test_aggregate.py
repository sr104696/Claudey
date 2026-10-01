import csv

from radar import aggregate, config


def _snap(path, rows):
    cols = ["bucket", "company", "title", "url", "location", "pay_display", "pay_min", "pay_max", "pay_type", "pay_period",
            "fit_score", "fit_signals", "domain_floor", "poor_reason", "hard_exclude_reason", "posted_date", "sources",
            "ats", "board", "job_id", "pipeline"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def test_aggregate_dedupes_across_runs_and_keeps_history(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregate, "SNAP_DIR", tmp_path)
    fit = dict(bucket="fit", company="Acme", title="Regulatory Counsel", url="https://x/1", ats="greenhouse", board="acme",
               job_id="1", pay_display="$200K base", pay_min="200000", pay_max="200000", pay_type="base", pay_period="year")
    old = dict(fit, title="Product Counsel", url="https://x/2", job_id="2")
    _snap(tmp_path / "2026-09-24.csv", [fit, old])
    _snap(tmp_path / "2026-09-28.csv", [fit, dict(fit, company="Axiom Talent Platform", url="https://x/3", job_id="3"),
                                         dict(fit, title="Coffee Chats", url="https://x/4", job_id="4")])
    md, st = aggregate.build()
    assert st["unique"] == 4 and st["fits"] == 1 and st["gone_fits"] == 1 and st["not_seats"] == 1 and st["dropped"] == 1
    assert md.count("Regulatory Counsel") == 1 and "Product Counsel" in md


def test_prune_keeps_latest_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    for d in ("2026-09-01", "2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29"):
        (tmp_path / f"diff_{d}.md").write_text("x")
    assert aggregate.prune_out(4) == ["diff_2026-09-01.md"]
    assert len(list(tmp_path.glob("diff_*.md"))) == 4


def test_applied_and_dismissed_leave_the_open_lists(tmp_path, monkeypatch):
    from radar import seen

    monkeypatch.setattr(aggregate, "SNAP_DIR", tmp_path)
    base = dict(bucket="fit", company="Acme", ats="greenhouse", board="acme", pay_display="$200K base", pay_min="200000",
                pay_max="200000", pay_type="base", pay_period="year")
    a = dict(base, title="Regulatory Counsel", url="https://x/1", job_id="1")
    b = dict(base, title="Product Counsel", url="https://x/2", job_id="2")
    c = dict(base, title="Privacy Counsel", url="https://x/3", job_id="3")
    _snap(tmp_path / "2026-09-28.csv", [a, b, c])
    seen.record_decision("https://x/1", "applied")
    seen.record_decision("greenhouse:acme:2", "dismissed")
    md, st = aggregate.build()
    assert st["fits"] == 1 and st["handled"] == 2
    open_part, handled_part = md.split("## 6. Applied or dismissed")
    assert "Privacy Counsel" in open_part and "Regulatory Counsel" not in open_part and "Product Counsel" not in open_part
    assert "Regulatory Counsel" in handled_part and "Product Counsel" in handled_part
