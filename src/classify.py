import os
import sys
import json
import math
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR    = os.path.join(BASE_DIR, "models")

# ─── Dummy Model for Single-Class Bins ─────────────────────────────────────────
class DummyModel:
    def __init__(self, label_idx):
        self.label_idx = label_idx
    def predict(self, X):
        return np.full(X.shape[0], self.label_idx)
    def predict_proba(self, X):
        res = np.zeros((X.shape[0], 1))
        res[:, 0] = 1.0
        return res

# ─── Cache models ──────────────────────────────────────────────────────────────
loaded_models = {}

def load_bin_models(bin_id):
    bin_id_lower = bin_id.lower()
    if bin_id_lower in loaded_models:
        return loaded_models[bin_id_lower]

    bin_dir = os.path.join(MODELS_DIR, bin_id_lower)
    model_path   = os.path.join(bin_dir, "severity_model.joblib")
    scaler_path  = os.path.join(bin_dir, "scaler.joblib")
    le_path      = os.path.join(bin_dir, "label_encoder.joblib")
    feat_path    = os.path.join(bin_dir, "feature_list.json")
    history_path = os.path.join(bin_dir, "sender_history.json")

    for path, label in [(model_path, "model"), (scaler_path, "scaler"),
                        (le_path, "encoder"), (feat_path, "feature list"),
                        (history_path, "sender history")]:
        if not os.path.exists(path):
            print(f"[ERROR] Missing {label} for {bin_id}: {path}")
            sys.exit(1)

    model  = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    le     = joblib.load(le_path)
    with open(feat_path)    as f: feature_cols  = json.load(f)
    with open(history_path) as f: raw_history   = json.load(f)

    # Convert timestamps
    history = {}
    for sender, evts in raw_history.items():
        history[sender] = [
            {"ts": datetime.fromisoformat(e["ts"]),
             "policy": e["policy"], "receiver": e["receiver"]}
            for e in evts
        ]
        
    loaded_models[bin_id_lower] = (model, scaler, le, feature_cols, history)
    return loaded_models[bin_id_lower]

# ─── Feature engineering helpers ──────────────────────────────────────────────
def shannon_entropy(s: str) -> float:
    if not s: return 0.0
    probs = [n / len(s) for n in Counter(s).values()]
    return -sum(p * math.log2(p) for p in probs)

def compute_features(ev: dict, prior: list, feature_cols: list) -> dict:
    sender   = ev.get("sender", "")
    receiver = ev.get("receiver", "")
    policy   = ev.get("dlp_policy", "PII_PAN").upper()
    ts_raw   = ev.get("timestamp", datetime.now(timezone.utc).isoformat())
    ts       = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else ts_raw
    bin_id   = ev.get("bin_id", "BIN_001")

    # Base features
    username    = sender.split("@")[0]
    recv_domain = receiver.split("@")[1].lower() if "@" in receiver else receiver.lower()

    feat = {
        "sender_username_length":    len(username),
        "sender_username_entropy":   round(shannon_entropy(username), 4),
    }

    # Conditional Original Features based on what's in feature_cols
    if "receiver_domain_frequency" in feature_cols:
        DOMAIN_FREQ = {"gmail.com": 0.50, "yahoo.com": 0.50}
        feat["receiver_domain_frequency"] = DOMAIN_FREQ.get(recv_domain, 0.01)

    if "policy_encoded" in feature_cols:
        if bin_id == "BIN_001":
            POLICY_MAP = {"PII_PAN": 0, "PII_AADHAAR": 1, "PII_DL": 2}
            feat["policy_encoded"] = POLICY_MAP.get(policy, 0)
        elif bin_id == "BIN_003":
            import re
            m = re.search(r'G(\d+)', policy)
            feat["policy_encoded"] = float(m.group(1)) if m else 0.0

    if "cc_domain_frequency" in feature_cols:
        cc = ev.get("cc", "")
        cc_domain = cc.split("@")[1].lower() if "@" in cc else "none"
        CC_FREQ = {"yuva.com": 0.8, "none": 0.2}
        feat["cc_domain_frequency"] = CC_FREQ.get(cc_domain, 0.01)

    # Behavioral features
    cutoff_30d = ts - timedelta(days=30)
    cutoff_7d  = ts - timedelta(days=7)
    prior_30d  = [h for h in prior if h["ts"] >= cutoff_30d]
    prior_7d   = [h for h in prior if h["ts"] >= cutoff_7d]

    prior_policies  = {h["policy"] for h in prior}
    prior_receivers = {h["receiver"] for h in prior}

    today_str    = ts.date().isoformat()
    daily_counts = Counter(h["ts"].date().isoformat() for h in prior_30d)
    today_count  = daily_counts.get(today_str, 0) + 1
    if len(daily_counts) >= 3:
        vals  = list(daily_counts.values())
        mu, std = np.mean(vals), np.std(vals)
        zscore = float((today_count - mu) / (std + 1e-6))
    else:
        zscore = 0.0

    days_since = 999.0
    if prior:
        last_ts    = max(h["ts"] for h in prior)
        days_since = (ts - last_ts).total_seconds() / 86400.0

    # New Production Base Features
    is_ftc = 1 if ev.get("sender_type", "FTE") == "FTC" else 0
    is_encrypted_payload = 1 if ev.get("is_encrypted", False) else 0
    is_personal_recipient = 1 if ev.get("receiver_domain_type", "PERSONAL") == "PERSONAL" else 0
    
    cc_raw = ev.get("cc", "")
    cc_list = [c.strip() for c in cc_raw.split(",") if c.strip()]
    internal_ccs = [c for c in cc_list if "yuva.com" in c]
    internal_cc_count = len(internal_ccs)
    has_manager_cc = 1 if any("manager" in c for c in internal_ccs) else 0
    
    context_confidence = float(ev.get("context_confidence", 1.0))
    is_false_positive_regex = 1 if context_confidence < 0.5 else 0

    beh = {
        "sender_30d_violation_count": len(prior_30d),
        "sender_7d_violation_count":  len(prior_7d),
        "sender_policy_repeat":        1 if policy in prior_policies else 0,
        "sender_new_receiver":         0 if receiver in prior_receivers else 1,
        "sender_daily_volume_zscore":  round(zscore, 4),
        "sender_policy_diversity":     len(prior_policies),
        "days_since_last_violation":   round(min(days_since, 999.0), 2),
        "hour_of_day":                 ts.hour,
        "is_weekend":                  1 if ts.weekday() >= 5 else 0,
        "is_after_hours":              1 if (ts.hour < 8 or ts.hour >= 18) else 0,
        "is_ftc": is_ftc,
        "is_encrypted_payload": is_encrypted_payload,
        "is_personal_recipient": is_personal_recipient,
        "internal_cc_count": internal_cc_count,
        "has_manager_cc": has_manager_cc,
        "is_false_positive_regex": is_false_positive_regex,
        "context_confidence": round(context_confidence, 2)
    }
    
    # Only include behavioral features that the model actually expects
    for col in feature_cols:
        if col in beh:
            feat[col] = beh[col]

    return feat

