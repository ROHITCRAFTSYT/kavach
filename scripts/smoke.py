"""Run the full pipeline on every bundled sample and print a compact report."""
import asyncio, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
from kavach.app import SAMPLE_CATALOG, SAMPLES, gateway, settings
from kavach import pipeline

async def one(entry):
    kw = dict(text=entry.get("text"), data=None, filename="")
    if entry["kind"] != "text":
        kw.update(data=(SAMPLES / entry["id"]).read_bytes(), filename=entry["id"], text=None)
    t = time.time(); out = {}
    async for ev in pipeline.run(gw=gateway, settings=settings, language="auto", **kw):
        out.setdefault(ev["type"], []).append(ev)
    if "error" in out:
        return f"{entry['id']}: ERROR {out['error'][0]['message']}"
    a = out["analysis"][0]["analysis"]; loc = out["localized"][0]["localized"]
    lines = [f"== {entry['id']}  {time.time()-t:.1f}s  verdict={a['verdict']} risk={a['risk_score']} lang={loc['language']} via={loc['method']} degraded={a['degraded']}"]
    for f in a["findings"]:
        ev = f["evidence"]
        lines.append(f"   [{f['source']}{'+rule' if f['corroborated'] else ''}] {f['pattern_id']} ({f['severity']}) seg={ev['segment_id']} score={ev['score']} :: {ev['quote'][:70]}")
    for f in a["rejected_claims"]:
        lines.append(f"   REJECTED {f['pattern_id']} score={f['evidence']['score']} :: {f['evidence']['quote'][:70]}")
    lines.append("   facts: " + "; ".join(f"{k['label']}={k['value']}" for k in a["key_facts"])[:300])
    lines.append("   " + loc["headline"] + " | " + loc["explanation"][:220])
    lines.append("   trace: " + ", ".join(f"{s['name']}={s['ms']}ms" for s in out["trace"][0]["spans"]))
    return "\n".join(lines)

async def main():
    only = sys.argv[1:]
    entries = [e for e in SAMPLE_CATALOG if not only or e["id"] in only]
    for r in await asyncio.gather(*[one(e) for e in entries]):
        print(r)

asyncio.run(main())
