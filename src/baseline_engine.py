import os
import json
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, Counter

def process_bin(bin_id):
    bin_id_lower = bin_id.lower()
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LABELS_PATH = os.path.join(BASE_DIR, "bins", bin_id_lower, f"{bin_id_lower}_labels.json")
    INPUT_PATH  = os.path.join(BASE_DIR, "bins", bin_id_lower, f"{bin_id_lower}_timestamped.jsonl")
    OUTPUT_PATH = os.path.join(BASE_DIR, "bins", bin_id_lower, f"{bin_id_lower}_enriched.jsonl")

    print(f"--- Baseline Engine: {bin_id} ---")

    print("[1/4] Loading analyst labels...")
    with open(LABELS_PATH, "r") as f:
        labels_raw = json.load(f)
    
    sub_bin_map = {}
    default_label = "HIGH"
    for l in labels_raw:
        if "sub_bin_id" in l:
            sub_bin_map[l["sub_bin_id"]] = l["severity"]
        else:
            default_label = l["severity"]

    print("[2/4] Loading timestamped events...")
    events = []
    with open(INPUT_PATH, "r") as f:
        for line in f:
            events.append(json.loads(line))
    print(f"      Loaded {len(events):,} events (already sorted chronologically)")

    print("[3/4] Computing behavioral features...")
    sender_history = defaultdict(list)
    results = []

    for i, ev in enumerate(events):
        sender = ev["sender"]
        ts = datetime.fromisoformat(ev["timestamp"])
        policy = ev["dlp_policy"]
        receiver = ev["receiver"]
        
        prior_events = sender_history[sender]
        
        # Windows
        cutoff_30d = ts - timedelta(days=30)
        cutoff_7d  = ts - timedelta(days=7)
        prior_30d  = [h for h in prior_events if h["ts"] >= cutoff_30d]
        prior_7d   = [h for h in prior_events if h["ts"] >= cutoff_7d]
        
        # Sets
        prior_policies = {h["policy"] for h in prior_events}
        prior_receivers = {h["receiver"] for h in prior_events}
        
        # Z-score of daily volume
        today = ts.date()
        daily_counts = Counter(h["ts"].date() for h in prior_30d)
        today_count = daily_counts.get(today, 0) + 1
        
        if len(daily_counts) >= 3:
            vals = list(daily_counts.values())
            mu = np.mean(vals)
            std = np.std(vals)
            zscore = (today_count - mu) / (std + 1e-6)
        else:
            zscore = 0.0
            
        # Days since last
        if prior_events:
            last_ts = max(h["ts"] for h in prior_events)
            days_since = (ts - last_ts).total_seconds() / 86400
        else:
            days_since = 999.0
            
        # Time features
        hour = ts.hour
        is_weekend = 1 if ts.weekday() >= 5 else 0
        is_after_hours = 1 if (hour < 8 or hour >= 18) else 0

        # Netskope Feature
        violation_count = int(ev.get("violation_count", 1))

        # New Production Base Features
        is_ftc = 1 if "@yuvaext" in sender.lower() else 0
        is_encrypted_payload = 1 if policy.upper() == "ENCRYPTED" else 0
        is_personal_recipient = 1 if ev.get("receiver_domain_type", "PERSONAL") == "PERSONAL" else 0
        
        cc_raw = ev.get("cc", "")
        cc_list = [c.strip() for c in cc_raw.split(",") if c.strip()]
        internal_ccs = [c for c in cc_list if "yuva.com" in c]
        internal_cc_count = len(internal_ccs)
        has_manager_cc = 1 if any("manager" in c for c in internal_ccs) else 0
        
        context_confidence = float(ev.get("context_confidence", 1.0))
        is_false_positive_regex = 1 if context_confidence < 0.5 else 0

        # Create behavioral dict
        beh = {
            "sender_30d_violation_count": len(prior_30d),
            "sender_7d_violation_count": len(prior_7d),
            "sender_policy_repeat": 1 if policy in prior_policies else 0,
            "sender_new_receiver": 0 if receiver in prior_receivers else 1,
            "sender_daily_volume_zscore": round(float(zscore), 4),
            "sender_policy_diversity": len(prior_policies),
            "days_since_last_violation": round(min(days_since, 999.0), 2),
            "hour_of_day": hour,
            "is_weekend": is_weekend,
            "is_after_hours": is_after_hours,
            "violation_count": violation_count,
            "is_ftc": is_ftc,
            "is_encrypted_payload": is_encrypted_payload,
            "is_personal_recipient": is_personal_recipient,
            "internal_cc_count": internal_cc_count,
            "has_manager_cc": has_manager_cc,
            "is_false_positive_regex": is_false_positive_regex,
            "context_confidence": round(context_confidence, 2)
        }
        
        ev.update(beh)
        
        # Ground Truth Labeling based on Production Scenarios
        # Default fallback
        sub_bin_id = ev.get("sub_bin_id")
        sev = sub_bin_map.get(sub_bin_id, default_label)
        
        # Scenario 1: False Positive Content Validation
        if is_false_positive_regex:
            sev = "MEDIUM" # (Low/No alert)
        else:
            # Scenario 4: Encrypted payload -> CRITICAL
            if is_encrypted_payload:
                sev = "CRITICAL"
            else:
                # Scenario 3: >= 2 internal persons in CC -> MEDIUM
                if internal_cc_count >= 2:
                    sev = "MEDIUM"
                    
                # Sender Scenario: FTC sending externally -> CRITICAL
                if is_ftc and is_personal_recipient:
                    sev = "CRITICAL"
                    
                # Receiver Scenarios
                if not is_personal_recipient:
                    # Scenario 2: Vendor/Business domain -> LOW/MEDIUM (not raised)
                    if has_manager_cc:
                        sev = "MEDIUM"
                    elif sev == "CRITICAL":
                        sev = "HIGH"
                else:
                    # Scenario 1: Personal domain -> HIGH
                    if sev == "MEDIUM":
                        sev = "HIGH"
                
        # Existing Behavioral Escalations (Volume spikes overrule standard rules)
        if sev == "HIGH":
            if beh["sender_30d_violation_count"] >= 15:
                sev = "CRITICAL"
            elif beh["sender_7d_violation_count"] >= 7:
                sev = "CRITICAL"
                
        ev["severity"] = sev
        
        # Record into history
        sender_history[sender].append({"ts": ts, "policy": policy, "receiver": receiver})
        results.append(ev)
        
        if (i + 1) % 2000 == 0:
            print(f"      {i + 1:,}/{len(events):,} events processed...")

    print("[4/4] Saving enriched events...")
    with open(OUTPUT_PATH, "w") as f:
        for ev in results:
            f.write(json.dumps(ev) + "\n")

    print(f"\nDone: {len(results):,} events -> {OUTPUT_PATH}")

    df = pd.DataFrame(results)
    print("\nSeverity distribution (behavioral-adjusted):")
    print(df["severity"].value_counts().to_string())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin", type=str, required=True)
    args = parser.parse_args()
    process_bin(args.bin)
