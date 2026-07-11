import sys, os, json, tempfile
import pandas as pd
from datetime import datetime, timezone
import streamlit as st

# Setup absolute path to import from src correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from classify import load_bin_models, compute_features, DummyModel, classify_batch

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
# UI LAYOUT
# ─────────────────────────────────────────────
st.title("🛡️ Email DLP Severity Predictor")
st.markdown("Interactive PoC leveraging the **Phase 2 Multi-Bin Architecture**.")

tab1, tab2 = st.tabs(["Single Incident Analyzer", "Batch File Processor"])

# ─────────────────────────────────────────────
# TAB 1: SINGLE INCIDENT ANALYZER
# ─────────────────────────────────────────────
with tab1:
    st.sidebar.header("Incident Details (Single Test)")
    sender   = st.sidebar.text_input("Sender Email", "user001@yuva.com")
    receiver = st.sidebar.text_input("Receiver Email", "personal@gmail.com")
    policy   = st.sidebar.text_input("DLP Policy", "PII_PAN")
    cc       = st.sidebar.text_input("CC (Optional)", "", help="Required for BIN_002 source code rules")
    
    analyze_btn = st.sidebar.button("Analyze Incident Across All Bins", type="primary", use_container_width=True)
    
    if analyze_btn:
        if not sender or not receiver or not policy:
            st.warning("Please provide Sender, Receiver, and Policy to analyze.")
        else:
            st.subheader(f"Multi-Bin Analysis Results for `{sender}`")
            st.markdown("Comparing how the same event is evaluated by the specialized ML models for each bin.")
            
            # Run prediction for all 3 bins
            cols = st.columns(3)
            bins = ["BIN_001", "BIN_002", "BIN_003"]
            
            for i, bin_id in enumerate(bins):
                with cols[i]:
                    model_artifacts = get_model_and_baseline(bin_id)
                    if not model_artifacts:
                        st.error(f"Failed to load {bin_id} models.")
                        continue
                        
                    model, scaler, le, feature_cols, history = model_artifacts
                    combined_prior = history.get(sender, [])
                    
                    ev = {
                        "bin_id": bin_id,
                        "sender": sender,
                        "receiver": receiver,
                        "dlp_policy": policy,
                        "cc": cc,
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
                        <div style="background-color: #262730; padding: 15px; border-radius: 10px; border-left: 5px solid {color}; margin-bottom:15px;">
                            <h4 style="margin:0; color:#eee;">{bin_id}</h4>
                            <h2 style="margin:0; color:{color}; font-size:1.5rem;">{severity}</h2>
                            <p style="margin:5px 0 0 0; font-size: 0.9em; color:#bbb;">{action}</p>
                            <p style="margin:0; font-size: 0.8em; color:#888;">Confidence: {confidence}%</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("View Feature Context"):
                        st.json(feats)


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
