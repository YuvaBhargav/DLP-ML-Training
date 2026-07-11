# -*- coding: utf-8 -*-
"""
gen_test_log.py
Generates a 1000-event realistic test log covering all key scenarios.
Output: test_log.jsonl
"""

import json, random
from datetime import datetime, timedelta

random.seed(99)

POLICIES  = ["PII_PAN", "PII_AADHAAR", "PII_DL"]
DOMAINS   = ["gmail.com", "yahoo.com"]
START     = datetime(2026, 1, 20, 0, 0, 0)

events = []

def make(sender, receiver_domain, policy, ts):
    recv_user = f"ext{random.randint(100,999)}"
    return {
        "sender":     sender,
        "receiver":   f"{recv_user}@{receiver_domain}",
        "dlp_policy": policy,
        "timestamp":  ts.strftime("%Y-%m-%dT%H:%M:%S"),
    }

def biz_ts(base_day=0):
    """Business hours: Mon-Fri, 09-17h"""
    day = START + timedelta(days=base_day)
    while day.weekday() >= 5:
        base_day += 1
        day = START + timedelta(days=base_day)
    return day.replace(hour=random.randint(9,17), minute=random.randint(0,59))

def after_ts(base_day=0):
    """After hours: 20:00-23:59"""
    day = START + timedelta(days=base_day)
    return day.replace(hour=random.randint(20,23), minute=random.randint(0,59))

def midnight_ts(base_day=0):
    """Late night: 00:00-05:00"""
    day = START + timedelta(days=base_day)
    return day.replace(hour=random.randint(0,5), minute=random.randint(0,59))

def weekend_ts(base_day=0):
    """Weekend: find next Sat/Sun"""
    day = START + timedelta(days=base_day)
    while day.weekday() < 5:
        base_day += 1
        day = START + timedelta(days=base_day)
    return day.replace(hour=random.randint(10,18), minute=random.randint(0,59))

# ── Scenario A: 200 new/unknown senders, business hours (MEDIUM/HIGH expected) ──
for i in range(200):
    policy  = random.choice(POLICIES)
    domain  = random.choice(DOMAINS)
    sender  = f"newjoin_{i:03d}@yuva.com"
    events.append(make(sender, domain, policy, biz_ts(random.randint(0, 10))))

# ── Scenario B: 150 events from known HEAVY senders in training data ─────────
# user001 has 436 training events → should often hit CRITICAL
heavy = ["user001@yuva.com", "user002@yuva.com", "user003@yuva.com"]
for i in range(150):
    sender = random.choice(heavy)
    policy = random.choice(POLICIES)
    domain = random.choice(DOMAINS)
    events.append(make(sender, domain, policy, biz_ts(random.randint(0, 7))))

# ── Scenario C: 100 after-hours events (is_after_hours=1) ────────────────────
for i in range(100):
    sender = f"user{random.randint(10, 100):03d}@yuva.com"
    policy = random.choice(POLICIES)
    domain = random.choice(DOMAINS)
    events.append(make(sender, domain, policy, after_ts(random.randint(0, 14))))

# ── Scenario D: 80 late-night / 2am events ───────────────────────────────────
for i in range(80):
    sender = f"user{random.randint(50, 200):03d}@yuva.com"
    policy = random.choice(POLICIES)
    domain = random.choice(DOMAINS)
    events.append(make(sender, domain, policy, midnight_ts(random.randint(0, 14))))

# ── Scenario E: 80 weekend events ────────────────────────────────────────────
for i in range(80):
    sender = f"user{random.randint(20, 150):03d}@yuva.com"
    policy = random.choice(POLICIES)
    domain = random.choice(DOMAINS)
    events.append(make(sender, domain, policy, weekend_ts(random.randint(0, 20))))

# ── Scenario F: 150 rapid succession (same sender, multiple hits same day) ───
rapid_senders = [f"rapid_{i:02d}@yuva.com" for i in range(15)]
for sender in rapid_senders:
    base_day = random.randint(0, 7)
    base_hour = random.randint(9, 16)
    base = (START + timedelta(days=base_day)).replace(hour=base_hour, minute=0)
    for j in range(10):   # 10 events from same sender in same day
        ts = base + timedelta(minutes=j * random.randint(5, 30))
        policy = random.choice(POLICIES)
        domain = random.choice(DOMAINS)
        events.append(make(sender, domain, policy, ts))

# ── Scenario G: 100 PAN-only to Gmail (the MEDIUM exception pattern) ─────────
for i in range(100):
    sender = f"panexcept_{i:03d}@yuva.com"
    events.append(make(sender, "gmail.com", "PII_PAN", biz_ts(random.randint(0, 14))))

# ── Scenario H: 50 escalating repeat policy (same sender, same policy, 3 days)
for i in range(10):
    sender  = f"repeat_{i:02d}@yuva.com"
    policy  = random.choice(POLICIES)
    base_day = random.randint(0, 5)
    for j in range(5):    # 5 events, same policy, spread over 3 days
        ts = biz_ts(base_day + j // 2)
        events.append(make(sender, random.choice(DOMAINS), policy, ts))

# ── Scenario I: 40 cross-policy (same sender, different policies) ─────────────
for i in range(10):
    sender   = f"diverse_{i:02d}@yuva.com"
    base_day = random.randint(0, 10)
    for j, policy in enumerate(POLICIES * 2 + ["PII_PAN"]):
        ts = biz_ts(base_day + j)
        events.append(make(sender, random.choice(DOMAINS), policy, ts))

# ── Sort chronologically ──────────────────────────────────────────────────────
events.sort(key=lambda x: x["timestamp"])

# ── Save ──────────────────────────────────────────────────────────────────────
outpath = "test_log.jsonl"
with open(outpath, "w") as f:
    for ev in events:
        f.write(json.dumps(ev) + "\n")

print(f"Generated {len(events):,} events -> {outpath}")

# Summary
from collections import Counter
policies = Counter(e["dlp_policy"] for e in events)
hours    = Counter("after-hours" if int(e["timestamp"][11:13]) < 8 or int(e["timestamp"][11:13]) >= 18
                   else "business" for e in events)
senders  = Counter(e["sender"] for e in events)

print(f"Policy mix    : {dict(policies)}")
print(f"Hour mix      : {dict(hours)}")
print(f"Unique senders: {len(senders)}")
print(f"Top 5 senders : {senders.most_common(5)}")
