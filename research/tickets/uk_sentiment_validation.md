# UK Sentiment Data Utility Validation (Step 69)

**Status:** READY TO EXECUTE (research-only; no runtime integration)
**Date:** 2026-02-25
**Owner:** Copilot (execution) + human reviewer (final recommendation)
**Scope:** Offline experiment design and recommendation only.

---

## 1) Objective

Assess whether adding sentiment features improves UK-first equity research performance
enough to justify data/complexity overhead.

This ticket does **not** add production/runtime features.

---

## 2) Candidate UK-Compatible Sentiment Paths (Free/Low-Cost)

### Path A — Massive/Polygon News Sentiment (existing integration path)

- Source: Polygon/Massive news endpoint (`/v2/reference/news`)
- Current relevance: already aligned with existing `news_features.py` workflow
- Cost profile: free/low-cost tier compatible for bounded experiments
- Key constraints:
  - article volume and historical depth limits by tier
  - potential UK coverage skew by symbol and period

### Path B — Financial News RSS + Lexicon Scoring (VADER/FinVADER)

- Source examples: Reuters business RSS, FT markets headlines, Yahoo Finance UK feeds
- Method: timestamped headline ingestion + deterministic lexicon sentiment scoring
- Cost profile: free feeds + local scoring
- Key constraints:
  - feed stability / parser maintenance
  - weaker domain adaptation vs model-based NLP

---

## 3) Offline Experiment Plan

### 3.1 Universe and Time Window

- Symbol basket (UK approved basket): `HSBA.L`, `VOD.L`, `BP.L`, `BARC.L`, `SHEL.L`
- Baseline horizon: H5 label regime in `FEATURE_LABEL_SPEC.md`
- Suggested evaluation period: at least 2 years OOS-equivalent folds

### 3.2 Compared Variants

1. **Baseline**: current non-sentiment feature set
2. **Baseline + Path A sentiment**
3. **Baseline + Path B sentiment**

### 3.3 Protocol

- Use existing walk-forward methodology and anti-leakage rules in research specs
- Keep model family constant across variants (isolate sentiment effect)
- Keep costs/slippage assumptions constant across variants
- Record missing-coverage rate for sentiment features per symbol/fold

---

## 4) Validation Criteria (Hard)

To recommend `proceed`, a sentiment variant must satisfy both:

1. **PR-AUC improvement:**
   - `delta_pr_auc >= +0.02` vs baseline
2. **Drawdown safety:**
   - max drawdown must **not** worsen by more than 5% relative to baseline
   - i.e. `drawdown_worsening_pct <= 5%`

If criteria are mixed/inconclusive, return `park`.
If criteria fail clearly or data quality is poor, return `reject`.

---

## 5) Output Template (Recommendation)

```markdown
## Step 69 Recommendation

- Decision: proceed | park | reject
- Chosen path: Path A | Path B | none

### Metrics Summary
- Baseline PR-AUC: <value>
- Sentiment PR-AUC: <value>
- Delta PR-AUC: <value>
- Baseline max drawdown: <value>
- Sentiment max drawdown: <value>
- Drawdown worsening (%): <value>

### Data Quality Notes
- Coverage rate (articles/headlines per symbol): <value>
- Missing sentiment feature rate: <value>
- Any timestamp alignment issues: yes/no + notes

### Cost/Complexity Notes
- Ongoing ingestion complexity: low/medium/high
- Provider risk (availability/limits): low/medium/high

### Rationale
<2–5 bullets>

### Follow-on Action
- If proceed: create implementation step with acceptance criteria
- If park: define revisit trigger (date/condition)
- If reject: record no-go rationale in LPDD evolution log
```

---

## 6) Guardrails

- No runtime (`src/`) integration in this ticket
- No promotion decision without claim-integrity metadata
- Keep all timestamps UTC-aware and leakage-safe joins only
