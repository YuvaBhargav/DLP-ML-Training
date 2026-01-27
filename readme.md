📧 Email DLP – ML-Assisted Incident Classification (BIN_001)
1. Project Overview

This project implements a Machine Learning–assisted, human-in-the-loop classification system for Email Data Loss Prevention (DLP) incidents, with a focus on regulated environments (e.g., banking, financial services).

The goal is to:

Discover behavioral patterns in email DLP incidents

Group similar incidents into bins and sub-bins

Enable analyst-driven labeling at pattern level

Prepare the system for future automation and retraining

⚠️ Scope (current phase):

Channel: Email only

Data source: Netskope-style email DLP logs

Coverage: BIN_001 only (PII → Personal Email → No CC)

2. High-Level Architecture (Current Phase)
Email DLP Logs (JSONL)
        ↓
Feature Engineering
        ↓
Hard Bin Assignment (BIN_001)
        ↓
DBSCAN Clustering (Sub-bins)
        ↓
Rare Cluster Merging
        ↓
Analyst Review & Labeling


No auto-close or automation is enabled at this stage.

3. BIN_001 Definition

BIN_001 captures the following behavior:

Internal Full-Time Employee (FTE) sending PII data to a personal email address without CC or oversight

Key Characteristics

Outbound email

Sender: Internal corporate domain

Receiver: Personal email domain (Gmail, Yahoo, etc.)

CC: None

Content: PII (PAN, Aadhaar, Driving License)

Regulatory Context

In regulated entities, this pattern represents a critical compliance risk due to:

Uncontrolled data destination

Absence of managerial oversight

Strict regulatory requirements around PII handling

4. Input Data Format

Data is stored as JSON Lines (.jsonl), one event per line.

Example:

{"sender":"user@corp.com","receiver":"user@gmail.com","dlp_policy":"PII_PAN"}


File used:

bins/bin_001/bin_001.jsonl

5. Feature Engineering

For each email event, the following features are derived:

Feature	Description
sender_username_length	Length of sender username
sender_username_entropy	Shannon entropy of username (human vs random)
receiver_domain_frequency	Normalized frequency of receiver domain
policy_encoded	Encoded PII subtype (PAN / Aadhaar / DL)

These features represent behavioral variance, not severity.

6. Clustering Approach (DBSCAN)
Why DBSCAN?

No prior knowledge of number of clusters

Naturally detects outliers

Suitable for noisy security data

Parameters
eps = 0.5
min_samples = 20

Output

Each event is assigned a cluster_label, mapped to a sub_bin_id:

BIN_001_MAIN

BIN_001_EDGE_n

BIN_001_OUTLIER

7. Rare Edge Cluster Merging

Clusters with fewer than 50 events are considered unstable and merged into:

BIN_001_EDGE_RARE


This prevents analyst overload while preserving safety.

Final Sub-Bins for BIN_001
Sub-Bin	Purpose
BIN_001_MAIN	Most common, repeatable behavior
BIN_001_EDGE_1–5	Stable behavioral variants
BIN_001_EDGE_RARE	Rare but repeatable patterns
BIN_001_OUTLIER	Unknown or anomalous behavior

Final output file:

bins/bin_001_clustered_final.json


This file is treated as the single source of truth.

8. Sub-Bin Context Summary

A summary is generated to aid analyst understanding, including:

Event count

Unique senders / receivers

Dominant receiver domain

Average username entropy

PII policy mix

This allows pattern-level reasoning, not event-by-event review.

9. Analyst Labeling Strategy (BIN_001)
Key Principle

Analysts label sub-bins, not individual emails.

Regulatory Assumption

Because BIN_001 involves:

PII

Personal email

No CC / oversight

➡️ All sub-bins under BIN_001 are treated as compliance violations.

10. Final Labels for BIN_001
Labeling Decision (Applies to ALL sub-bins)
Attribute	Value
Severity	CRITICAL
Allowed Behavior	❌ No
Auto-Close Eligible	❌ No
Human Review Required	✅ Yes
Policy Alignment	VIOLATION
Example Label Record
{
  "bin_id": "BIN_001",
  "sub_bin_id": "BIN_001_MAIN",
  "severity": "CRITICAL",
  "allowed_behavior": false,
  "auto_close_eligible": false,
  "confidence": 5,
  "review_required": true,
  "business_justification": "Outbound transmission of PII to personal email without oversight violates regulatory data protection requirements",
  "policy_alignment": "VIOLATION"
}

11. Key Takeaway (Design Rationale)

Machine Learning is used to group and prioritize incidents

Human analysts retain control over policy and severity

Compliance is strengthened, not weakened, by ML

No automation occurs without explicit human approval

12. Current Status

✅ BIN_001 data ingested
✅ Feature engineering completed
✅ Sub-bins discovered and stabilized
✅ Analyst labels created

➡️ Ready to proceed to BIN_002 or automation logic

If you want next, we can:

Extend this README for BIN_002 / BIN_003

Add auto-close enforcement logic

Add retraining and drift handling

Convert this into a final project report

Just tell me what’s next.