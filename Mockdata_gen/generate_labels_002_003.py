import json
import os

def generate_bin2_labels():
    # BIN_002: Internal -> Business (SOURCE_CODE)
    # Since Source Code is highly sensitive, we assume any sub-bin is HIGH by default.
    # Exception: if CC is present (manager oversight), maybe it's MEDIUM, but our DBScan just finds clusters.
    
    # Just basic logic for simulated labels
    labels = [
        {
            "bin_id": "BIN_002",
            "sub_bin_id": "BIN_002_MAIN",
            "severity": "HIGH",
            "allowed_behavior": False,
            "auto_close_eligible": False,
            "policy_alignment": "VIOLATION"
        },
        {
            "bin_id": "BIN_002",
            "sub_bin_id": "BIN_002_EDGE_1",
            "severity": "CRITICAL",  # maybe this edge cluster has weird cc domains
            "allowed_behavior": False,
            "auto_close_eligible": False,
            "policy_alignment": "VIOLATION"
        },
        {
            "bin_id": "BIN_002",
            "severity": "HIGH",  # fallback
            "policy_alignment": "VIOLATION"
        }
    ]
    with open("bins/bin_002/bin_002_labels.json", "w") as f:
        json.dump(labels, f, indent=2)

def generate_bin3_labels():
    # BIN_003: FTC -> Personal (BU_CONTENT)
    # Contractors sending BU content to personal emails is very suspicious. Default CRITICAL.
    labels = [
        {
            "bin_id": "BIN_003",
            "sub_bin_id": "BIN_003_MAIN",
            "severity": "CRITICAL",
            "allowed_behavior": False,
            "auto_close_eligible": False,
            "policy_alignment": "VIOLATION"
        },
        {
            "bin_id": "BIN_003",
            "severity": "CRITICAL", # fallback
            "policy_alignment": "VIOLATION"
        }
    ]
    with open("bins/bin_003/bin_003_labels.json", "w") as f:
        json.dump(labels, f, indent=2)

if __name__ == "__main__":
    os.makedirs("bins/bin_002", exist_ok=True)
    os.makedirs("bins/bin_003", exist_ok=True)
    generate_bin2_labels()
    generate_bin3_labels()
    print("Generated bin_002_labels.json and bin_003_labels.json")
