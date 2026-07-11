import sys, os, json, tempfile
import pandas as pd
from datetime import datetime, timezone
import streamlit as st

# Setup absolute path to import from src correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from classify import load_bin_models, compute_features, DummyModel, classify_batch
from retrain_from_feedback import retrain_from_feedback as run_retrain

# ─── Paths ─────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDBACK_LOG = os.path.join(BASE_DIR, "feedback_log.jsonl")

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Email DLP Severity Predictor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CACHE MODELS
# ─────────────────────────────────────────────
@st.cache_resource
def get_model_and_baseline(bin_id):
    try:
        return load_bin_models(bin_id)
    except Exception as e:
        return None

# ─────────────────────────────────────────────
# FEEDBACK HELPER
# ─────────────────────────────────────────────
def save_feedback(bin_id, sender, receiver, policy, model_prediction,
                  model_confidence, analyst_label, was_correct, feats, notes=""):
    """Append one analyst feedback record to feedback_log.jsonl."""
    # Convert any numpy scalars to native Python for JSON serialisation
    serialisable_feats = {k: (v.item() if hasattr(v, "item") else v) for k, v in feats.items()}
    entry = {
        "timestamp":        datetime.now().isoformat(),
        "bin_id":           bin_id,
        "sender":           sender,
        "receiver":         receiver,
        "dlp_policy":       policy,
        "model_prediction": model_prediction,
        "model_confidence": model_confidence,
        "analyst_label":    analyst_label,
        "was_correct":      was_correct,
        "notes":            notes,
        "features":         serialisable_feats,
    }
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

# ─────────────────────────────────────────────
# UI LAYOUT
# ─────────────────────────────────────────────
st.title("🛡️ Email DLP Severity Predictor")
st.markdown("Interactive PoC leveraging the **Phase 2 Multi-Bin Architecture**.")

tab1, tab2, tab3 = st.tabs(["🔍 Single Incident Analyzer", "📦 Batch File Processor", "📋 Analyst Feedback"])

