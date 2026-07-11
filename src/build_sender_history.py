import json
import os
from collections import defaultdict
import argparse

def process_bin(bin_id):
    bin_id_lower = bin_id.lower()
    BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ENRICHED_PATH = os.path.join(BASE_DIR, "bins", bin_id_lower, f"{bin_id_lower}_enriched.jsonl")
    OUTPUT_PATH   = os.path.join(BASE_DIR, "models", bin_id_lower, "sender_history.json")

    print(f"Building sender history from training data for {bin_id}...")

    if not os.path.exists(ENRICHED_PATH):
        print(f"[ERROR] {ENRICHED_PATH} not found.")
        return

    history = defaultdict(list)

    with open(ENRICHED_PATH, "r") as f:
        for line in f:
            ev = json.loads(line)
            history[ev["sender"]].append({
                "ts":       ev["timestamp"],
                "policy":   ev["dlp_policy"],
                "receiver": ev["receiver"],
            })

    for sender in history:
        history[sender].sort(key=lambda x: x["ts"])

    history_dict = {sender: events for sender, events in history.items()}

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(history_dict, f)

    total_events = sum(len(v) for v in history_dict.values())
    print(f"Saved history for {len(history_dict):,} senders ({total_events:,} events) -> {OUTPUT_PATH}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin", type=str, required=True)
    args = parser.parse_args()
    process_bin(args.bin)
