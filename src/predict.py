# -*- coding: utf-8 -*-
import sys, io, os, json
import pandas as pd
from datetime import datetime, timezone
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
predict.py -- Interactive severity predictor for Email DLP incidents
=============================================================================
Loads the trained models and lets you test them by typing in
email details. The model returns a severity prediction (CRITICAL / HIGH / MEDIUM).

Usage:
    venv/Scripts/python src/predict.py
"""

# Import the core logic from classify.py so we use the exact same feature engineering!
from classify import load_bin_models, compute_features, DummyModel

# ─────────────────────────────────────────────
# 1. Predict Wrapper
# ─────────────────────────────────────────────
def predict(bin_id: str, sender: str, receiver: str, dlp_policy: str, cc: str = ""):
    # Build a mock event
    ev = {
        "bin_id": bin_id,
        "sender": sender,
        "receiver": receiver,
        "dlp_policy": dlp_policy,
        "cc": cc,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        model, scaler, le, feature_cols, history = load_bin_models(bin_id)
    except SystemExit:
        print(f"\n  [!] Could not load models for {bin_id}. Please check if they exist in models/{bin_id.lower()}/")
        return

    # Use the sender's actual training history as the baseline
    combined_prior = history.get(sender, [])
    
    # Compute the full 14 features exactly as in production
    feats = compute_features(ev, combined_prior, feature_cols)
    
    # Scale and Predict
    X_raw = pd.DataFrame([feats], columns=feature_cols)
    X_sc  = scaler.transform(X_raw)

    if isinstance(model, DummyModel):
        label_idx = model.label_idx
        proba = model.predict_proba(X_sc)[0]
    else:
        label_idx = model.predict(X_sc)[0]
        proba     = model.predict_proba(X_sc)[0]

    severity   = le.inverse_transform([label_idx])[0]
    confidence = round(proba[0] * 100, 1) if isinstance(model, DummyModel) else round(proba[label_idx] * 100, 1)

    print()
    print("  -" * 50)
    print(f"  INCIDENT ANALYSIS ({bin_id})")
    print("  -" * 50)
    print(f"  Sender          : {sender}")
    print(f"  Receiver        : {receiver}")
    if cc:
        print(f"  CC              : {cc}")
    print(f"  DLP Policy      : {dlp_policy}")
    print()
    print("  Extracted Features:")
    for k, v in feats.items():
        print(f"    {k:<28}: {v}")
    
    print()
    print(f"  >> PREDICTED SEVERITY : {severity}")
    print(f"     Model confidence   : {confidence:.1f}%")

    if severity == "CRITICAL":
        print()
        print("  [ACTION REQUIRED] ESCALATE IMMEDIATELY.")
    elif severity == "HIGH":
        print()
        print("  [ACTION REQUIRED] HUMAN REVIEW REQUIRED.")
    else:
        print()
        print("  [REVIEW] LOG AND MONITOR. Potential policy exception.")

    print("  -" * 50)
    print()

# ─────────────────────────────────────────────
# 2. Interactive loop
# ─────────────────────────────────────────────
EXAMPLE_CASES = [
    ("BIN_001", "john.smith@yuva.com",      "john.smith@gmail.com", "PII_PAN", "", "Typical PAN -> Gmail (First-time offender = MEDIUM)"),
    ("BIN_001", "user001@yuva.com",         "user001@gmail.com",    "PII_PAN", "", "user001 from training history (Repeat offender = CRITICAL)"),
    ("BIN_002", "dev123@yuva.com",          "partner@vendor.com",   "SOURCE_CODE", "mgr@yuva.com", "Source code with manager CC (HIGH)"),
    ("BIN_002", "dev123@yuva.com",          "partner@vendor.com",   "SOURCE_CODE", "", "Source code without manager CC (CRITICAL)"),
    ("BIN_003", "contractor99@yuvaext.com", "personal@gmail.com",   "BU_CONTENT_G4", "", "Contractor sending BU data (CRITICAL)"),
]

def print_header():
    print()
    print("=" * 70)
    print("  Email DLP -- Multi-Bin Severity Predictor (Phase 2)")
    print("  Uses production classify.py logic & baseline histories")
    print("=" * 70)
    print()
    print("  Example cases (enter 'e' to cycle through them):")
    for i, (b, s, r, p, c, desc) in enumerate(EXAMPLE_CASES, 1):
        print(f"    {i}. [{b}] {desc}")
    print()
    print("  Type 'q' or 'quit' to exit.")
    print()

example_idx = [0]

def main():
    print_header()
    while True:
        print("  Enter incident details (or 'e' for example, 'q' to quit)")
        bin_in = input("  Bin ID (BIN_001/002/003): ").strip().upper()

        if bin_in.lower() in ("q", "quit", "exit"):
            print("\n  Bye!\n")
            break

        if bin_in.lower() == "e":
            case = EXAMPLE_CASES[example_idx[0] % len(EXAMPLE_CASES)]
            example_idx[0] += 1
            b, s, r, p, c, desc = case
            print(f"  [Example {example_idx[0]}] {desc}")
            predict(b, s, r, p, c)
            continue

        if not bin_in.startswith("BIN_"):
            print("  [!] Bin ID must be BIN_001, BIN_002, etc.")
            continue

        sender_in = input("  Sender email            : ").strip()
        receiver_in = input("  Receiver email          : ").strip()
        policy_in = input("  DLP policy              : ").strip()
        
        cc_in = ""
        if bin_in == "BIN_002":
            cc_in = input("  CC email (optional)     : ").strip()

        if not sender_in or not receiver_in or not policy_in:
            print("\n  [!] Sender, receiver, and policy fields are required.\n")
            continue

        predict(bin_in, sender_in, receiver_in, policy_in, cc_in)

if __name__ == "__main__":
    main()