# ─────────────────────────────────────────────
# TAB 1: SINGLE INCIDENT ANALYZER
# ─────────────────────────────────────────────
with tab1:
    st.sidebar.header("Incident Details")
    sender   = st.sidebar.text_input("Sender Email", "contractor@yuvaext.com")
    receiver = st.sidebar.text_input("Receiver Email", "personal@gmail.com")
    policy   = st.sidebar.text_input("DLP Policy", "ENCRYPTED")
    cc       = st.sidebar.text_input("CC (Optional)", "manager@yuva.com", help="Comma separated. Triggers business oversight rules.")
    violation_count = st.sidebar.number_input("# Violations (Regex Matches)", min_value=1, max_value=5000, value=15, step=1)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Payload Context")
    context_confidence = st.sidebar.slider("Regex Context Confidence", 0.0, 1.0, 1.0, 0.1, help="<0.5 marks as contextual False Positive (e.g. UTR detected as Aadhaar)")
    
    analyze_btn = st.sidebar.button("Analyze Incident", type="primary", use_container_width=True)
    
    if analyze_btn:
        if not sender or not receiver or not policy:
            st.warning("Please provide Sender, Receiver, and Policy to analyze.")
        else:
            # Auto-route to the correct Bin Model based on Policy
            p = policy.upper()
            if p == "SOURCE_CODE":
                bin_id = "BIN_002"
            elif p.startswith("BU_"):
                bin_id = "BIN_003"
            else:
                bin_id = "BIN_001"
                
            model_artifacts = get_model_and_baseline(bin_id)
            if not model_artifacts:
                st.error(f"Failed to load models. Please ensure {bin_id} models exist.")
            else:
                model, scaler, le, feature_cols, history = model_artifacts
                combined_prior = history.get(sender, [])
                has_history = len(combined_prior) > 0
                
                ev = {
                    "bin_id": bin_id,
                    "sender": sender,
                    "receiver": receiver,
                    "receiver_domain_type": "PERSONAL" if ("gmail" in receiver.lower() or "yahoo" in receiver.lower()) else "BUSINESS",
                    "dlp_policy": policy,
                    "cc": cc,
                    "violation_count": violation_count,
                    "context_confidence": context_confidence,
                    "timestamp": datetime.now().isoformat()
                }
                
                feats = compute_features(ev, combined_prior, feature_cols)
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

                if severity == "CRITICAL":
                    color = "red"
                    action = "ESCALATE IMMEDIATELY"
                elif severity == "HIGH":
                    color = "orange"
                    action = "HUMAN REVIEW REQUIRED"
                else:
                    color = "green"
                    action = "LOG AND MONITOR"

                st.markdown(f"""
                    <div style="background-color: #262730; padding: 20px; border-radius: 10px; border-left: 8px solid {color}; margin-bottom: 20px;">
                        <h2 style="margin:0; color:{color}; font-size:2rem;">SEVERITY: {severity}</h2>
                        <p style="margin:5px 0 0 0; font-size: 1.2em;"><strong>Recommended Action:</strong> {action}</p>
                        <p style="margin:5px 0 0 0; color:#bbb;">Model Confidence: {confidence}%</p>
                    </div>
                """, unsafe_allow_html=True)
                
                # Side-by-side breakdown
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 📊 Behavioral Context")
                    st.caption("Derived from the sender's historical baseline.")
                    if not has_history:
                        st.info("First-time offender. No historical baseline found.")
                    
                    # Display key behavioral metrics
                    m1, m2 = st.columns(2)
                    m1.metric("30-Day Violations", feats.get("sender_30d_violation_count", 0))
                    m2.metric("7-Day Violations", feats.get("sender_7d_violation_count", 0))
                    
                    m3, m4 = st.columns(2)
                    days_since = feats.get("days_since_last_violation", 999.0)
                    days_since_str = "N/A" if days_since == 999.0 else f"{days_since} days"
                    m3.metric("Last Violation", days_since_str)
                    m4.metric("New Receiver?", "Yes" if feats.get("sender_new_receiver", 0) == 1 else "No")
                    
                with col2:
                    st.markdown("### 🧮 Model Features")
                    st.caption("The exact feature vector fed to the ML model.")
                    st.json(feats)
                    
                st.markdown("---")

                # ── Store prediction in session state so the feedback form persists ──
                st.session_state.last_pred = {
                    "bin_id":     bin_id,
                    "sender":     sender,
                    "receiver":   receiver,
                    "policy":     policy,
                    "severity":   severity,
                    "confidence": confidence,
                    "feats":      feats,
                }
                st.session_state.feedback_submitted = False

    # ── Analyst Feedback Form (persists via session_state) ──────────────────
    if "last_pred" in st.session_state:
        pred = st.session_state.last_pred

        if st.session_state.get("feedback_submitted", False):
            st.success("✅ Feedback submitted! This correction will be applied on next retrain.")
        else:
            st.markdown("---")
            st.markdown("### 📋 Submit Analyst Feedback")
            col_fb1, col_fb2 = st.columns([3, 1])
            with col_fb1:
                fb_choice = st.radio(
                    f"Model predicted **{pred['severity']}** with **{pred['confidence']}%** confidence. Is this correct?",
                    ["✅ Confirmed Correct", "⚠️ Override Severity"],
                    horizontal=True,
                    key="fb_radio"
                )
            with col_fb2:
                if fb_choice == "⚠️ Override Severity":
                    override_sev = st.selectbox(
                        "Correct Severity",
                        [s for s in ["MEDIUM", "HIGH", "CRITICAL"] if s != pred["severity"]],
                        key="fb_override"
                    )
                else:
                    override_sev = pred["severity"]
                    st.caption(f"Label: **{pred['severity']}**")

            notes = st.text_area(
                "Analyst Notes (optional)",
                height=60,
                key="fb_notes",
                placeholder="e.g. Confirmed FP — user had manager approval for this transfer"
            )

            if st.button("📨 Submit Feedback", type="primary", key="fb_submit"):
                was_correct = fb_choice.startswith("✅")
                save_feedback(
                    bin_id=pred["bin_id"],
                    sender=pred["sender"],
                    receiver=pred["receiver"],
                    policy=pred["policy"],
                    model_prediction=pred["severity"],
                    model_confidence=pred["confidence"],
                    analyst_label=override_sev,
                    was_correct=was_correct,
                    feats=pred["feats"],
                    notes=notes
                )
                st.session_state.feedback_submitted = True
                st.rerun()

