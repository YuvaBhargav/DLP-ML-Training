# Email DLP – ML-Assisted Incident Classification (BIN_001)

## 1. Project Overview

This project implements a Machine Learning–assisted, human-in-the-loop classification system for **Email Data Loss Prevention (DLP)** incidents, designed for **regulated environments** such as banking and financial services.

The objectives of this phase are:
- Identify behavioral patterns in email DLP incidents
- Group similar incidents into bins and sub-bins
- Enable analyst-driven labeling at a pattern level
- Prepare the foundation for future automation and retraining

**Current Scope**
- Channel: Email only  
- Data source: Netskope-style email DLP logs  
- Coverage: BIN_001 (PII → Personal Email → No CC)  

---

## 2. High-Level Architecture (Current Phase)

Email DLP Logs (JSONL)
|
v
Feature Engineering
|
v
Hard Bin Assignment (BIN_001)
|
v
DBSCAN Clustering (Sub-bins)
|
v
Rare Cluster Merging
|
v
Analyst Review & Labeling


No auto-close or automated enforcement is enabled in this phase.

---

## 3. BIN_001 Definition

**BIN_001** represents outbound email incidents where:

- Sender is an internal Full-Time Employee (FTE)
- Recipient is a personal email domain (Gmail, Yahoo, etc.)
- No CC recipients are present
- Email content triggers PII-related DLP policies

### PII Types Covered
- PAN
- Aadhaar
- Driving License

### Regulatory Context

In regulated entities, this behavior is considered a **critical compliance risk** due to:
- Transmission of regulated PII to uncontrolled destinations
- Absence of managerial or organizational oversight
- Violation of internal and regulatory data protection policies

---

## 4. Input Data Format

Input data is stored in **JSON Lines (.jsonl)** format, one event per line.

Example:
```json
{"sender":"user@corp.com","receiver":"user@gmail.com","dlp_policy":"PII_PAN"}

Input file: bins/bin_001/bin_001.jsonl

5. Feature Engineering

The following behavioral features are derived for clustering:
| Feature                   | Description                              |
| ------------------------- | ---------------------------------------- |
| sender_username_length    | Length of sender username                |
| sender_username_entropy   | Shannon entropy of username              |
| receiver_domain_frequency | Normalized frequency of receiver domain  |
| policy_encoded            | Encoded PII subtype (PAN / Aadhaar / DL) |

These features describe behavioral variation, not risk or severity.


6. Clustering Approach

Algorithm

DBSCAN (Density-Based Spatial Clustering)

Rationale

No need to predefine number of clusters

Naturally detects outliers

Well-suited for noisy security data
Parameters
   eps = 0.5
   min_samples = 20

Output

Each event is assigned a sub_bin_id:
BIN_001_MAIN
BIN_001_EDGE_n
BIN_001_OUTLIER

7. Rare Edge Cluster Merging

Clusters with fewer than 50 events are considered unstable and merged into: BIN_001_EDGE_RARE

Final Sub-Bins:

| Sub-Bin           | Description                   |
| ----------------- | ----------------------------- |
| BIN_001_MAIN      | Most common, stable behavior  |
| BIN_001_EDGE_1–5  | Stable behavioral variants    |
| BIN_001_EDGE_RARE | Rare but repeatable patterns  |
| BIN_001_OUTLIER   | Unknown or anomalous behavior |

Final output file:bins/bin_001/bin_001_clustered_final.json

8. Sub-Bin Context Summary

For analyst context, each sub-bin is summarized using:

Event count
Unique senders and receivers
Dominant receiver domain
Average sender username entropy
PII policy mix
This enables pattern-level review instead of event-level analysis.

9. Analyst Labeling Strategy
Core Principle

Analysts label sub-bins, not individual email events.

Regulatory Assumption
Because BIN_001 involves:
Regulated PII
Personal email destinations
No CC or oversight
All sub-bins under BIN_001 are treated as policy violations.


10. Final Labels for BIN_001
The following labels apply to all sub-bins in BIN_001:
| Attribute             | Value     |
| --------------------- | --------- |
| Severity              | CRITICAL  |
| Allowed Behavior      | No        |
| Auto-Close Eligible   | No        |
| Human Review Required | Yes       |
| Policy Alignment      | VIOLATION |

Example Label Record:
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

11. Key Design Takeaways

Machine Learning is used for pattern discovery, not policy decisions
Human analysts retain authority over severity and compliance
ML strengthens regulatory enforcement through consistency
No automation occurs without explicit human approval

12. Current Status

BIN_001 data ingested
Feature engineering completed
Sub-bins discovered and stabilized
Analyst labels created
System is now ready to extend to BIN_002 or automation logic.

