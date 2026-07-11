import sys, os, json, tempfile
import pandas as pd
import requests
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

def get_llm_reasoning(feats, severity):
    prompt = f"""You are an expert SOC Analyst triage AI. Explain in 2-3 concise sentences why the following Data Loss Prevention (DLP) incident was assigned a severity of {severity} based on its contextual features.

Focus heavily on contextual factors like:
- violation_count: number of sensitive matches
- is_ftc: 1 if sender is a contractor
- has_manager_cc: 1 if a manager is CC'd
- is_personal_recipient: 1 if sending to gmail/yahoo
- is_encrypted_payload: 1 if the policy is ENCRYPTED

Features:
{json.dumps(feats, indent=2)}
"""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("response", "No response generated.")
        else:
            return f"Error: LLM returned status {response.status_code}"
    except requests.exceptions.RequestException as e:
        return "⚠️ **Local LLM not reachable.** Please ensure Ollama is running (`ollama run llama3`) to enable AI Reasoning."

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
                st.markdown("### 🧠 AI Analyst Reasoning")
                with st.spinner("Generating plain-English reasoning via Local LLM..."):
                    reasoning = get_llm_reasoning(feats, severity)
                    st.info(reasoning)

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
