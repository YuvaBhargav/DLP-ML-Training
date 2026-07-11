# Email DLP — ML-Assisted Incident Severity Classification
### A deep-dive technical reference for every component, decision, and data flow

---

## Table of Contents

1. [What This System Does](#1-what-this-system-does)
2. [What It Does NOT Do](#2-what-it-does-not-do)
3. [Repository Structure](#3-repository-structure)
4. [End-to-End Pipeline Flow](#4-end-to-end-pipeline-flow)
5. [Stage 1 — Mock Data Generation](#5-stage-1--mock-data-generation)
6. [Stage 2 — BIN Assignment](#6-stage-2--bin-assignment)
7. [Stage 3 — Feature Engineering](#7-stage-3--feature-engineering)
8. [Stage 4 — DBSCAN Clustering (Sub-bins)](#8-stage-4--dbscan-clustering-sub-bins)
9. [Stage 5 — Analyst Labeling](#9-stage-5--analyst-labeling)
10. [Stage 6 — Behavioral Baseline Engine](#10-stage-6--behavioral-baseline-engine)
11. [Stage 7 — Supervised ML Training](#11-stage-7--supervised-ml-training)
12. [Stage 8 — Batch Inference (classify.py)](#12-stage-8--batch-inference-classifypy)
13. [All Features Explained](#13-all-features-explained)
14. [All Labels Explained](#14-all-labels-explained)
15. [Model Selection Rationale](#15-model-selection-rationale)
16. [How to Run Everything (Step by Step)](#16-how-to-run-everything-step-by-step)
17. [Input/Output Formats](#17-inputoutput-formats)
18. [Why 100% Accuracy is Misleading](#18-why-100-accuracy-is-misleading)
19. [Known Limitations](#19-known-limitations)
20. [What Production Would Need](#20-what-production-would-need)
21. [Phase 2 — Multi-Bin Expansion](#21-phase-2--multi-bin-expansion)
22. [Phase 3 — Netskope Ingestion, Local LLM Integration & Rule Refinements](#22-phase-3--netskope-ingestion-local-llm-integration--rule-refinements)
23. [Phase 4 — Human-in-the-Loop Feedback & Auto-Retraining](#23-phase-4--human-in-the-loop-feedback--auto-retraining)

---

## 1. What This System Does

This system takes **email DLP log events** (already detected by an enterprise DLP
tool like Netskope) and automatically classifies each event's **severity**:

```
MEDIUM   →  Log and monitor (policy exception, low risk)
HIGH     →  Human analyst must review
CRITICAL →  Escalate immediately (repeat offender, dangerous pattern)
```

The enterprise DLP already handled content detection — it applied regex rules,
identified PAN/Aadhaar/DL numbers, and triggered a policy alert. This system
sits **downstream** of that: it reads those alerts and decides how urgently they
need a human response, based on behavioral context.

---

## 2. What It Does NOT Do

- **Does NOT read email body content** — no NLP, no content scanning
- **Does NOT run regex** — that is the enterprise DLP's job
- **Does NOT auto-block or auto-close** — humans retain enforcement authority
- **Does NOT replace analysts** — it prioritizes their queue

---

## 3. Repository Structure

```
DLP-ML-Training/
│
├── bins/                           ← All generated and processed data
│   ├── all_bins.csv                ← Combined CSV of all 3 bins (30k events)
│   ├── bin_001/                    ← BIN_001 specific files
│   │   ├── bin_001.jsonl                  ← Raw generated events (10k)
│   │   ├── bin_001_clustered_final.json   ← After DBSCAN (has sub_bin_id)
│   │   ├── bin_001_labels.json            ← Analyst-assigned labels per sub-bin
│   │   ├── bin_001_subbin_summary.csv     ← Per sub-bin stats for analyst review
│   │   ├── bin_001_timestamped.jsonl      ← After add_timestamps.py (has sender pool + timestamps)
│   │   └── bin_001_enriched.jsonl         ← Final: has all features + severity label
│   ├── bin_002/                    ← Fully processed files for BIN_002
│   │   └── bin_002.jsonl                  
│   └── bin_003/                    ← Fully processed files for BIN_003
│       └── bin_003.jsonl                  
│
├── models/                         ← Trained model artefacts (created by train.py)
│   ├── bin_001/                    ← Models for BIN_001
│   ├── bin_002/                    ← Models for BIN_002
│   └── bin_003/                    ← Models for BIN_003
│       ├── severity_model.joblib   ← The trained classifier (Gradient Boosting)
│       ├── scaler.joblib           ← StandardScaler (MUST be applied before predicting)
│       ├── label_encoder.joblib    ← Maps 0/1/2 → CRITICAL/HIGH/MEDIUM
│       ├── feature_list.json       ← Ordered list of feature names the model expects
│       └── sender_history.json     ← Sender event history from training data (baseline)
│
├── Mockdata_gen/                   ← Scripts used to generate synthetic data
│   ├── bins_gen.py                 ← Generates bin_001, bin_002, bin_003 raw events
│   ├── sub_bin_gen.py              ← Runs DBSCAN clustering on any bin dynamically
│   ├── sub_bin_context.py          ← Generates sub-bin summary CSV for analysts
│   └── generate_labels_002_003.py  ← Simulates analyst labeling for Phase 2 bins
│
├── src/                            ← Main source code
│   ├── add_timestamps.py           ← Adds timestamps/senders to any bin dynamically
│   ├── baseline_engine.py          ← Computes behavioral features per bin
│   ├── build_sender_history.py     ← Serializes training sender history per bin
│   ├── classify.py                 ← Multi-bin batch inference on mixed log files
│   ├── gen_10k_mixed_log.py        ← Generates a 10,000 event realistic test log spanning 3 bins
│   ├── gen_dashboard.py            ← Renders interactive PoC dashboard
│   ├── predict.py                  ← Interactive single-event predictor (CLI)
│   └── train.py                    ← Trains and saves the ML model per bin
│
├── sample_log.jsonl                ← Example input for classify.py
├── sample_mixed.jsonl              ← Mini multi-bin sample
├── test_10k_mixed.jsonl            ← 10,000 randomized events across all bins
├── dashboard.html                  ← The fully interactive HTML PoC dashboard
├── requirements.txt                ← Python dependencies
├── .gitignore
└── readme.md                       ← This file
```

---

## 4. End-to-End Pipeline Flow

```
[bins_gen.py]
  Generate 10,000 raw email DLP events for BIN_001
  → bins/bin_001/bin_001.jsonl

[sub_bin_gen.py]
  Engineer 4 features per event
  → Run DBSCAN clustering
  → Assign sub_bin_id to each event
  → bins/bin_001/bin_001_clustered_final.json

[sub_bin_context.py]
  Summarize each sub-bin (event counts, dominant domain, policy mix)
  → bins/bin_001/bin_001_subbin_summary.csv

[HUMAN ANALYST]
  Review the sub-bin summary
  → Assign severity + policy alignment per sub-bin
  → bins/bin_001/bin_001_labels.json

[add_timestamps.py]
  Assign 300-sender Pareto-distributed pool to clustered events
  → Add 90-day realistic timestamps
  → Sort chronologically
  → bins/bin_001/bin_001_timestamped.jsonl

[baseline_engine.py]
  Process events in chronological order
  → For each event: compute 10 behavioral features from sender's prior history
  → Derive behaviorally-adjusted severity label
  → bins/bin_001/bin_001_enriched.jsonl

[train.py]
  Load enriched data (14 features, 3-class target)
  → Train Logistic Regression, Random Forest, Gradient Boosting
  → Evaluate on accuracy + high-severity FN rate
  → Save best model + scaler + encoder + feature list
  → models/

[build_sender_history.py]
  Serialize sender event history from training data
  → models/sender_history.json

--- PRODUCTION USE ---

[classify.py] (new log input)
  Load saved model + sender history baseline
  → For each new event: compute 14 features using training history + intra-batch history
  → Predict severity + confidence + recommended action
  → Output classified JSONL
```

---

## 5. Stage 1 — Mock Data Generation

**Script:** `Mockdata_gen/bins_gen.py`

Generates 10,000 events for each of 3 bins using Python's `Faker` library.

### BIN_001 (what this system focuses on)

Each event has:

```json
{
  "bin_id":       "BIN_001",
  "sender":       "john_doe@yuva.com",
  "receiver":     "johndoe@gmail.com",
  "cc":           "",
  "sender_type":  "FTE",
  "receiver_type":"Personal",
  "dlp_policy":   "PII_PAN",
  "dlp_category": "PII-Content"
}
```

**BIN_001 definition (hard rules, all must be true):**
- Sender is an internal FTE (`@yuva.com` domain)
- Receiver is a personal email domain (Gmail or Yahoo)
- CC is empty (no managerial oversight)
- DLP policy is PII-related (PAN, Aadhaar, or Driving Licence)

### BIN_002
- Source Code content (`SOURCE_CODE` policy)
- Receiver is a business domain (`partner.com`, `vendor.com`)
- CC is present (internal manager/peer)

### BIN_003
- Sender is an FTC (Fixed-Term Contractor) at `yuvaext.com`
- Receiver is personal (Gmail/Yahoo)
- Policy is Business Unit content (`BU_CONTENT_G1` through `G9`)

---

## 6. Stage 2 — BIN Assignment

BINs are **hard rule-based buckets**, not ML. An event lands in BIN_001 if and
only if all 4 conditions are simultaneously true (see above). This is deterministic.

The ML only starts after the BIN is determined.

---

## 7. Stage 3 — Feature Engineering

**Script:** `Mockdata_gen/sub_bin_gen.py` (original 4 features)

These 4 features capture **behavioral variance** within BIN_001, not risk itself:

### `sender_username_length`
Length of the local part of the sender email before `@`.
- `john@yuva.com` → length = 4
- `j.smith.1234@yuva.com` → length = 12
- Why it matters: unusually short or long usernames can indicate non-standard accounts

### `sender_username_entropy`
Shannon entropy of the sender's username characters.

```
entropy(s) = -Σ p(c) × log₂(p(c))   for each unique character c in s
```

- `"aaa"` → entropy = 0 (all same character)
- `"abc"` → entropy = 1.58 (uniform distribution over 3 chars)
- `"xK3q9z"` → high entropy (random-looking, possibly auto-generated account)
- Why it matters: service accounts or compromised accounts often have high-entropy, random-looking usernames

### `receiver_domain_frequency`
Normalized proportion of events in BIN_001 that go to this receiver domain.

```
freq("gmail.com") = count(receiver_domain == "gmail.com") / total_events
```

- In the dataset: gmail ≈ 0.50, yahoo ≈ 0.50
- Unknown domains at inference: assigned a small fallback (0.01)
- Why it matters: dominant receiver domains are typical behavior; rare domains are anomalous

### `policy_encoded`
Ordinal encoding of the triggered DLP policy:

```
PII_PAN     → 0
PII_AADHAAR → 1
PII_DL      → 2
```

- This is the only "content" signal — it comes from the DLP engine, not from reading email content

---

## 8. Stage 4 — DBSCAN Clustering (Sub-bins)

**Script:** `Mockdata_gen/sub_bin_gen.py`

DBSCAN (Density-Based Spatial Clustering of Applications with Noise) is applied
on the 4 features above after StandardScaler normalization.

### Why DBSCAN instead of K-Means or hierarchical?

| Factor | K-Means | DBSCAN |
|---|---|---|
| Predefined cluster count | Required | Not needed |
| Handles outliers | No (forces into nearest cluster) | Yes (labels as -1) |
| Handles arbitrary shapes | No | Yes |
| Sensitive to noise | Yes | By design robust |

### Parameters used

```python
DBSCAN(eps=0.5, min_samples=20, metric="euclidean")
```

- `eps=0.5`: two points are "neighbors" if their Euclidean distance after scaling ≤ 0.5
- `min_samples=20`: a cluster must have at least 20 events to be considered "core"
- Points with fewer than 20 neighbors within eps distance → labeled as noise (-1)

### Sub-bin mapping

```
cluster_label = -1  →  BIN_001_OUTLIER   (noise/anomaly)
cluster_label =  0  →  BIN_001_MAIN      (largest/densest cluster)
cluster_label =  n  →  BIN_001_EDGE_n    (smaller stable clusters)
```

### Rare edge merging

After clustering, any `BIN_001_EDGE_*` cluster with fewer than 50 events is
relabeled as `BIN_001_EDGE_RARE`. This prevents analysts from reviewing
unstable, non-repeatable patterns that may not generalize.

### Actual sub-bins produced (from training data)

| Sub-bin | Events | Dominant Policy | Dominant Domain |
|---|---|---|---|
| BIN_001_MAIN | 1,699 | PII_AADHAAR | gmail.com |
| BIN_001_EDGE_1 | 1,646 | PII_PAN | yahoo.com |
| BIN_001_EDGE_2 | 1,612 | PII_PAN | gmail.com |
| BIN_001_EDGE_3 | 1,608 | PII_AADHAAR | yahoo.com |
| BIN_001_EDGE_4 | 1,607 | PII_DL | gmail.com |
| BIN_001_EDGE_5 | 1,526 | PII_DL | yahoo.com |
| BIN_001_EDGE_RARE | 210 | Mixed | gmail.com |
| BIN_001_OUTLIER | 92 | Mixed | yahoo.com |

The clustering worked because `policy_encoded` and `receiver_domain_frequency`
cleanly separate the 6 natural groups (3 policies × 2 domains).

---

## 9. Stage 5 — Analyst Labeling

**File:** `bins/bin_001/bin_001_labels.json`

A human analyst reviewed the sub-bin summary CSV and assigned labels:

```json
[
  {
    "bin_id":     "BIN_001",
    "sub_bin_id": "BIN_001_MAIN",
    "severity":   "HIGH",
    "allowed_behavior": false,
    "auto_close_eligible": false,
    "confidence": 5,
    "review_required": true,
    "policy_alignment": "VIOLATION"
  },
  ...
  {
    "bin_id":     "BIN_001",
    "sub_bin_id": "BIN_001_EDGE_2",
    "severity":   "MEDIUM",
    "allowed_behavior": true,
    "auto_close_eligible": false,
    "confidence": 4,
    "policy_alignment": "EXCEPTION"
  },
  {
    "bin_id":     "BIN_001",
    "severity":   "HIGH",   ← no sub_bin_id = this is the fallback default
    "policy_alignment": "VIOLATION"
  }
]
```

### Why EDGE_2 is MEDIUM

`BIN_001_EDGE_2` = `PII_PAN + gmail.com` combination. The analyst treated PAN sent
to Gmail as a **monitored exception** rather than a full violation — possibly because
a business process exists where employees legitimately share PAN for tax purposes.

All other sub-bins → HIGH (outright policy violations).

### Fallback label

The last entry without a `sub_bin_id` is the **bin-level default**. Any event
with an unrecognized or missing sub_bin_id (e.g., `BIN_001_EDGE_RARE`) falls back
to this label (HIGH).

---

## 10. Stage 6 — Behavioral Baseline Engine

This is the core innovation of Phase 1. It processes events in strict chronological
order and computes 10 additional features per event based on the sender's prior history.

### Why chronological order matters

If you compute features using future events (lookahead), you create data leakage —
the model sees information it wouldn't have at inference time. The engine enforces
a strict "only use past events" rule by:
1. Sorting all events by timestamp first
2. Processing one-by-one, updating history only AFTER each event is processed

### `add_timestamps.py` — what it does

Since the original synthetic data had no timestamps, this script adds them:

**Sender pool:** 300 senders (`user001@yuva.com` through `user300@yuva.com`)

**Pareto/power-law distribution of events per sender:**
```python
weights_raw = np.random.pareto(1.2, 300) + 1.0
```
This gives a realistic distribution where:
- A few senders have 300–400 events (heavy violators)
- Most senders have 5–30 events
- The median is ~19 events

**Timestamp distribution (per event):**
```
65% → Business hours: Mon-Fri, 08:00–18:00
15% → Evening: Mon-Fri, 18:00–23:00
10% → Late night/early morning: 00:00–06:00  (suspicious)
10% → Weekend: any hour               (suspicious)
```

This creates a realistic pattern where after-hours and weekend events are rare
but identifiable — exactly what makes behavioral signals meaningful.

### `baseline_engine.py` — the 10 behavioral features

For each event, the following are computed from all **prior** events for the same sender:

#### `sender_30d_violation_count`
Total DLP events for this sender in the 30 days before the current event.
```python
cutoff_30d = current_timestamp - timedelta(days=30)
prior_30d  = [h for h in prior if h["ts"] >= cutoff_30d]
count      = len(prior_30d)
```
**Signal:** A count of 0 = first-time offender. A count of 50 = active recidivist.

#### `sender_7d_violation_count`
Same logic, 7-day window. Captures short-term escalation patterns.
```python
cutoff_7d = current_timestamp - timedelta(days=7)
count     = len([h for h in prior if h["ts"] >= cutoff_7d])
```
**Signal:** 7+ events in a week suggests intentional, not accidental behavior.

#### `sender_policy_repeat`
Binary (0 or 1). Has this sender triggered this exact DLP policy before?
```python
prior_policies      = {h["policy"] for h in prior}
sender_policy_repeat = 1 if current_policy in prior_policies else 0
```
**Signal:** Repeat of the same policy = likely not accidental. First time = possible mistake.

#### `sender_new_receiver`
Binary (0 or 1). Has this sender ever sent to this receiver before?
```python
prior_receivers   = {h["receiver"] for h in prior}
sender_new_receiver = 0 if current_receiver in prior_receivers else 1
```
**Signal:** Sending sensitive data to someone you've never emailed = higher risk.
(Note: in synthetic data, all receivers are random so this is always 1. On real
logs where people email the same colleagues repeatedly, this becomes very meaningful.)

#### `sender_daily_volume_zscore`
Z-score of today's violation count versus the sender's 30-day daily average.
```python
daily_counts = Counter(h["ts"].date() for h in prior_30d)
today_count  = daily_counts.get(today, 0) + 1

mu, std = mean(daily_counts.values()), std(daily_counts.values())
zscore  = (today_count - mu) / (std + 1e-6)
```
- z = 0: normal day
- z = +3: today has 3× more violations than the sender's average — spike
- z = -1: below average
- Fallback: 0.0 if fewer than 3 historical days (insufficient baseline)

**Signal:** Volume spikes may indicate data exfiltration attempts.

#### `sender_policy_diversity`
Count of distinct DLP policies this sender has triggered historically.
```python
sender_policy_diversity = len({h["policy"] for h in prior})
```
- 0: first-ever event
- 1: always triggers the same policy
- 3: has triggered PAN, Aadhaar, and DL at different times

**Signal:** High diversity = broader exposure to sensitive data types, more concerning.

#### `days_since_last_violation`
Elapsed days since the sender's most recent prior DLP event.
```python
if prior:
    last_ts     = max(h["ts"] for h in prior)
    days_since  = (current_ts - last_ts).total_seconds() / 86400
else:
    days_since  = 999.0   # sentinel for "first event ever"
```
- 999: first-ever event (new)
- 0.02: sent another policy-triggering email 30 minutes ago
- 30: sent one a month ago

**Signal:** Low values (< 1 day) mean rapid successive violations.

#### `hour_of_day`
Integer 0–23 from the event timestamp.

**Signal:** Emails at 2am or 11pm are unusual for legitimate business activity.

#### `is_weekend`
Binary. 1 if the event falls on Saturday or Sunday.

**Signal:** Accessing and transmitting sensitive data on a weekend raises suspicion.

#### `is_after_hours`
Binary. 1 if `hour_of_day < 8` or `hour_of_day >= 18`.

**Signal:** Captures both late-night and early-morning events.

### Behavioral label escalation rules

The baseline_engine also adjusts severity labels based on behavioral context:

```
Base label comes from analyst's sub_bin assignment:
  PAN + Gmail (EDGE_2)  → MEDIUM
  Everything else       → HIGH

Escalation MEDIUM → HIGH (any of these):
  sender_30d_violation_count >= 5          ← repeat offender
  sender_policy_repeat AND days_since < 3  ← same policy, repeated within 3 days
  is_after_hours AND sender_new_receiver   ← suspicious combination

Escalation HIGH → CRITICAL (any of these):
  sender_30d_violation_count >= 15         ← heavy recidivist
  sender_7d_violation_count  >= 7          ← 7+ violations in one week
```

**Why these thresholds?** They are starting points based on judgment. In production,
they should be tuned based on analyst feedback on what they consider "escalation-worthy."

---

## 11. Stage 7 — Supervised ML Training

**Script:** `src/train.py`

### What the model learns

Given the 14 features for an event, predict which of
{CRITICAL, HIGH, MEDIUM} is the correct severity.

The model does not use business rules — it learns the mapping from examples in
the enriched training data where the labels were derived by the behavioral engine.

### The 14 features (in order)

```python
FEATURE_COLS = [
    # Original (from DBSCAN feature engineering)
    "sender_username_length",
    "sender_username_entropy",
    "receiver_domain_frequency",
    "policy_encoded",
    # Behavioral (from baseline_engine.py)
    "sender_30d_violation_count",
    "sender_7d_violation_count",
    "sender_policy_repeat",
    "sender_new_receiver",
    "sender_daily_volume_zscore",
    "sender_policy_diversity",
    "days_since_last_violation",
    "hour_of_day",
    "is_weekend",
    "is_after_hours",
]
```

The **order matters** — the scaler and model are fitted on this exact column order.
The list is saved to `models/feature_list.json` and loaded by classify.py at inference.

### Train/test split

```python
train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
```

- 8,000 events for training, 2,000 for testing
- `stratify=y` ensures CRITICAL/HIGH/MEDIUM proportions are preserved in both splits
  (important because MEDIUM is rare — only 173 events / 1.7% of data)

### StandardScaler

```python
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled  = scaler.transform(X_test)
```

Normalizes each feature to zero mean, unit variance. This is required because:
- `sender_30d_violation_count` can range 0–150
- `is_weekend` is binary (0 or 1)
- Without scaling, large-magnitude features would dominate

**Critical:** The scaler is fitted ONLY on training data. Test data uses the
training distribution's mean and std — this prevents data leakage.

### Three models trained

#### Logistic Regression
```python
LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")
```
- `class_weight="balanced"` adjusts weights inversely proportional to class frequency:
  MEDIUM (1.7%) gets ~58× more weight than CRITICAL/HIGH
- Simple linear decision boundary in 14-dimensional feature space
- Result: 95.3% accuracy, 2.49% high-severity FN rate

#### Random Forest
```python
RandomForestClassifier(n_estimators=200, random_state=42,
                       class_weight="balanced", n_jobs=-1)
```
- 200 decision trees, each trained on a random bootstrap sample
- Final prediction = majority vote across all trees
- `n_jobs=-1` uses all CPU cores
- Result: 99.95% accuracy, 0% FN rate

#### Gradient Boosting
```python
GradientBoostingClassifier(n_estimators=200, random_state=42, max_depth=4)
```
- Builds 200 trees sequentially — each tree corrects errors of previous trees
- `max_depth=4` limits tree complexity to prevent overfitting
- No built-in class_weight — relies on the label distribution in the data
- Result: 100% accuracy, 0% FN rate ← selected as best

### Success criteria

```
Accuracy >= 80%                      ← floor, not ceiling
High-severity FN rate < 5%          ← primary safety constraint
```

**High-severity FN rate** = % of actual CRITICAL/HIGH events that the model
predicted as MEDIUM. These are the dangerous misclassifications — a critical
incident gets missed and goes unreviewed.

### Model selection

```python
best = min(results, key=lambda n: (results[n]["fn_rate"], -results[n]["acc"]))
```

Primary sort: lowest FN rate. Tie-break: highest accuracy. Safety first.

### Feature importance (from Random Forest)

```
sender_30d_violation_count    0.3287  ← 33% — most important feature
sender_7d_violation_count     0.1731
policy_encoded                0.1474
days_since_last_violation     0.0910
receiver_domain_frequency     0.0907
sender_daily_volume_zscore    0.0412
sender_policy_diversity       0.0401
is_after_hours                0.0252
sender_policy_repeat          0.0250
hour_of_day                   0.0203
sender_username_entropy       0.0099
sender_username_length        0.0064
is_weekend                    0.0010
sender_new_receiver           0.0000  ← 0 because all synthetic receivers are unique
```

**Key takeaway:**
- Behavioral features: 74.6% of total importance
- Original features: 25.4%

The 30-day and 7-day violation counts are the most powerful predictors —
sender history dominates over content-based signals.

---

## 12. Stage 8 — Batch Inference (classify.py)

**Script:** `src/classify.py`

### How the sender history baseline works

At training time, we know each sender's full event history. At inference time
on new logs, a sender's history is loaded from `models/sender_history.json`
(serialized from training data) and merged with events that appear earlier in
the same batch being classified.

```
new_event arrives for user001@yuva.com
    ↓
Load user001's training history (events from Oct-Dec 2025)
    + any user001 events earlier in the current batch
    ↓
Compute 14 features using this combined prior history
    ↓
Scale with saved scaler
    ↓
Predict with saved model
```

### Intra-batch history accumulation

Events in the same batch are processed in timestamp order. Each classified event
is added to `batch_history` so subsequent events for the same sender see it:

```python
batch_history: dict[str, list] = defaultdict(list)

for ev in sorted_events:
    combined_prior = training_history.get(sender) + batch_history[sender]
    feats = compute_features(ev, combined_prior)
    # ... classify ...
    batch_history[sender].append({"ts": ts, "policy": policy, "receiver": receiver})
```

This means: if user001 sends 3 events in the same log batch, the 2nd event
"sees" the 1st as prior history, and the 3rd sees both. This is correct
production behavior — in a streaming system, each event knows about all
previous events.

### New senders (not in training history)

If a sender has no entry in `sender_history.json`, `prior = []` — they get
behavioral features of 0/999 (no history). The model handles this gracefully:
- `sender_30d_violation_count = 0` → not a repeat offender
- `days_since_last_violation = 999` → first-ever event
- `sender_policy_repeat = 0` → first time for this policy

The model learned from training that these values correspond to low-history
events, typically labeled MEDIUM if the underlying policy+domain combination
is the PAN→Gmail exception.

### Output fields per classified event

```json
{
  "sender":              "user001@yuva.com",
  "receiver":            "victim@gmail.com",
  "dlp_policy":          "PII_PAN",
  "timestamp":           "2026-01-15T14:32:00",
  "predicted_severity":  "MEDIUM",
  "confidence_pct":      100.0,
  "recommended_action":  "LOG_AND_MONITOR",
  "behavioral_context": {
    "sender_30d_violations":     12,
    "sender_7d_violations":       3,
    "is_repeat_policy":          true,
    "is_new_receiver":           true,
    "is_after_hours":            false,
    "is_weekend":                false,
    "days_since_last_violation": 0.24
  }
}
```

### Recommended actions

```
MEDIUM   → LOG_AND_MONITOR        (add to monitoring queue, no immediate action)
HIGH     → HUMAN_REVIEW_REQUIRED  (assign to analyst for review within SLA)
CRITICAL → ESCALATE_IMMEDIATELY   (page on-call analyst, consider suspension)
```

---

## 13. All Features Explained

| Feature | Source | Type | Range | Meaning |
|---|---|---|---|---|
| sender_username_length | Email field | int | 1–50 | Length of sender's username |
| sender_username_entropy | Computed | float | 0–4 | Randomness of username characters |
| receiver_domain_frequency | Computed | float | 0–1 | How common is this destination domain |
| policy_encoded | DLP log | int | 0, 1, 2 | PAN=0, Aadhaar=1, DL=2 |
| sender_30d_violation_count | History | int | 0–500 | DLP hits in last 30 days |
| sender_7d_violation_count | History | int | 0–100 | DLP hits in last 7 days |
| sender_policy_repeat | History | 0/1 | binary | Has sender triggered this policy before? |
| sender_new_receiver | History | 0/1 | binary | Never emailed this receiver before? |
| sender_daily_volume_zscore | History | float | -∞ to +∞ | Today's volume vs. sender's baseline |
| sender_policy_diversity | History | int | 0–3 | Distinct policy types triggered |
| days_since_last_violation | History | float | 0–999 | Days since previous DLP event |
| hour_of_day | Timestamp | int | 0–23 | Hour of the event |
| is_weekend | Timestamp | 0/1 | binary | Saturday or Sunday? |
| is_after_hours | Timestamp | 0/1 | binary | Before 8am or after 6pm? |

---

## 14. All Labels Explained

| Label | Trigger condition | Recommended action | Auto-close? |
|---|---|---|---|
| MEDIUM | First-time PAN→Gmail (EDGE_2 pattern) with no escalation signals | Log and monitor | Not eligible |
| HIGH | Any violation not meeting MEDIUM criteria, OR MEDIUM escalated by behavioral signals | Human review required | No |
| CRITICAL | HIGH sender with 15+ violations in 30 days OR 7+ in a week | Escalate immediately | No |

---

## 15. Model Selection Rationale

### Why not just use rules?

Rules (`if policy == PAN and domain == gmail → MEDIUM`) are brittle. They don't
generalize to combinations of signals. The ML model learns the interaction between
all 14 features simultaneously — e.g., "PAN→Gmail is MEDIUM unless the sender
has 10+ recent violations AND it's after-hours."

### Why Gradient Boosting over Random Forest?

Both achieved nearly identical results on synthetic data. GBT is selected because:
- Slightly better calibrated probabilities (confidence scores)
- Better handling of feature interactions at shallow depth (`max_depth=4`)
- In practice on real noisy data, GBT tends to outperform RF on tabular data

### Why not deep learning / neural networks?

For 14 structured tabular features and 10,000 events, gradient boosting
consistently outperforms neural networks. Neural nets excel at unstructured data
(images, text). For this use case, they would overfit and be harder to interpret.

### Why keep Logistic Regression?

LR's 95.3% is more honest. On real data, it will degrade gracefully — it won't
memorize training-specific patterns. It's a useful lower-bound benchmark.

---

## 16. How to Run Everything (Step by Step)

### Prerequisites

```powershell
# Create virtual environment
python -m venv venv

# Activate
venv\Scripts\Activate.ps1   # PowerShell
# or
venv\Scripts\activate       # Command Prompt

# Install dependencies
pip install -r requirements.txt
```

### Full pipeline (training)

```powershell
# 1. Add timestamps + sender pool to clustered BIN_001 data
venv\Scripts\python src\add_timestamps.py

# 2. Compute behavioral features + adjust labels
venv\Scripts\python src\baseline_engine.py

# 3. Train the model
venv\Scripts\python src\train.py

# 4. Serialize sender history for inference
venv\Scripts\python src\build_sender_history.py
```

### Inference on new logs

```powershell
# Print results to terminal
venv\Scripts\python src\classify.py your_log.jsonl

# Save results to file
venv\Scripts\python src\classify.py your_log.jsonl classified_output.jsonl
```

### Interactive single-event predictor

```powershell
venv\Scripts\python src\predict.py
```

---

## 17. Input/Output Formats

### Input: new log events for classify.py

One JSON object per line (JSONL format).

**Required fields:**
```json
{
  "sender":     "alice@yuva.com",
  "receiver":   "alice@gmail.com",
  "dlp_policy": "PII_PAN",
  "timestamp":  "2026-01-15T14:32:00"
}
```

**Optional fields (safe to include, not used by model):**
```json
{
  "cc":           "",
  "sender_type":  "FTE",
  "receiver_type":"Personal",
  "dlp_category": "PII-Content",
  "event_id":     "abc-123"
}
```

**Valid values for `dlp_policy`:**
- `PII_PAN`
- `PII_AADHAAR`
- `PII_DL`
- Anything else → defaults to PII_PAN (unknown policy)

**Timestamp format:** ISO 8601 — `YYYY-MM-DDTHH:MM:SS`

### Output: classified events

Same fields as input, plus:

```json
"predicted_severity":  "HIGH",          ← MEDIUM / HIGH / CRITICAL
"confidence_pct":      100.0,           ← 0–100, model's certainty
"recommended_action":  "HUMAN_REVIEW_REQUIRED",
"behavioral_context":  {
  "sender_30d_violations":      12,
  "sender_7d_violations":        3,
  "is_repeat_policy":           true,
  "is_new_receiver":            true,
  "is_after_hours":             false,
  "is_weekend":                 false,
  "days_since_last_violation":  0.24
}
```

---

## 18. Why 100% Accuracy is Misleading

The model achieves 100% on the test set for two reasons:

**Reason 1: Circular learning**
DBSCAN clustered events using 4 features. The labels came from those clusters.
The supervised model then learned on those same 4 features (plus 10 behavioral
ones). The model is partially re-learning the DBSCAN assignment.

**Reason 2: Synthetic data is too clean**
- All senders are generated by Faker → usernames are realistic but non-overlapping
- Timestamps are programmatically distributed → no real temporal noise
- Policy assignments are random → no real behavioral patterns

On real production logs you would expect:
- ~65–75% accuracy initially
- ~85–90% after tuning with behavioral features and real labeled data

The 100% result validates the **pipeline architecture and feature engineering
approach**, not the model's production-readiness.

---

## 19. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Synthetic training data | Model not calibrated for real logs | Replace with real labeled data |
| `sender_new_receiver` = 0 always | Feature wasted on synthetic data | Will activate on real logs |
| Sender history resets after retraining | New model forgets old behavior | Persist and merge history |
| No time-decay on history | A violation 30 days ago = same as yesterday | Add exponential decay weighting |
| 3 DLP policies only | Doesn't generalize to other DLP categories | Add BIN_002, BIN_003 pipelines |
| No confidence thresholds | All predictions acted on regardless of confidence | Add abstention band (70–85%) |

---

## 20. What Production Would Need

To deploy this on real Netskope/Symantec DLP logs:

1. **Real labeled data** from analyst ticket resolutions (closed/escalated tickets = ground truth labels)
2. **Persistent sender history store** (Redis, Elasticsearch, or PostgreSQL) instead of a flat JSON file
3. **Streaming inference** rather than batch — classify events as they arrive via Kafka/Pub-Sub
4. **Confidence threshold gating:**
   - Confidence > 95% → auto-action (auto-close MEDIUM, auto-escalate CRITICAL)
   - Confidence 70–95% → queue with model suggestion
   - Confidence < 70% → human review always
5. **Weekly retraining loop** on analyst-confirmed labels to handle concept drift
6. **Model monitoring** — alert if accuracy or FN rate degrades in production

---

## 21. Phase 2 — Multi-Bin Expansion

In Phase 2, the pipeline was heavily refactored to support scaling across infinite DLP bins dynamically. The system is no longer hardcoded to BIN_001.

### 1. Refactored Generic Scripts
All core processing scripts (`sub_bin_gen.py`, `add_timestamps.py`, `baseline_engine.py`, `train.py`, and `build_sender_history.py`) now accept a `--bin` parameter. 

When executed, they dynamically adapt their feature engineering. For example, DBSCAN clustering for BIN_002 utilizes `cc_domain_frequency` instead of `policy_encoded` (since the policy for BIN_002 is statically `SOURCE_CODE`).

### 2. BIN_002 & BIN_003 Implementation
The simulated "analyst" labels for these bins were generated programmatically:
- **BIN_002 (Source Code)**: Transferring source code to external business domains without manager CC is highly sensitive. The sub-bins generated default to `HIGH` and `CRITICAL`.
- **BIN_003 (Contractors)**: Fixed-Term Contractors sending internal BU content to personal emails represents the highest inherent risk pattern. As such, **100% of BIN_003 data was labeled CRITICAL**.

### 3. Dynamic Inference Routing (`classify.py`)
Because production DLP logs arrive as a mixed stream of events, `classify.py` was rewritten to be **bin-aware**. 

When a batch of 10,000 mixed events is loaded, `classify.py`:
1. Inspects the `bin_id` of the event.
2. Dynamically loads the corresponding ML model, scaler, feature list, and baseline history from `/models/bin_xxx/` into an in-memory cache.
3. Computes the behavioral features uniquely required by that bin's model.
4. Generates the prediction.

### 4. Single-Class Fallback Architecture
Because BIN_003 data is 100% `CRITICAL`, Random Forest training would fail (as it requires at least two distinct classes to compute splits). Instead of hacking the training data, `train.py` elegantly detects single-class bins and generates a `DummyModel` that mimics the scikit-learn API. 

This `DummyModel` is pickled and dynamically loaded by `classify.py` just like any real ML model. When called, it simply yields a 100% confidence prediction of the single class. This preserves the overarching architectural uniformity while saving vast amounts of compute.

### 5. Validation via 10k Mixed Log Simulator
To validate the Phase 2 system, a `gen_10k_mixed_log.py` script was written to simulate a massive, enterprise-scale payload:

- **Total Events**: 10,000
- **Distribution**: ~50% BIN_001, ~30% BIN_002, ~20% BIN_003
- **Chronology**: Spread out over a 30-day realistic timezone window.

When `classify.py` processed `test_10k_mixed.jsonl`, it correctly invoked the dynamic models and output:

```text
Summary:
  CRITICAL  :  5982 events
  HIGH      :  3856 events
  MEDIUM    :   162 events
```
*Note: The high concentration of CRITICAL events is due to the inherent severity of BIN_002 and BIN_003.*

### 6. HTML PoC Dashboard
A standalone, zero-dependency `dashboard.html` is generated by `gen_dashboard.py` running against the classification output. It provides stakeholders with an interactive, beautifully styled UI containing:
- High-level metric summary cards.
- Chart.js visualizations of Severity Distribution, Policy Mix, and Temporal Anomalies.
- An interactive, filterable data table that allows analysts to click any row to reveal the **Behavioral Context** that drove the ML model's decision.

---
*Last updated: Phase 2 (Multi-Bin Expansion) complete.*

---

## 22. Phase 3 — Netskope Ingestion, Local LLM Integration & Rule Refinements

This phase introduced ingestion adapters for enterprise logs (Netskope CSV format), added a local LLM integration for AI-powered reasoning, and refined the contractor (FTC) detection and override policies.

### 1. Enterprise Netskope CSV Ingestion & Synthesis
* **Synthetic Logs Generator ([gen_netskope_logs.py](file:///d:/DLP-ML-Training/src/gen_netskope_logs.py))**: Generates 10,000 synthetic Netskope logs (`netskope_sample.csv`) containing fields such as user, receiver, CCs, policies (including `ENCRYPTED`), and legacy/analyst statuses.
* **Ingestion Adapter ([ingest_netskope.py](file:///d:/DLP-ML-Training/src/ingest_netskope.py))**: Parsed Netskope CSV files into timestamped JSONL payloads and generated standard analyst labels:
  - Maps legacy status field (e.g., `FalsePositive`, `businessrequirement` -> `MEDIUM`; `pending review` -> `HIGH`; `Critical_Escalation` -> `CRITICAL`).
  - Routes incidents dynamically to their respective BINs (BIN_001 for PII/Aadhaar/DL/ENCRYPTED, BIN_002 for SOURCECODE, and BIN_003 for BU policies).

### 2. Local LLM Triage Assistance ([app.py](file:///d:/DLP-ML-Training/src/app.py))
* **AI Analyst Reasoning**: Added `get_llm_reasoning()` that queries a local Ollama server running `llama3`.
* **Prompting Strategy**: Extracts the contextual features (e.g., contractor status, receiver type, CC counts, payload encryption) and asks the model to produce a concise 2-3 sentence SOC analyst explanation.
* **UI Integration**: Displays the generated reasoning text inside a dedicated **"🧠 AI Analyst Reasoning"** component in the Streamlit interface.

### 3. FTC and Encrypted Policy Rules Refinement ([baseline_engine.py](file:///d:/DLP-ML-Training/src/baseline_engine.py))
* **FTC Detection**: Standardized contractor identification checking by searching for `@yuvaext` in the sender's email domain.
* **Encryption Override**: Identified encrypted payloads by checking if the policy is `ENCRYPTED`. Any encrypted payload triggers an automatic severity override to `CRITICAL` in the baseline rules.

---

*Last updated: Phase 3 (Netskope Ingestion, Local LLM Integration & Rule Refinements) complete.*

---

## 23. Phase 4 — Human-in-the-Loop Feedback & Auto-Retraining

This phase closes the human-analyst loop. Analysts can now confirm or override any model prediction directly in the Streamlit UI. Every correction is persisted to a structured log file. A dedicated tab shows the full correction history with one-click retraining buttons that merge analyst corrections into the training data and immediately activate the new model — no terminal or restart required.

---

### 1. Feedback Storage — `feedback_log.jsonl`

Every analyst interaction (confirmation **or** correction) is appended as a single JSON line to `feedback_log.jsonl` at the project root.

**Schema of each entry:**

```json
{
  "timestamp":        "2026-07-11T22:49:00",
  "bin_id":           "BIN_001",
  "sender":           "contractor@yuvaext.com",
  "receiver":         "personal@gmail.com",
  "dlp_policy":       "ENCRYPTED",
  "model_prediction": "CRITICAL",
  "model_confidence": 100.0,
  "analyst_label":    "HIGH",
  "was_correct":      false,
  "notes":            "Manager had approved this transfer in advance.",
  "features": {
    "sender_30d_violation_count": 3,
    "sender_7d_violation_count":  1,
    "is_ftc":                     1,
    "is_encrypted_payload":       1,
    "is_personal_recipient":      1,
    "has_manager_cc":             0,
    "violation_count":            1,
    ...all 11+ features...
  }
}
```

| Field | Description |
|---|---|
| `was_correct` | `true` if analyst confirmed the model's label; `false` if they overrode it |
| `analyst_label` | The ground-truth label the analyst assigned (same as `model_prediction` when `was_correct=true`) |
| `features` | Complete feature vector used for that prediction — used directly for retraining |
| `notes` | Free-text analyst explanation (optional, never used by model) |

**Only `was_correct=false` entries are used during retraining.** Confirmed-correct entries are logged for audit purposes but not fed back into the training loop (the original enriched data already contains those patterns).

---

### 2. `save_feedback()` — `src/app.py`

```python
def save_feedback(bin_id, sender, receiver, policy, model_prediction,
                  model_confidence, analyst_label, was_correct, feats, notes=""):
```

- Converts any **numpy scalar** types in `feats` to native Python (`v.item()`) so the dict serialises cleanly to JSON.
- Appends one line to `feedback_log.jsonl` in append mode — never overwrites, never holds a lock between writes.
- Called immediately when the analyst clicks **📨 Submit Feedback** in the UI.

---

### 3. Analyst Feedback Form — Tab 1 (`src/app.py`)

After every successful prediction in the **🔍 Single Incident Analyzer** tab, a feedback form appears below the AI Reasoning section.

**Session state design:** The prediction details (`bin_id`, `severity`, `confidence`, full `feats` dict) are stored in `st.session_state.last_pred` the moment a result is computed. This ensures the form persists across Streamlit reruns (e.g., when the user interacts with the radio button) without re-running the ML pipeline.

**Form layout:**
- **Radio button** (horizontal): `✅ Confirmed Correct` | `⚠️ Override Severity`
- **Selectbox** (only visible on override): Shows only the two severities that are **not** the current prediction — prevents accidentally confirming the same label as an override.
- **Text area**: Optional analyst notes (placeholder gives examples of what to write).
- **Submit button**: Calls `save_feedback()` → sets `st.session_state.feedback_submitted = True` → calls `st.rerun()` to refresh the form to a confirmation message.

---

### 4. Analyst Feedback Tab — Tab 3 (`src/app.py`)

A completely new **📋 Analyst Feedback** tab with three sections:

#### 4a. Summary Metrics (4 columns)
```
📊 Total Feedback  |  ✅ Confirmed Correct  |  ⚠️ Override Corrections  |  📦 Bins with Corrections
```

#### 4b. Retrain Buttons
One **🔁 Retrain BIN_XXX (N corrections)** button is rendered per bin that has at least one override. Each button:
1. Calls `run_retrain(bin_id_r)` (the imported `retrain_from_feedback` function)
2. Wraps the call in `st.spinner` with a realistic time estimate
3. On success: calls `get_model_and_baseline.clear()` to **invalidate the `@st.cache_resource` cache** — this forces the next prediction to load the freshly trained model from disk
4. Expands a **📊 View Training Details** panel showing per-model accuracy and FN rate logs
5. Displays 3 metric cards: **New Accuracy**, **High-Severity FN Rate**, **Best Model**

#### 4c. Feedback History Table
A `st.dataframe` (full-width, hidden index) showing all feedback entries in **reverse chronological order** (most recent first) with columns:

| Column | Source |
|---|---|
| Timestamp | `entry["timestamp"][:19]` formatted as `YYYY-MM-DD HH:MM:SS` |
| Bin | `entry["bin_id"]` |
| Sender | `entry["sender"]` |
| Policy | `entry["dlp_policy"]` |
| Model Predicted | `entry["model_prediction"]` |
| Analyst Label | `entry["analyst_label"]` |
| Correct? | `✅` or `❌` |
| Notes | `entry["notes"]` |

---

### 5. `src/retrain_from_feedback.py` — Retraining Engine

A self-contained module callable from the Streamlit UI **or** the CLI:

```powershell
venv\Scripts\python src\retrain_from_feedback.py --bin BIN_001
```

#### `retrain_from_feedback(bin_id)` — Step by Step

**Step 1: Load feature list**
```python
feat_path = "models/bin_001/feature_list.json"
feature_cols = json.load(f)  # e.g. ["sender_30d_violation_count", "is_ftc", ...]
```
This guarantees the feedback rows use the **exact same column order** the scaler and model were originally fitted on.

**Step 2: Load original enriched training data**
```python
enriched_path = "bins/bin_001/bin_001_enriched.jsonl"  # e.g. 6,000 rows
df_train = df_original[ALL_FEATURES + ["severity"]].fillna(0)
```

**Step 3: Load and weight analyst corrections**
```python
FEEDBACK_WEIGHT = 3
# Only was_correct=False entries are used
if feedback_rows:
    df_feedback = pd.DataFrame(feedback_rows * FEEDBACK_WEIGHT)  # 3x duplication
    df_train = pd.concat([df_train, df_feedback], ignore_index=True)
```

**Why ×3?** Each correction row is duplicated 3 times before merging. This means a dataset of 6,000 original rows + 10 analyst corrections becomes 6,030 rows where the analyst's signal has ~5% influence. If the analyst provides 100 corrections they have ~33% weight. This is a deliberate soft-weighting rather than hard override — the model still generalises from the baseline but steers toward analyst judgement.

**Step 4: Encode labels**
```python
le = LabelEncoder()
y_enc = le.fit_transform(y)  # Refitted on the combined dataset
```
The `LabelEncoder` is **refitted** on the combined dataset. This handles the edge case where the original single-class bin (e.g., BIN_003 was 100% CRITICAL) gains a new class from analyst corrections.

**Step 5: Train 3 models**

| Model | Config |
|---|---|
| Logistic Regression | `max_iter=1000, class_weight="balanced"` |
| Random Forest | `n_estimators=200, class_weight="balanced", n_jobs=-1` |
| Gradient Boosting | `n_estimators=200, max_depth=4` |

Same 80/20 stratified split and StandardScaler as the original `train.py`.

**Step 6: Select best model**
```python
# Primary: lowest high-severity FN rate. Tie-break: highest accuracy.
best_name = min(results, key=lambda n: (results[n]["fn_rate"], -results[n]["acc"]))
```

**Step 7: Overwrite artifacts**
```
models/bin_001/severity_model.joblib  ← new model
models/bin_001/scaler.joblib          ← new scaler (fitted on expanded data)
models/bin_001/label_encoder.joblib   ← new encoder (may have new classes)
models/bin_001/feature_list.json      ← same feature list (preserved)
```

**Step 8: Cache invalidation (UI only)**
```python
get_model_and_baseline.clear()  # Clears Streamlit @st.cache_resource
```
The next prediction in Tab 1 will call `load_bin_models()` fresh from disk, loading the new `.joblib` files. No app restart required.

**Return value:**
```python
{
    "bin_id":     "BIN_001",
    "n_feedback": 5,            # corrections applied
    "model_name": "Gradient Boosting",
    "accuracy":   99.87,
    "fn_rate":    0.0,
    "log":        [...]         # per-step log strings shown in expander
}
```

---

### 6. Ollama LLM Fixes (also in Phase 3/4 boundary)

Two bugs were identified and fixed in `get_llm_reasoning()`:

#### Bug 1: 404 from hardcoded model name
The original code sent `"model": "llama3"`. If the local Ollama installation has `llama3.1:latest` (a different tag), the API returns `404 model not found`.

**Fix:** Added `get_ollama_model()` helper that:
1. Queries `GET /api/tags` to get the list of installed models
2. Tries a priority list: `llama3.1:latest` → `llama3.1` → `llama3:latest` → `llama3`
3. Falls back to any model with `"llama"` in the name
4. Finally falls back to whichever model is first in the list

#### Bug 2: Connection refused / timeout on Windows
On Windows, `localhost` can resolve to the IPv6 loopback `::1` while Ollama only listens on IPv4 `127.0.0.1`, causing `ConnectionRefusedError`.

**Fix:** Changed all Ollama URLs from `http://localhost:11434` to `http://127.0.0.1:11434`.

Additionally, the 10-second request timeout was increased to **40 seconds** because on the first request Ollama needs to load the 8B parameter model from disk into GPU/CPU RAM, which routinely takes 15–35 seconds.

---

### 7. Known Limitation: Streamlit Cloud Ephemeral Storage

When deployed to **Streamlit Community Cloud** (which clones from GitHub and runs in an ephemeral container), all file writes at runtime — `feedback_log.jsonl` and retrained `.joblib` files — exist **only in container RAM** and are lost when:
- The app goes to sleep after inactivity
- The app is redeployed
- The container is restarted by the platform

**Mitigation for full production use:**

| Option | Mechanism |
|---|---|
| **Git push after retrain** | Use PyGitHub with a PAT stored in Streamlit Secrets to commit new `.joblib` files back to the repo after every retrain |
| **External model store** | Store models in Hugging Face Hub, AWS S3, or GCS; load by URL at startup |
| **Persistent feedback DB** | Write `feedback_log` rows to Supabase, Firebase, or a hosted PostgreSQL instead of a local JSONL file |
| **GitHub Actions trigger** | Push a `feedback_log.jsonl` update to the repo, which triggers a CI workflow that retrains and commits model artifacts |

This limitation does **not** affect local execution (`streamlit run src/app.py`) where all writes are permanent.

---

*Last updated: Phase 4 (Human-in-the-Loop Feedback & Auto-Retraining) complete.*
