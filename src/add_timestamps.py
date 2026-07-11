import os
import json
import random
import argparse
import numpy as np
from datetime import datetime, timedelta

def process_bin(bin_id):
    bin_id_lower = bin_id.lower()
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    INPUT_PATH = os.path.join(BASE_DIR, "bins", bin_id_lower, f"{bin_id_lower}_clustered_final.json")
    OUTPUT_PATH = os.path.join(BASE_DIR, "bins", bin_id_lower, f"{bin_id_lower}_timestamped.jsonl")

    print(f"--- Adding timestamps to {bin_id} ---")
    
    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] {INPUT_PATH} not found.")
        return

    print(f"[1/3] Loading clustered data from {INPUT_PATH}...")
    with open(INPUT_PATH, "r") as f:
        events = json.load(f)
    print(f"      Loaded {len(events):,} events")

    print("[2/3] Assigning senders and timestamps...")
    # Sender pool (300 senders) - we map original synthetic senders to a finite pool to create repeats
    NUM_SENDERS = 300
    
    # Prefix based on bin to ensure distinct sender pool if desired, but we can reuse users 
    # to simulate a user offending across bins. Let's use user001..user300
    senders = [f"user{i:03d}@yuva.com" for i in range(1, NUM_SENDERS + 1)]

    # Generate a Pareto distribution for event counts per sender (heavy-tailed)
    weights = np.random.pareto(1.2, NUM_SENDERS) + 1.0
    weights /= weights.sum()

    # Assign new senders
    assigned_senders = np.random.choice(senders, size=len(events), p=weights)

    # 90-day time window
    START_DATE = datetime(2025, 10, 1)
    END_DATE = datetime(2025, 12, 31)
    TOTAL_DAYS = (END_DATE - START_DATE).days

    for i, ev in enumerate(events):
        ev["sender"] = assigned_senders[i]
        
        # Temporal distribution
        day_offset = random.randint(0, TOTAL_DAYS)
        base_date = START_DATE + timedelta(days=day_offset)
        
        time_slot = random.random()
        if time_slot < 0.65:
            # Business hours: 08:00 - 18:00
            hour = random.randint(8, 17)
        elif time_slot < 0.80:
            # Evening: 18:00 - 23:00
            hour = random.randint(18, 22)
        elif time_slot < 0.90:
            # Late night: 00:00 - 06:00
            hour = random.randint(0, 5)
        else:
            # Weekend
            while base_date.weekday() < 5:
                base_date += timedelta(days=1)
            hour = random.randint(8, 22)

        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        final_time = base_date.replace(hour=hour, minute=minute, second=second)
        
        ev["timestamp"] = final_time.isoformat()

    # Sort chronologically
    events.sort(key=lambda x: x["timestamp"])

    print(f"[3/3] Saving...")
    with open(OUTPUT_PATH, "w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    print(f"\nDone: {len(events):,} events -> {OUTPUT_PATH}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin", type=str, required=True, help="e.g. BIN_001, BIN_002")
    args = parser.parse_args()
    process_bin(args.bin)
