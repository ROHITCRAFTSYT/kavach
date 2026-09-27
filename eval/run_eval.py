"""Kavach evaluation harness: rules-only vs AI-only vs fused, on a hand-written multilingual text set.

One LLM call per case (analyzer.analyse). The three systems are compared WITHOUT extra API calls:
  * rules      : signals.detect(source.segments) scored on its own (the true rules-only baseline)
  * rules_resid: the rule findings that survived the merge inside the fused analysis (rules the AI missed)
  * ai         : the verified AI findings from the same analysis, re-scored with corroboration switched off
  * fused      : analysis.risk_score / analysis.verdict (what the product shows)

Usage:
  python eval/run_eval.py                       # full set
  python eval/run_eval.py --limit 4 --concurrency 4
  python eval/run_eval.py --ids s01_en_digital_arrest,l01_en_bank_debit
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import math
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from kavach import analyzer, ingest, scoring, signals  # noqa: E402
from kavach.config import get_settings  # noqa: E402
from kavach.sarvam import SarvamGateway  # noqa: E402

SYSTEMS = ["rules", "rules_resid", "ai", "fused"]
SYSTEM_LABELS = {
    "rules": "Rules only (independent)",
    "rules_resid": "Rules residual (in fused)",
    "ai": "AI only (verified claims)",
    "fused": "Fused (product)",
}
LENIENT_POS = {"scam", "suspicious"}
STRICT_POS = {"scam"}


# ---------------------------------------------------------------------------- data
def load_dataset(path: Path) -> list[dict]:
    cases = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{n}: invalid JSON: {exc}")
        missing = {"id", "lang", "label", "category", "text"} - case.keys()
        if missing or case["label"] not in ("scam", "legit"):
            raise SystemExit(f"{path}:{n}: bad case (missing={missing}, label={case.get('label')})")
        cases.append(case)
    return cases


# ---------------------------------------------------------------------------- one case
_SCORE_HAS_AI_RAN = "ai_ran" in inspect.signature(scoring.score).parameters


def rescore(findings, ai_ran: bool):
    """scoring.score, passing `ai_ran` when this version of kavach supports it (rule-only hits are
    discounted further when the LLM read the content and chose not to flag them)."""
    return scoring.score(findings, ai_ran=ai_ran) if _SCORE_HAS_AI_RAN else scoring.score(findings)


async def run_case(case: dict, settings, gw: SarvamGateway, sem: asyncio.Semaphore, timeout: float) -> dict:
    row: dict = {"id": case["id"], "lang": case["lang"], "label": case["label"], "category": case["category"]}
    async with sem:
        t0 = time.perf_counter()
        try:
            source = ingest.from_text(case["text"], settings)
            row["detected_language"] = source.language

            # (a) independent rules-only baseline: no API involved
            rule_findings = signals.detect(source.segments)
            r_risk, r_verdict, _ = rescore(rule_findings, ai_ran=False)  # = degraded mode

            analysis = await asyncio.wait_for(analyzer.analyse(source, gw), timeout=timeout)
            row["latency_s"] = round(time.perf_counter() - t0, 2)

            # (a') rule findings that survived the merge (overlapping ones were merged away)
            resid = [f.model_copy(deep=True) for f in analysis.findings if f.source == "rule"]
            rr_risk, rr_verdict, _ = rescore(resid, ai_ran=not analysis.degraded)

            # (b) AI-only: verified AI findings, corroboration boost removed
            ai = [f.model_copy(deep=True, update={"corroborated": False})
                  for f in analysis.findings if f.source == "ai"]
            a_risk, a_verdict, _ = rescore(ai, ai_ran=True)

            row.update({
                "fused_verdict": analysis.verdict.value, "fused_risk": analysis.risk_score,
                "rules_verdict": r_verdict.value, "rules_risk": r_risk,
                "rules_resid_verdict": rr_verdict.value, "rules_resid_risk": rr_risk,
                "ai_verdict": a_verdict.value, "ai_risk": a_risk,
                "n_findings": len(analysis.findings),
                "n_ai_verified": len(ai),
                "n_rejected": len(analysis.rejected_claims),
                "n_rule_findings": len(rule_findings),
                "n_corroborated": sum(1 for f in analysis.findings if f.corroborated),
                "degraded": analysis.degraded,
                "document_kind": analysis.document_kind,
                "patterns": sorted({f.pattern_id for f in analysis.findings}),
                "rule_patterns": sorted({f.pattern_id for f in rule_findings}),
                "rejected_quotes": [f"{f.pattern_id}: {f.evidence.quote[:80]}" for f in analysis.rejected_claims],
                "error": None,
            })
        except asyncio.TimeoutError:
            row.update(error=f"timeout after {timeout:.0f}s", latency_s=round(time.perf_counter() - t0, 2))
        except Exception as exc:  # record and continue
            row.update(error=f"{type(exc).__name__}: {exc}", latency_s=round(time.perf_counter() - t0, 2))
    status = row["error"] or (f"fused={row['fused_verdict']}({row['fused_risk']}) rules={row['rules_verdict']} "
                              f"ai={row['ai_verdict']} rejected={row['n_rejected']}")
    print(f"  [{row['latency_s']:>6.1f}s] {row['id']:<32} label={row['label']:<5} {status}", flush=True)
    return row


# ---------------------------------------------------------------------------- metrics
def confusion(rows: list[dict], system: str, positive: set[str]) -> dict:
    tp = fp = tn = fn = 0
    for r in rows:
        pred = r[f"{system}_verdict"] in positive
        gold = r["label"] == "scam"
        if pred and gold:
            tp += 1
        elif pred:
            fp += 1
        elif gold:
            fn += 1
        else:
            tn += 1
    n = tp + fp + tn + fn
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": (tp + tn) / n if n else 0.0,
        "precision": prec, "recall": rec,
        "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
    }


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = max(0, math.ceil(p / 100 * len(s)) - 1)  # nearest-rank
    return s[k]


def compute_metrics(rows: list[dict]) -> dict:
    ok = [r for r in rows if not r.get("error")]
    metrics: dict = {"n_cases": len(rows), "n_ok": len(ok), "n_errors": len(rows) - len(ok),
                     "systems": {}, "per_language": {}, "per_category": {}}
    for s in SYSTEMS:
        metrics["systems"][s] = {"lenient": confusion(ok, s, LENIENT_POS), "strict": confusion(ok, s, STRICT_POS)}

    by_lang: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        by_lang[r["lang"]].append(r)
    for lang, rs in sorted(by_lang.items()):
        metrics["per_language"][lang] = {"n": len(rs), **{
            s: sum((r[f"{s}_verdict"] in LENIENT_POS) == (r["label"] == "scam") for r in rs) / len(rs)
            for s in ("rules", "ai", "fused")}}

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        by_cat[f"{r['label']}:{r['category']}"].append(r)
    for cat, rs in sorted(by_cat.items()):
        metrics["per_category"][cat] = {"n": len(rs), "fused_acc": sum(
            (r["fused_verdict"] in LENIENT_POS) == (r["label"] == "scam") for r in rs) / len(rs)}

    claims_verified = sum(r["n_ai_verified"] for r in ok)
    claims_rejected = sum(r["n_rejected"] for r in ok)
    claims = claims_verified + claims_rejected
    metrics["evidence"] = {
        "ai_claims": claims, "verified": claims_verified, "rejected": claims_rejected,
        "verification_rate": claims_verified / claims if claims else None,
        "cases_with_rejections": sum(1 for r in ok if r["n_rejected"]),
        "corroborated_findings": sum(r["n_corroborated"] for r in ok),
        "degraded": sum(1 for r in ok if r["degraded"]),
    }
    lat = [r["latency_s"] for r in ok if r.get("latency_s") is not None]
    metrics["latency_s"] = {"p50": percentile(lat, 50), "p95": percentile(lat, 95),
                            "max": max(lat) if lat else None, "mean": sum(lat) / len(lat) if lat else None}
    return metrics


# ---------------------------------------------------------------------------- reporting
def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def system_table(metrics: dict, mode: str) -> list[str]:
    out = ["| System | Acc | Precision | Recall | F1 | FPR | TP | FP | TN | FN |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for s in SYSTEMS:
        m = metrics["systems"][s][mode]
        out.append(f"| {SYSTEM_LABELS[s]} | {pct(m['accuracy'])} | {pct(m['precision'])} | {pct(m['recall'])} | "
                   f"{pct(m['f1'])} | {pct(m['fpr'])} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} |")
    return out


def write_report(path: Path, metrics: dict, rows: list[dict], meta: dict) -> None:
    ev, lat = metrics["evidence"], metrics["latency_s"]
    lines = [
        "# Kavach evaluation report", "",
        f"- Run: {meta['started']} | model: `{meta['model']}` | dataset: `{meta['dataset']}`",
        f"- Cases: {metrics['n_cases']} ({metrics['n_ok']} ok, {metrics['n_errors']} errors) | "
        f"concurrency {meta['concurrency']} | wall time {meta['wall_s']:.0f}s",
        "- Dataset is synthetic and hand-written; see eval/README.md. Small n: treat differences of one or two cases as noise.",
        "",
        "## Lenient: positive = verdict in {scam, suspicious}", "", *system_table(metrics, "lenient"), "",
        "## Strict: positive = verdict == scam", "", *system_table(metrics, "strict"), "",
        "## Evidence grounding", "",
        "| AI claims | Verified | Rejected (quote not in source) | Verification rate | Cases with rejections | Corroborated findings | Degraded (LLM down) |",
        "|---|---|---|---|---|---|---|",
        f"| {ev['ai_claims']} | {ev['verified']} | {ev['rejected']} | {pct(ev['verification_rate'])} | "
        f"{ev['cases_with_rejections']} | {ev['corroborated_findings']} | {ev['degraded']} |", "",
        "## Latency (per case, end-to-end analyse)", "",
        "| p50 | p95 | max | mean |", "|---|---|---|---|",
        "| " + " | ".join("n/a" if lat[k] is None else f"{lat[k]:.1f}s" for k in ("p50", "p95", "max", "mean")) + " |", "",
        "## Per-language accuracy (lenient)", "",
        "| Language | n | Rules | AI | Fused |", "|---|---|---|---|---|",
    ]
    for lang, m in metrics["per_language"].items():
        lines.append(f"| {lang} | {m['n']} | {pct(m['rules'])} | {pct(m['ai'])} | {pct(m['fused'])} |")
    lines += ["", "## Per-category accuracy (fused, lenient)", "", "| Category | n | Fused acc |", "|---|---|---|"]
    for cat, m in metrics["per_category"].items():
        lines.append(f"| {cat} | {m['n']} | {pct(m['fused_acc'])} |")
    lines += ["", "## Per-case results", "",
              "| id | lang | label | fused | risk | rules | AI | findings | rejected | latency | note |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            lines.append(f"| {r['id']} | {r['lang']} | {r['label']} | ERROR | | | | | | {r.get('latency_s', '')}s | "
                         f"{r['error'][:80].replace('|', '/')} |")
            continue
        wrong = (r["fused_verdict"] in LENIENT_POS) != (r["label"] == "scam")
        note = ("**MISS** " if wrong else "") + ("degraded " if r["degraded"] else "") + ",".join(r["patterns"])
        lines.append(f"| {r['id']} | {r['lang']} | {r['label']} | {r['fused_verdict']} | {r['fused_risk']} | "
                     f"{r['rules_verdict']} | {r['ai_verdict']} | {r['n_findings']} | {r['n_rejected']} | "
                     f"{r['latency_s']:.1f}s | {note} |")
    rejected = [(r["id"], q) for r in rows if not r.get("error") for q in r["rejected_quotes"]]
    if rejected:
        lines += ["", "## Rejected AI claims (not found in the source text)", ""]
        lines += [f"- `{cid}` {q}" for cid, q in rejected]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(metrics: dict) -> None:
    print("\n" + "=" * 92)
    print(f"{'System':<28}{'Acc':>8}{'Prec':>8}{'Rec':>8}{'F1':>8}{'FPR':>8}   {'strict F1':>10}{'strict FPR':>11}")
    print("-" * 92)
    for s in SYSTEMS:
        m, st = metrics["systems"][s]["lenient"], metrics["systems"][s]["strict"]
        print(f"{SYSTEM_LABELS[s]:<28}{pct(m['accuracy']):>8}{pct(m['precision']):>8}{pct(m['recall']):>8}"
              f"{pct(m['f1']):>8}{pct(m['fpr']):>8}   {pct(st['f1']):>10}{pct(st['fpr']):>11}")
    ev, lat = metrics["evidence"], metrics["latency_s"]
    print("-" * 92)
    print(f"cases ok={metrics['n_ok']}/{metrics['n_cases']}  AI claims={ev['ai_claims']} verified={ev['verified']} "
          f"rejected={ev['rejected']} (verification rate {pct(ev['verification_rate'])})  degraded={ev['degraded']}")
    if lat["p50"] is not None:
        print(f"latency p50={lat['p50']:.1f}s p95={lat['p95']:.1f}s max={lat['max']:.1f}s")
    print("=" * 92)


# ---------------------------------------------------------------------------- main
async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default=str(ROOT / "eval" / "dataset.jsonl"))
    ap.add_argument("--limit", type=int, default=None, help="only the first N cases (after --ids)")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--ids", default=None, help="comma-separated case ids")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results"))
    ap.add_argument("--case-timeout", type=float, default=480.0, help="seconds per case before recording a timeout")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    cases = load_dataset(Path(args.dataset))
    if args.ids:
        wanted = [i.strip() for i in args.ids.split(",") if i.strip()]
        unknown = set(wanted) - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"unknown ids: {sorted(unknown)}")
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("no cases selected")

    settings = get_settings()
    gw = SarvamGateway(settings)
    sem = asyncio.Semaphore(max(1, args.concurrency))
    started = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"Kavach eval: {len(cases)} cases, concurrency {args.concurrency}, model {settings.reasoning_model}", flush=True)

    t0 = time.perf_counter()
    rows = await asyncio.gather(*[run_case(c, settings, gw, sem, args.case_timeout) for c in cases])
    wall = time.perf_counter() - t0

    metrics = compute_metrics(rows)
    meta = {"started": started, "model": settings.reasoning_model, "dataset": Path(args.dataset).name,
            "concurrency": args.concurrency, "wall_s": wall, "n_selected": len(cases),
            "ids": [c["id"] for c in cases]}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps({"meta": meta, "metrics": metrics, "rows": rows},
                                                 ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out / "report.md", metrics, rows, meta)
    print_summary(metrics)
    print(f"wrote {out / 'results.json'} and {out / 'report.md'} (wall {wall:.0f}s)")


if __name__ == "__main__":
    asyncio.run(main())
