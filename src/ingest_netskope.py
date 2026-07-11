import os
import csv
import json
from datetime import datetime

def ingest_netskope_csv(csv_path="netskope_sample.csv"):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    # Prepare outputs per bin
    bin_files = {
        "BIN_001": open("bins/bin_001/bin_001_timestamped.jsonl", "w"),
        "BIN_002": open("bins/bin_002/bin_002_timestamped.jsonl", "w"),
        "BIN_003": open("bins/bin_003/bin_003_timestamped.jsonl", "w")
    }
    
    bin_labels = {
        "BIN_001": {},
        "BIN_002": {},
        "BIN_003": {}
    }

    # Status to Severity mapping
    status_map = {
        "FalsePositive": "MEDIUM",
        "businessrequirement": "MEDIUM",
        "low_priority": "MEDIUM",
        "pending review": "HIGH",
        "Critical_Escalation": "CRITICAL"
    }

    count = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            incident_id = row["Incident Id"]
            policy = row["DLP Policy"]
            
            # Route to bin
            p = policy.upper()
            if p == "SOURCECODE":
                bin_id = "BIN_002"
            elif p.startswith("BU"):
                bin_id = "BIN_003"
            else:
                bin_id = "BIN_001" # aadhaar, DL, ENCRYPTED
                
            # Build event
            dt = datetime.fromtimestamp(float(row["Timestamp"]))
            ev = {
                "incident_id": incident_id,
                "timestamp": dt.isoformat(),
                "sender": row["Acting User"],
                "receiver": row["Receiver"],
                "dlp_policy": policy,
                "cc": row.get("Cc", ""),
                "violation_count": int(row.get("# Violations", 1))
            }
            
            # Map Analyst Label
            status = row.get("Status", "pending review")
            severity = status_map.get(status, "HIGH")
            
            # Save
            bin_files[bin_id].write(json.dumps(ev) + "\n")
            bin_labels[bin_id][incident_id] = severity
            count += 1

    # Close and save labels
    for b_id, f in bin_files.items():
        f.close()
        
    for b_id, labels in bin_labels.items():
        with open(f"bins/{b_id.lower()}/analyst_labels.json", "w") as f:
            json.dump(labels, f, indent=2)
            
    print(f"Successfully ingested {count} Netskope logs into the 3 bins.")

if __name__ == "__main__":
    ingest_netskope_csv()