# ─── Main classify function ────────────────────────────────────────────────────
def classify_batch(input_path: str, output_path: str | None = None):
    if not os.path.exists(input_path):
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r") as f:
        new_events = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(new_events):,} events from {input_path}")
    new_events.sort(key=lambda x: x.get("timestamp", ""))

    # We need batch history per bin and per sender
    batch_history = defaultdict(lambda: defaultdict(list))

    results = []
    for ev in new_events:
        bin_id  = ev.get("bin_id", "BIN_001")
        sender  = ev.get("sender", "")
        policy  = ev.get("dlp_policy", "PII_PAN").upper()
        receiver = ev.get("receiver", "")
        ts_raw  = ev.get("timestamp", datetime.now(timezone.utc).isoformat())
        ts      = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else ts_raw

        model, scaler, le, feature_cols, history = load_bin_models(bin_id)

        combined_prior = (history.get(sender, []) + batch_history[bin_id][sender])

        feats = compute_features(ev, combined_prior, feature_cols)

        X_raw = pd.DataFrame([feats], columns=feature_cols)
        X_sc  = scaler.transform(X_raw)

        # Handle dummy model for single-class bins
        if hasattr(model, "label_idx"):
            label_idx = model.label_idx
            proba = model.predict_proba(X_sc)[0]
        else:
            label_idx  = model.predict(X_sc)[0]
            proba      = model.predict_proba(X_sc)[0]
            
        severity   = le.inverse_transform([label_idx])[0]
        confidence = round(proba[0] * 100, 1) if hasattr(model, "label_idx") else round(proba[label_idx] * 100, 1)

        if severity == "CRITICAL": action = "ESCALATE_IMMEDIATELY"
        elif severity == "HIGH": action = "HUMAN_REVIEW_REQUIRED"
        else: action = "LOG_AND_MONITOR"

        result = {**ev,
                  "predicted_severity": severity,
                  "confidence_pct":     confidence,
                  "recommended_action": action,
                  "behavioral_context": {
                      "sender_30d_violations":   feats.get("sender_30d_violation_count", 0),
                      "sender_7d_violations":    feats.get("sender_7d_violation_count", 0),
                      "is_repeat_policy":        bool(feats.get("sender_policy_repeat", 0)),
                      "is_new_receiver":         bool(feats.get("sender_new_receiver", 0)),
                      "is_after_hours":          bool(feats.get("is_after_hours", 0)),
                      "is_weekend":              bool(feats.get("is_weekend", 0)),
                      "days_since_last_violation": feats.get("days_since_last_violation", 999.0),
                  }}
        results.append(result)

        batch_history[bin_id][sender].append({
            "ts": ts, "policy": policy, "receiver": receiver
        })

    if output_path:
        with open(output_path, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
        print(f"Classified {len(results):,} events -> {output_path}")
    else:
        print(f"\n{'#':<5} {'BIN':<9} {'SENDER':<25} {'POLICY':<14} {'SEVERITY':<10} {'CONF%':<8} {'ACTION'}")
        print("-" * 100)
        for i, r in enumerate(results, 1):
            print(f"{i:<5} {r.get('bin_id',''):<9} {r.get('sender',''):<25} {r.get('dlp_policy',''):<14} "
                  f"{r['predicted_severity']:<10} {r['confidence_pct']:<8} "
                  f"{r['recommended_action']}")

    from collections import Counter as C
    sev_dist = C(r["predicted_severity"] for r in results)
    print(f"\nSummary:")
    for sev in ["CRITICAL", "HIGH", "MEDIUM"]:
        if sev in sev_dist:
            print(f"  {sev:<10}: {sev_dist[sev]:>5} events")

    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: venv/Scripts/python src/classify.py <input.jsonl> [output.jsonl]")
        sys.exit(0)

    input_file  = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    classify_batch(input_file, output_file)
