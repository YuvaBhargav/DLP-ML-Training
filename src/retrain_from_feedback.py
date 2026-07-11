"""
retrain_from_feedback.py
Merges analyst feedback corrections with original enriched training data
and retrains the model for a given bin. Callable from the Streamlit UI or CLI.
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

# --- Paths ---
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDBACK_LOG = os.path.join(BASE_DIR, "feedback_log.jsonl")

# Each analyst correction row is duplicated this many times so the model
# trusts human judgement more than the original synthetic data.
FEEDBACK_WEIGHT = 3

HIGH_LABELS = {"HIGH", "CRITICAL"}


class DummyModel:
    """Mirrors the DummyModel in train.py for single-class bins."""
    def __init__(self, label_idx):
        self.label_idx = label_idx

    def predict(self, X):
        return np.full(X.shape[0], self.label_idx)

    def predict_proba(self, X):
        res = np.zeros((X.shape[0], 1))
        res[:, 0] = 1.0
        return res


def _high_fn_rate(y_true, y_pred, high_idxs):
    """% of actual HIGH/CRITICAL events predicted as MEDIUM -- the safety metric."""
    mask = np.isin(y_true, high_idxs)
    n_actual = mask.sum()
    if n_actual == 0:
        return 0.0
    n_missed = (~np.isin(y_pred[mask], high_idxs)).sum()
    return n_missed / n_actual * 100.0


def retrain_from_feedback(bin_id: str) -> dict:
    """
    Main entry point. Retrains the model for `bin_id` using original enriched
    data merged with analyst feedback corrections.

    Returns a dict with:
        bin_id, n_feedback, model_name, accuracy, fn_rate, log (list of strings)
    """
    bin_id_lower = bin_id.lower()
    log = []

    # 1. Load feature list
    feat_path = os.path.join(BASE_DIR, "models", bin_id_lower, "feature_list.json")
    if not os.path.exists(feat_path):
        raise FileNotFoundError(f"Feature list not found: {feat_path}")
    with open(feat_path) as f:
        feature_cols = json.load(f)
    log.append(f"Feature list loaded: {len(feature_cols)} features")

    # 2. Load original enriched training data
    enriched_path = os.path.join(BASE_DIR, "bins", bin_id_lower, f"{bin_id_lower}_enriched.jsonl")
    if not os.path.exists(enriched_path):
        raise FileNotFoundError(f"Enriched data not found: {enriched_path}")

    rows = []
    with open(enriched_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    df_original = pd.DataFrame(rows)
    log.append(f"Original training data: {len(df_original):,} rows")

    TARGET_COL   = "severity"
    ALL_FEATURES = [c for c in feature_cols if c in df_original.columns]

    df_train = df_original[ALL_FEATURES + [TARGET_COL]].fillna(0).copy()

    # 3. Load analyst feedback corrections for this bin
    feedback_rows = []
    if os.path.exists(FEEDBACK_LOG):
        with open(FEEDBACK_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Only apply overrides (not confirmed-correct entries)
                if entry.get("bin_id") == bin_id and not entry.get("was_correct", True):
                    feats = entry.get("features", {})
                    row = {col: float(feats.get(col, 0)) for col in ALL_FEATURES}
                    row[TARGET_COL] = entry["analyst_label"]
                    feedback_rows.append(row)

    n_feedback = len(feedback_rows)
    log.append(f"Analyst corrections found: {n_feedback}")

    if feedback_rows:
        # Duplicate each correction FEEDBACK_WEIGHT times for higher influence
        df_feedback = pd.DataFrame(feedback_rows * FEEDBACK_WEIGHT)
        df_train = pd.concat([df_train, df_feedback], ignore_index=True)
        log.append(f"Added {len(df_feedback)} weighted rows (x{FEEDBACK_WEIGHT} each) -> {len(df_train):,} total")
    else:
        log.append("No override corrections -- retraining on original data only.")

    # 4. Encode labels
    X = df_train[ALL_FEATURES].fillna(0)
    y = df_train[TARGET_COL]

    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    HIGH_IDXS = [i for i, c in enumerate(le.classes_) if c in HIGH_LABELS]
    log.append(f"Label classes: {list(le.classes_)}")
    log.append(f"Total training rows: {len(X):,}")

    # 5. Train models
    if len(le.classes_) == 1:
        log.append("Only 1 class present -- using DummyModel (no split needed).")
        best_mdl   = DummyModel(label_idx=0)
        scaler     = StandardScaler().fit(X)
        best_metrics = {"accuracy": 100.0, "fn_rate": 0.0, "model_name": "DummyModel"}

    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_enc, test_size=0.20, random_state=42, stratify=y_enc
        )
        scaler = StandardScaler()
        X_train_sc = scaler.fit_transform(X_train)
        X_test_sc  = scaler.transform(X_test)

        candidate_models = {
            "Logistic Regression": LogisticRegression(
                max_iter=1000, random_state=42, class_weight="balanced"
            ),
            "Random Forest": RandomForestClassifier(
                n_estimators=200, random_state=42, class_weight="balanced", n_jobs=-1
            ),
            "Gradient Boosting": GradientBoostingClassifier(
                n_estimators=200, random_state=42, max_depth=4
            ),
        }

        eval_results = {}
        for name, mdl in candidate_models.items():
            mdl.fit(X_train_sc, y_train)
            y_pred = mdl.predict(X_test_sc)
            acc   = accuracy_score(y_test, y_pred) * 100
            fn_rt = _high_fn_rate(y_test, y_pred, HIGH_IDXS)
            eval_results[name] = {"model": mdl, "acc": acc, "fn_rate": fn_rt}
            log.append(f"  {name}: Accuracy={acc:.2f}%  FN Rate={fn_rt:.2f}%")

        # Primary sort: lowest FN rate. Tie-break: highest accuracy.
        best_name = min(eval_results, key=lambda n: (eval_results[n]["fn_rate"], -eval_results[n]["acc"]))
        best_mdl  = eval_results[best_name]["model"]
        best_metrics = {
            "accuracy":   eval_results[best_name]["acc"],
            "fn_rate":    eval_results[best_name]["fn_rate"],
            "model_name": best_name,
        }
        log.append(f"Best model selected: {best_name}")

    # 6. Save artifacts
    models_dir = os.path.join(BASE_DIR, "models", bin_id_lower)
    os.makedirs(models_dir, exist_ok=True)

    joblib.dump(best_mdl, os.path.join(models_dir, "severity_model.joblib"))
    joblib.dump(scaler,   os.path.join(models_dir, "scaler.joblib"))
    joblib.dump(le,       os.path.join(models_dir, "label_encoder.joblib"))
    with open(os.path.join(models_dir, "feature_list.json"), "w") as f:
        json.dump(ALL_FEATURES, f, indent=2)

    log.append(f"Artifacts saved -> models/{bin_id_lower}/")

    return {
        "bin_id":     bin_id,
        "n_feedback": n_feedback,
        "log":        log,
        **best_metrics,
    }


# --- CLI entry point ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Retrain a bin model with analyst feedback corrections."
    )
    parser.add_argument("--bin", required=True, help="e.g. BIN_001, BIN_002, BIN_003")
    args = parser.parse_args()

    result = retrain_from_feedback(args.bin)
    print(f"\n{'=' * 60}")
    print(f"  Retrain complete for {result['bin_id']}")
    print(f"{'=' * 60}")
    for line in result["log"]:
        print(f"  {line}")
    print(f"\n  Best Model : {result['model_name']}")
    print(f"  Accuracy   : {result['accuracy']:.2f}%")
    print(f"  FN Rate    : {result['fn_rate']:.2f}%")
    print(f"  Feedback   : {result['n_feedback']} correction(s) applied")
