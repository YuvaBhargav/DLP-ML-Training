import json
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from collections import Counter
import math

# -----------------------------
# 1. Load BIN_001 JSON
# -----------------------------
df = pd.read_json("bin_001_clustered.json",)

# -----------------------------
# 2. Feature Engineering
# -----------------------------

# Sender username
df["sender_username"] = df["sender"].str.split("@").str[0]

# Sender username length
df["sender_username_length"] = df["sender_username"].str.len()

# Shannon entropy of sender username
def shannon_entropy(s):
    if not isinstance(s, str) or len(s) == 0:
        return 0
    probs = [n / len(s) for n in Counter(s).values()]
    return -sum(p * math.log2(p) for p in probs)

df["sender_username_entropy"] = df["sender_username"].apply(shannon_entropy)

# Receiver domain
df["receiver_domain"] = df["receiver"].str.split("@").str[1]

# Receiver domain frequency (normalized)
domain_freq = df["receiver_domain"].value_counts(normalize=True)
df["receiver_domain_frequency"] = df["receiver_domain"].map(domain_freq)

# Policy subtype encoding
policy_map = {
    "PII_PAN": 0,
    "PII_AADHAAR": 1,
    "PII_DL": 2
}
df["policy_encoded"] = df["dlp_policy"].map(policy_map)

# -----------------------------
# 3. Final Feature Matrix
# -----------------------------
features = df[
    [
        "sender_username_length",
        "sender_username_entropy",
        "receiver_domain_frequency",
        "policy_encoded"
    ]
].fillna(0)

# -----------------------------
# 4. Scale Features
# -----------------------------
scaler = StandardScaler()
X_scaled = scaler.fit_transform(features)

# -----------------------------
# 5. Run DBSCAN
# -----------------------------
dbscan = DBSCAN(
    eps=0.5,
    min_samples=20,
    metric="euclidean"
)

df["cluster_label"] = dbscan.fit_predict(X_scaled)

# -----------------------------
# 6. Map clusters → sub-bins
# -----------------------------
def map_sub_bin(label):
    if label == -1:
        return "BIN_001_OUTLIER"
    elif label == 0:
        return "BIN_001_MAIN"
    else:
        return f"BIN_001_EDGE_{label}"

df["sub_bin_id"] = df["cluster_label"].apply(map_sub_bin)

# -----------------------------
# 7. Save output
# -----------------------------
df.to_json("bin_001_clustered.json", orient="records", indent=2)

# -----------------------------
# 8. Quick sanity check
# -----------------------------
print(df["sub_bin_id"].value_counts())

# -----------------------------
# Merge rare EDGE clusters
# -----------------------------

sub_bin_counts = df["sub_bin_id"].value_counts()

rare_edges = sub_bin_counts[
    (sub_bin_counts < 50) &
    (sub_bin_counts.index.str.startswith("BIN_001_EDGE_"))
].index.tolist()

df.loc[df["sub_bin_id"].isin(rare_edges), "sub_bin_id"] = "BIN_001_EDGE_RARE"

print("After merging rare edges:")
print(df["sub_bin_id"].value_counts())

# Save final version
df.to_json("bins/bin_001_clustered_final.json", orient="records", indent=2)

