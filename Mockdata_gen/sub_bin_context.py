import pandas as pd

df = pd.read_json("bins/bin_001/bin_001_clustered_final.json")

summary = (
    df.groupby("sub_bin_id")
    .agg(
        event_count=("sender", "count"),
        unique_senders=("sender", "nunique"),
        unique_receivers=("receiver", "nunique"),
        top_receiver_domain=("receiver_domain", lambda x: x.value_counts().idxmax()),
        avg_username_entropy=("sender_username_entropy", "mean"),
        policy_mix=("dlp_policy", lambda x: list(x.value_counts().index))
    )
    .reset_index()
)

print(summary)
summary.to_csv("bins/bin_001/bin_001_subbin_summary.csv", index=False)
