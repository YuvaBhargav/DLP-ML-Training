# -*- coding: utf-8 -*-
"""
gen_10k_mixed_log.py
Generates a 10,000-event realistic mixed test log spanning BIN_001, BIN_002, and BIN_003.
Output: test_10k_mixed.jsonl
"""

import json, random
from datetime import datetime, timedelta

random.seed(42)

START = datetime(2026, 1, 20, 0, 0, 0)

# Definitions for BIN_001
B1_POLICIES = ["PII_PAN", "PII_AADHAAR", "PII_DL"]
B1_DOMAINS  = ["gmail.com", "yahoo.com"]

# Definitions for BIN_002
B2_POLICIES = ["SOURCE_CODE"]
B2_DOMAINS  = ["partner.com", "vendor.com"]
B2_CC_DOMAINS = ["yuva.com", "none"]

# Definitions for BIN_003
B3_POLICIES = [f"BU_CONTENT_G{i}" for i in range(1, 10)]
B3_DOMAINS  = ["gmail.com", "yahoo.com"]

events = []

def biz_ts(base_day=0):
    day = START + timedelta(days=base_day)
    while day.weekday() >= 5:
        base_day += 1
        day = START + timedelta(days=base_day)
    return day.replace(hour=random.randint(9,17), minute=random.randint(0,59))

def after_ts(base_day=0):
    day = START + timedelta(days=base_day)
    return day.replace(hour=random.randint(20,23), minute=random.randint(0,59))

def weekend_ts(base_day=0):
    day = START + timedelta(days=base_day)
    while day.weekday() < 5:
        base_day += 1
        day = START + timedelta(days=base_day)
    return day.replace(hour=random.randint(10,18), minute=random.randint(0,59))

def get_time(is_weekend=False, is_after=False, base_day_range=30):
    d = random.randint(0, base_day_range)
    if is_weekend: return weekend_ts(d)
    if is_after: return after_ts(d)
    return biz_ts(d)

# We want 10,000 events total.
# Let's distribute them: 50% BIN_001, 30% BIN_002, 20% BIN_003
counts = {"BIN_001": 5000, "BIN_002": 3000, "BIN_003": 2000}

# Generate BIN_001
for i in range(counts["BIN_001"]):
    sender = f"user{random.randint(1, 300):03d}@yuva.com"
    recv_user = f"ext{random.randint(100,999)}"
    domain = random.choice(B1_DOMAINS)
    policy = random.choice(B1_POLICIES)
    ts = get_time(is_weekend=random.random()<0.1, is_after=random.random()<0.15)
    
    events.append({
        "bin_id": "BIN_001",
        "sender": sender,
        "receiver": f"{recv_user}@{domain}",
        "dlp_policy": policy,
        "timestamp": ts.isoformat()
    })

# Generate BIN_002
for i in range(counts["BIN_002"]):
    sender = f"dev{random.randint(1, 150):03d}@yuva.com"
    recv_user = f"partner{random.randint(10,99)}"
    domain = random.choice(B2_DOMAINS)
    policy = "SOURCE_CODE"
    cc_domain = random.choice(B2_CC_DOMAINS)
    cc = f"mgr{random.randint(1,10)}@{cc_domain}" if cc_domain != "none" else ""
    ts = get_time(is_weekend=random.random()<0.05, is_after=random.random()<0.2)
    
    events.append({
        "bin_id": "BIN_002",
        "sender": sender,
        "receiver": f"{recv_user}@{domain}",
        "cc": cc,
        "dlp_policy": policy,
        "timestamp": ts.isoformat()
    })

# Generate BIN_003
for i in range(counts["BIN_003"]):
    sender = f"contractor{random.randint(1, 100):03d}@yuvaext.com"
    recv_user = f"personal{random.randint(100,999)}"
    domain = random.choice(B3_DOMAINS)
    policy = random.choice(B3_POLICIES)
    ts = get_time(is_weekend=random.random()<0.2, is_after=random.random()<0.2)
    
    events.append({
        "bin_id": "BIN_003",
        "sender": sender,
        "receiver": f"{recv_user}@{domain}",
        "dlp_policy": policy,
        "timestamp": ts.isoformat()
    })

# Sort chronologically
events.sort(key=lambda x: x["timestamp"])

# Save
outpath = "test_10k_mixed.jsonl"
with open(outpath, "w") as f:
    for ev in events:
        f.write(json.dumps(ev) + "\n")

print(f"Generated {len(events):,} mixed events -> {outpath}")
