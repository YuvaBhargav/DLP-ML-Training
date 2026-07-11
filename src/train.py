# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
train.py (Phase 2 - Multi-Bin Behavioral Baseline)
Trains a severity classifier using behaviorally-enriched data per bin.
"""

import os
import json
import joblib
import argparse
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

class DummyModel:
    def __init__(self, label_idx):
        self.label_idx = label_idx
    def predict(self, X):
        return np.full(X.shape[0], self.label_idx)
    def predict_proba(self, X):
        res = np.zeros((X.shape[0], 1))
        res[:, 0] = 1.0
        return res

def process_bin(bin_id):
    bin_id_lower = bin_id.lower()
    BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ENRICHED_PATH  = os.path.join(BASE_DIR, "bins", bin_id_lower, f"{bin_id_lower}_enriched.jsonl")
    MODELS_DIR     = os.path.join(BASE_DIR, "models", bin_id_lower)
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("=" * 62)
    print(f"  {bin_id} Severity Classifier  |  Phase 2")
    print("=" * 62)

    if not os.path.exists(ENRICHED_PATH):
        print(f"[ERROR] {ENRICHED_PATH} not found.")
        return

    print("\n[1/6] Loading enriched incident data...")
    rows = []
    with open(ENRICHED_PATH, "r") as f:
        for line in f:
            rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    print(f"      Loaded {len(df):,} events")

    # Define base features
    ORIGINAL_FEATURES = [
        "sender_username_length",
        "sender_username_entropy",
        "receiver_domain_frequency"
    ]
    
    # Add bin-specific features
    if bin_id == "BIN_001":
        ORIGINAL_FEATURES.append("policy_encoded")
    elif bin_id == "BIN_002":
        # we used cc_domain_frequency in dbscan but baseline engine didn't carry it over,
        # wait! `baseline_engine.py` doesn't compute `cc_domain_frequency`. 
        # But `policy_encoded` wasn't added by baseline either, it was from dbscan!
        # Ah, `baseline_engine.py` just loads `timestamped.jsonl` which has `cc_domain_frequency` 
        # from `clustered_final.json` because `add_timestamps.py` keeps all keys.
        if "cc_domain_frequency" in df.columns:
            ORIGINAL_FEATURES.append("cc_domain_frequency")
    elif bin_id == "BIN_003":
        if "policy_encoded" in df.columns:
            ORIGINAL_FEATURES.append("policy_encoded")

    BEHAVIORAL_FEATURES = [
        "sender_30d_violation_count",
        "sender_7d_violation_count",
        "sender_policy_repeat",
        "sender_new_receiver",
        "sender_daily_volume_zscore",
        "sender_policy_diversity",
        "days_since_last_violation",
        "hour_of_day",
        "is_weekend",
        "is_after_hours",
        "violation_count",
    ]
    
    # filter features that exist
    ALL_FEATURES = [f for f in ORIGINAL_FEATURES + BEHAVIORAL_FEATURES if f in df.columns]
    TARGET_COL   = "severity"
    HIGH_LABELS = {"HIGH", "CRITICAL"}

    print(f"\n[2/6] Target distribution (behavioral-adjusted labels):")
    print(df[TARGET_COL].value_counts().to_string())

    print(f"\n[3/6] Building feature matrix ({len(ALL_FEATURES)} features)...")
    X = df[ALL_FEATURES].fillna(0)
    y = df[TARGET_COL]

    # Handle case where there's only 1 class (like BIN_003)
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    print(f"      Label classes: {list(le.classes_)}")
    
    HIGH_IDXS = [i for i, c in enumerate(le.classes_) if c in HIGH_LABELS]

    if len(le.classes_) == 1:
        print("\n[!] Only 1 class present. Model training skipped, falling back to dummy classifier.")
        # We can just save a dummy model that always predicts this class
        best_mdl = DummyModel(0)
        scaler = StandardScaler().fit(X) # just fit
    else:
        print(f"\n[4/6] Splitting 80/20 and scaling...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_enc, test_size=0.20, random_state=42, stratify=y_enc
        )
        scaler = StandardScaler()
        X_train_sc = scaler.fit_transform(X_train)
        X_test_sc  = scaler.transform(X_test)
        
        def high_fn_rate(y_true, y_pred, high_idxs):
            mask = np.isin(y_true, high_idxs)
            n_actual = mask.sum()
            if n_actual == 0: return 0.0
            n_missed = (~np.isin(y_pred[mask], high_idxs)).sum()
            return n_missed / n_actual * 100.0

        models = {
            "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced"),
            "Random Forest": RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced", n_jobs=-1),
            "Gradient Boosting": GradientBoostingClassifier(n_estimators=200, random_state=42, max_depth=4),
        }

        print(f"\n[5/6] Training and evaluating models...")
        results = {}
        for name, mdl in models.items():
            print(f"\n  >> {name}")
            mdl.fit(X_train_sc, y_train)
            y_pred = mdl.predict(X_test_sc)

            acc    = accuracy_score(y_test, y_pred) * 100
            fn_rt  = high_fn_rate(y_test, y_pred, HIGH_IDXS)

            print(f"     Accuracy             : {acc:.2f}%")
            print(f"     High-severity FN rate: {fn_rt:.2f}%  (target < 5%)")
            results[name] = {"model": mdl, "acc": acc, "fn_rate": fn_rt}

        best_name = min(results, key=lambda n: (results[n]["fn_rate"], -results[n]["acc"]))
        best_mdl = results[best_name]["model"]
        print(f"\n  [BEST] {best_name}")

    # ─── Save artefacts ──────────────────────────────────────────────────────────
    model_path  = os.path.join(MODELS_DIR, "severity_model.joblib")
    scaler_path = os.path.join(MODELS_DIR, "scaler.joblib")
    le_path     = os.path.join(MODELS_DIR, "label_encoder.joblib")
    feat_path   = os.path.join(MODELS_DIR, "feature_list.json")

    joblib.dump(best_mdl, model_path)
    joblib.dump(scaler,        scaler_path)
    joblib.dump(le,            le_path)
    with open(feat_path, "w") as f:
        json.dump(ALL_FEATURES, f, indent=2)

    print(f"\n  Saved artefacts to -> {MODELS_DIR}")
    print("  Done.\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin", type=str, required=True)
    args = parser.parse_args()
    process_bin(args.bin)
