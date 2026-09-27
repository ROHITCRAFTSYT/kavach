# Kavach evaluation harness

A small, repeatable benchmark for Kavach's text path (`ingest.from_text` then `analyzer.analyse`).
It measures whether the product gets the verdict right, and also what each half of the system
(the offline rule engine and the Sarvam LLM) contributes.

## Dataset (`dataset.jsonl`)

40 **synthetic, hand-written** messages (SMS / WhatsApp / email / notice text), 20 `scam` and 20 `legit`,
one JSON object per line: `{"id", "lang", "label", "category", "text"}`. No case is real user data.
Phone numbers use the obviously fake `98765 xxxxx` pattern, links use made-up `.xyz` domains, and
brands are generic ("your bank"). The only real domains are the official government portals the
legit tax reminders point to.

| Language | Cases | | Language | Cases |
|---|---|---|---|---|
| English (`en`) | 8 | | Marathi (`mr`) | 2 |
| Hindi (`hi`) | 6 | | Kannada (`kn`) | 2 |
| Hinglish, Latin script (`hinglish`) | 4 | | Malayalam (`ml`) | 2 |
| Tamil (`ta`) | 4 | | Gujarati (`gu`) | 2 |
| Telugu (`te`) | 4 | | Punjabi (`pa`) | 2 |
| Bengali (`bn`) | 4 | | | |

Each language has an equal number of scam and legit cases. The file alternates scam and legit,
so `--limit N` gives a roughly balanced sample.

**Scam archetypes**, taken from public Indian cyber-fraud advisories (I4C / cybercrime.gov.in, RBI awareness material):
digital arrest by fake CBI or police, courier parcel with drugs, fake KYC or account/SIM block, OTP request,
"electricity will be cut tonight, call this number", lottery/KBC, task-based part-time job,
investment group with guaranteed returns, fake cashback/refund link, AnyDesk remote access,
fake customer care, fake loan app with a processing fee.

**Subtle scams** have no fraud keywords, so a keyword matcher can't catch them.
`s08` is a Hinglish "code sent to you by mistake" request that never says "OTP".
`s20` is a Punjabi "relative abroad, new number, send money, don't tell anyone" message.

**Legit cases** are bank debit and credit alerts, OTP delivery messages, utility bills with due dates
(one of them warns about disconnection), a municipal property-tax notice, a Lok Adalat court notice,
passport police verification, appointment reminders, delivery notifications, a government scheme notice,
school notices, and ITR/GST reminders that point to official portals.

**Hard negatives** are legit messages that use scam vocabulary:
- `l01`, `l02`, `l06`, `l13` say "never share your OTP/PIN".
- `l09` mentions RBI, KYC and OTP.
- `l07` is about police verification and `l16` is a court notice.
- `l11` is a genuine bill that warns about disconnection.
- `l03` asks the customer to share a delivery code.

## How to run

The harness needs `SARVAM_API_KEY` in the repo-root `.env`, the same as the app.

```
python eval/run_eval.py                                   # all 40 cases (about 10-15 min at concurrency 3)
python eval/run_eval.py --limit 4 --concurrency 4         # quick check
python eval/run_eval.py --ids s01_en_digital_arrest,l09_hinglish_bank_kyc_advisory
python eval/run_eval.py --out eval/results_run2 --case-timeout 480
```

Each case makes one LLM call, and each call typically takes 25-130 s. Errors and timeouts are recorded
in that case's row, and the run continues.

Outputs:
- `eval/results/results.json`: run metadata, all metrics, and one row per case. Each row has the id, language,
  label, fused verdict and risk, rules-only verdict, AI-only verdict, the number of findings,
  the number of rejected claims, latency, the patterns found and the text of rejected quotes.
- `eval/results/report.md`: the same information as markdown tables, with fused misses marked **MISS**.
- A summary table printed to stdout.

## Ablation: rules vs AI vs fused

`analyse()` runs the rule engine (`signals.detect`) and one LLM call. It keeps only the AI findings whose
quote can be found in the source (grounding), then merges those with the rules and scores the result.
The harness takes that single analysis and re-scores subsets of its findings with `scoring.score`,
so the comparison costs no extra API calls:

| System | Definition |
|---|---|
| **Rules only (independent)** | `signals.detect(source.segments)` scored on its own. This is what the product shows when the LLM is down (degraded mode). |
| **Rules residual (in fused)** | The `source=="rule"` findings left in `analysis.findings`. These are rules for patterns the AI did *not* flag, because overlapping rule hits are merged into the AI finding. This number shows how much the rules add on top of the AI, and how many false positives they add. |
| **AI only** | The `source=="ai"` findings, which are grounding-verified by construction, re-scored with `corroborated=False` so rules give them no boost. |
| **Fused** | `analysis.risk_score` / `analysis.verdict`, which is what the user sees. |

If the installed `scoring.score` accepts `ai_ran`, the harness passes it. That gives rule-only findings the same
extra discount the product applies when the LLM ran. The independent rules baseline is scored with `ai_ran=False`.

## Metrics

Verdicts are mapped to a binary prediction, with `scam` as the positive class:
- **Lenient**: positive = verdict in {`scam`, `suspicious`}. This is the headline number: "would the user be warned?"
- **Strict**: positive = verdict `scam` only.

For each system the harness reports:
- **Accuracy**: (TP+TN)/N.
- **Precision**: TP/(TP+FP).
- **Recall**: TP/(TP+FN).
- **F1**.
- **False-positive rate**: FP/(FP+TN), the share of legit messages wrongly flagged. This is the key number for trust on the hard negatives.
- **Confusion matrix**: TP, FP, TN, FN.

Other reported numbers:
- **Per-language accuracy** (lenient) for the rules, AI and fused systems, and **per-category** accuracy for fused.
- **Evidence grounding**:
  - AI claims = verified plus rejected. Rejected claims are in `analysis.rejected_claims`: quotes the LLM gave that could not be found in the source.
  - Verification rate = verified / claims.
  - Also reported: the number of corroborated findings (flagged by both AI and rules).
- **Degraded**: the number of cases where the LLM call failed and only rules ran.
- **Latency**: p50 and p95 (nearest-rank), plus max and mean, of wall-clock `analyse()` time per case. This number depends on concurrency and API load.

## Caveats

- The dataset is small, synthetic and hand-written by the developers. It is a regression and ablation check, not an
  estimate of real-world accuracy. A difference of one case moves accuracy by 2.5 points.
- The labels encode the authors' judgement. Some legit cases, such as the delivery code in `l03`, are deliberately borderline.
- LLM output is not fully deterministic even at low temperature, so re-runs can differ by a case or two.