# ─────────────────────────────────────────────
# TAB 2: BATCH FILE PROCESSOR
# ─────────────────────────────────────────────
with tab2:
    st.markdown("### Process Enterprise DLP Logs (JSONL)")
    st.info("Upload a `.jsonl` file containing DLP events. The system will dynamically route each event to the correct bin model and append the predictions.")
    
    uploaded_file = st.file_uploader("Upload JSONL Log", type=["jsonl"])
    
    if uploaded_file is not None:
        if st.button("Process Batch", type="primary"):
            with st.spinner("Processing batch through ML models..."):
                # Save uploaded file to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                # Run the production classify_batch logic
                try:
                    results = classify_batch(tmp_path, output_path=None)
                except Exception as e:
                    st.error(f"Error processing file: {e}")
                    results = []
                    
                # Clean up temp file
                os.unlink(tmp_path)
                
                if results:
                    st.success(f"Successfully classified {len(results)} events!")
                    
                    # Convert to DataFrame for visualization
                    df = pd.DataFrame(results)
                    
                    # Flatten the behavioral_context for the DataFrame view
                    if "behavioral_context" in df.columns:
                        context_df = pd.json_normalize(df["behavioral_context"])
                        df = pd.concat([df.drop(columns=["behavioral_context"]), context_df], axis=1)
                        
                    # Display the DataFrame
                    st.dataframe(df, use_container_width=True)
                    
                    # Provide download button for the JSONL
                    out_lines = [json.dumps(r) for r in results]
                    out_str = "\n".join(out_lines) + "\n"
                    
                    st.download_button(
                        label="Download Classified JSONL",
                        data=out_str,
                        file_name="classified_results.jsonl",
                        mime="application/json"
                    )

# ─────────────────────────────────────────────
# TAB 3: ANALYST FEEDBACK
# ─────────────────────────────────────────────
with tab3:
    st.markdown("### 📋 Analyst Feedback Log")
    st.caption("All analyst corrections submitted from the Single Incident Analyzer. Use the Retrain buttons to bake corrections into the models.")

    # Load feedback entries
    feedback_entries = []
    if os.path.exists(FEEDBACK_LOG):
        with open(FEEDBACK_LOG, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line:
                    try:
                        feedback_entries.append(json.loads(_line))
                    except Exception:
                        pass

    if not feedback_entries:
        st.info("📢 No feedback submitted yet. Analyze incidents in the **🔍 Single Incident Analyzer** tab and submit corrections to start building the feedback log.")
    else:
        total     = len(feedback_entries)
        overrides = [e for e in feedback_entries if not e.get("was_correct", True)]
        confirmed = total - len(overrides)
        bins_with_overrides = sorted({e["bin_id"] for e in overrides})

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📊 Total Feedback",          total)
        m2.metric("✅ Confirmed Correct",          confirmed)
        m3.metric("⚠️ Override Corrections",      len(overrides))
        m4.metric("📦 Bins with Corrections",    len(bins_with_overrides))

        st.markdown("---")

        # Retrain buttons
        if overrides:
            st.markdown("#### 🔁 Retrain Models from Analyst Feedback")
            st.caption(
                f"Each of the **{len(overrides)} override(s)** is weighted **×3** in training so analyst "
                "judgement takes precedence over synthetic baseline data. Original model artifacts will be overwritten."
            )
            retrain_cols = st.columns(max(len(bins_with_overrides), 1))
            for idx, bin_id_r in enumerate(bins_with_overrides):
                n_bin_overrides = sum(1 for e in overrides if e["bin_id"] == bin_id_r)
                with retrain_cols[idx]:
                    if st.button(
                        f"🔁 Retrain {bin_id_r}  ({n_bin_overrides} correction(s))",
                        type="primary",
                        key=f"retrain_{bin_id_r}",
                        use_container_width=True
                    ):
                        with st.spinner(f"Retraining {bin_id_r} with {n_bin_overrides} analyst correction(s) — this may take ~30 s..."):
                            try:
                                result = run_retrain(bin_id_r)
                                # Invalidate the cached model so the next prediction loads the new one
                                get_model_and_baseline.clear()
                                st.success(f"✅ {bin_id_r} retrained successfully! New model is active.")
                                with st.expander("📊 View Training Details"):
                                    for log_line in result.get("log", []):
                                        st.text(log_line)
                                col_a, col_b, col_c = st.columns(3)
                                col_a.metric("New Accuracy",          f"{result.get('accuracy', 0):.2f}%")
                                col_b.metric("High-Severity FN Rate", f"{result.get('fn_rate', 0):.2f}%")
                                col_c.metric("Best Model",            result.get("model_name", "N/A"))
                            except Exception as exc:
                                st.error(f"Retraining failed: {exc}")

        st.markdown("---")
        st.markdown("#### 📄 Feedback History (most recent first)")

        display_rows = []
        for e in reversed(feedback_entries):
            display_rows.append({
                "Timestamp":     e.get("timestamp", "")[:19].replace("T", " "),
                "Bin":           e.get("bin_id", ""),
                "Sender":        e.get("sender", ""),
                "Policy":        e.get("dlp_policy", ""),
                "Model Predicted": e.get("model_prediction", ""),
                "Analyst Label": e.get("analyst_label", ""),
                "Correct?": "✅" if e.get("was_correct", True) else "❌",
                "Notes":         e.get("notes", ""),
            })
        df_fb = pd.DataFrame(display_rows)
        st.dataframe(df_fb, use_container_width=True, hide_index=True)
