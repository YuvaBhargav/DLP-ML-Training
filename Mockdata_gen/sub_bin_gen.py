import json
import pandas as pd
import numpy as np
import argparse
import os
import math
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from collections import Counter

def shannon_entropy(s):
    if not isinstance(s, str) or len(s) == 0:
        return 0
    probs = [n / len(s) for n in Counter(s).values()]
    return -sum(p * math.log2(p) for p in probs)

def process_bin(bin_id):
    bin_id_lower = bin_id.lower()
    input_path = f"bins/{bin_id_lower}/{bin_id_lower}.jsonl"
    
    if not os.path.exists(input_path):
        print(f"Error: Could not find {input_path}")
        return

    print(f"--- Processing {bin_id} ---")
    df = pd.read_json(input_path, lines=True)

    # Base feature engineering (common to all)
    df["sender_username"] = df["sender"].str.split("@").str[0]
    df["sender_username_length"] = df["sender_username"].str.len()
    df["sender_username_entropy"] = df["sender_username"].apply(shannon_entropy)
    
    df["receiver_domain"] = df["receiver"].str.split("@").str[1]
    domain_freq = df["receiver_domain"].value_counts(normalize=True)
    df["receiver_domain_frequency"] = df["receiver_domain"].map(domain_freq)

    feature_cols = ["sender_username_length", "sender_username_entropy", "receiver_domain_frequency"]

    if bin_id == "BIN_001":
        # Policy varies
        policy_map = {"PII_PAN": 0, "PII_AADHAAR": 1, "PII_DL": 2}
        df["policy_encoded"] = df["dlp_policy"].map(policy_map).fillna(-1)
        feature_cols.append("policy_encoded")

    elif bin_id == "BIN_002":
        # Policy is always SOURCE_CODE. Let's use CC domain frequency
        df["cc_domain"] = df["cc"].str.split("@").str[1].fillna("none")
        cc_domain_freq = df["cc_domain"].value_counts(normalize=True)
        df["cc_domain_frequency"] = df["cc_domain"].map(cc_domain_freq)
        feature_cols.append("cc_domain_frequency")

    elif bin_id == "BIN_003":
        # Policy is BU_CONTENT_G1 through G9
        df["policy_encoded"] = df["dlp_policy"].str.extract(r'G(\d+)').astype(float).fillna(0)
        feature_cols.append("policy_encoded")

    features = df[feature_cols].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    dbscan = DBSCAN(eps=0.5, min_samples=20, metric="euclidean")
    df["cluster_label"] = dbscan.fit_predict(X_scaled)

    def map_sub_bin(label):
        if label == -1:
            return f"{bin_id}_OUTLIER"
        elif label == 0:
            return f"{bin_id}_MAIN"
        else:
            return f"{bin_id}_EDGE_{label}"

    df["sub_bin_id"] = df["cluster_label"].apply(map_sub_bin)

    sub_bin_counts = df["sub_bin_id"].value_counts()
    rare_edges = sub_bin_counts[
        (sub_bin_counts < 50) &
        (sub_bin_counts.index.str.startswith(f"{bin_id}_EDGE_"))
    ].index.tolist()

    df.loc[df["sub_bin_id"].isin(rare_edges), "sub_bin_id"] = f"{bin_id}_EDGE_RARE"

    print("Sub-bins generated:")
    print(df["sub_bin_id"].value_counts())

    # Save to clustered json (Note: changing to .jsonl to maintain consistency with timestamp output)
    output_path = f"bins/{bin_id_lower}/{bin_id_lower}_clustered_final.json"
    df.to_json(output_path, orient="records", indent=2)
    print(f"Saved -> {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin", type=str, required=True, help="e.g. BIN_001, BIN_002")
    args = parser.parse_args()
    process_bin(args.bin)
