"""ScamSaathi Streamlit Web Application (FR-071, FR-080, FR-084, NFR-011, NFR-012).

Agentic AI Assistant for Mobile Scam Defense in India.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure 'src' is in sys.path so scamsaathi is discoverable when launched directly via Streamlit CLI
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import streamlit as st

from scamsaathi.agents.context import build_context
from scamsaathi.config import PROJECT_ROOT, get_settings
from scamsaathi.pipeline.agentic import AgentRunner, AssessmentOutcome

# Page configuration
st.set_page_config(
    page_title="ScamSaathi - Mobile Scam Defense",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Custom CSS for high-contrast mobile responsiveness and 360px support
st.markdown(
    """
    <style>
    .reportview-container .main .block-container {
        max-width: 720px;
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .stButton button {
        min-height: 44px;
        font-weight: 600;
        border-radius: 8px;
    }
    .risk-badge {
        padding: 12px 18px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 1.15rem;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .risk-critical {
        background-color: #fee2e2;
        color: #991b1b;
        border: 2px solid #ef4444;
    }
    .risk-high {
        background-color: #ffedd5;
        color: #9a3412;
        border: 2px solid #f97316;
    }
    .risk-medium {
        background-color: #fef3c7;
        color: #92400e;
        border: 2px solid #f59e0b;
    }
    .risk-low {
        background-color: #ecfdf5;
        color: #065f46;
        border: 2px solid #10b981;
    }
    .portal-card {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .portal-title {
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 4px;
    }
    .disclaimer-box {
        font-size: 0.82rem;
        color: #64748b;
        border-top: 1px solid #e2e8f0;
        padding-top: 12px;
        margin-top: 24px;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_runner() -> AgentRunner:
    settings = get_settings()
    ctx = build_context(settings)
    return AgentRunner(ctx)


runner = get_runner()

# Pre-built scenarios for evaluator testing
DEMO_SCENARIOS = {
    "Select a pre-built scenario...": "",
    "🚨 KYC Phishing SMS (SBI Impersonation)": (
        "SBI Alert: Dear customer your SBI YONO account has been blocked today. "
        "Update KYC immediately at http://sbi-kyc-update.example/pan. Share OTP to verify."
    ),
    "🚨 Digital Arrest Threat (Hinglish Video Call)": (
        "CBI Headquarters calling: Aapke naam se parcel mein drugs aur illegal items mile hain. "
        "Arrest warrant issue ho chuka hai. Turant video call par aaiye aur matter clear kijiye, "
        "kisi ko batana nahi."
    ),
    "🚨 Advance Fee Lottery Scam (UPI)": (
        "Congratulations! You won Rs.25,00,000 in KBC Lucky Draw. "
        "To claim your prize, transfer government GST fee of Rs.4,999 to prize-tax@example-bank."
    ),
    "❓ Suspicious Parcel Call (Needs Clarification)": (
        "They called me saying a courier parcel arrived in my name and asked me to confirm details."
    ),
    "✅ Genuine Bank OTP Alert (Safe)": (
        "HDFC Bank: 482910 is your OTP for purchase of Rs. 1,450.00 at AMAZON. "
        "Do not share this OTP with anyone, including bank staff."
    ),
}

# Sidebar
with st.sidebar:
    st.title("🛡️ ScamSaathi")
    st.caption("Agentic AI Assistant for Mobile Scam Defense in India")

    st.markdown("---")
    st.subheader("📋 Privacy by Design (FR-084)")
    st.info(
        "**DPDP-Aligned Privacy Protection:**\n\n"
        "• **Automated Masking:** Phone numbers, emails, UPI IDs, bank accounts, national IDs (Aadhaar/PAN), and contextual OTPs are masked locally before AI processing.\n"
        "• **Known Limitations:** Pattern matching cannot reliably detect free-text personal names or street addresses; please avoid entering them.\n"
        "• **URLs Inspected:** Web links are analyzed for security threat intelligence and domain legitimacy.\n"
        "• **Zero Device Scraping:** Paste-only interface—we never access device SMS, call logs, or contacts.\n"
        "• **Ephemeral Processing:** Original text is cleared immediately after analysis."
    )

    st.markdown("---")
    st.subheader("🧪 Quick Demo Samples")
    selected_scenario = st.selectbox("Load sample message:", list(DEMO_SCENARIOS.keys()))

    settings = get_settings()
    st.markdown("---")
    st.caption(f"**Mode:** `{settings.mode.value}`")
    st.caption(f"**Primary Model:** `{settings.gemini_model_fast}`")
    if settings.groq_api_key:
        st.caption(f"**Fallback Provider:** `Groq ({settings.groq_model_fast})`")


# Session state initialization & Inactivity TTL (FR-084)
STREAMLIT_INACTIVITY_TTL_SECONDS = 1800.0  # 30-minute inactivity TTL for in-memory PII retention

now = time.time()
if "last_active_time" not in st.session_state:
    st.session_state.last_active_time = now

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "outcome" not in st.session_state:
    st.session_state.outcome = None
if "user_text_input" not in st.session_state:
    st.session_state.user_text_input = ""
if "last_selected_scenario" not in st.session_state:
    st.session_state.last_selected_scenario = "Select a pre-built scenario..."

# Inactivity TTL cleanup: purge abandoned runner session if inactive > 30 minutes
if st.session_state.thread_id and (now - st.session_state.last_active_time > STREAMLIT_INACTIVITY_TTL_SECONDS):
    runner.clear_session(st.session_state.thread_id)
    st.session_state.thread_id = None
    st.session_state.outcome = None
    st.session_state.last_active_time = now

# Handle scenario selection change: purge old runner session and load new text
if selected_scenario != st.session_state.last_selected_scenario:
    st.session_state.last_selected_scenario = selected_scenario
    if st.session_state.thread_id:
        runner.clear_session(st.session_state.thread_id)
    st.session_state.thread_id = None
    st.session_state.outcome = None
    st.session_state.user_text_input = DEMO_SCENARIOS.get(selected_scenario, "")
    st.session_state.last_active_time = now

# Main Screen
st.title("🛡️ ScamSaathi")
st.markdown("##### Assess any suspicious SMS, WhatsApp message, or phone call for scam risk.")

user_text = st.text_area(
    "Paste message or call details below:",
    key="user_text_input",
    height=140,
    placeholder="Paste the SMS, WhatsApp text, or caller conversation here...",
)

col_btn1, col_btn2 = st.columns([2, 1])
with col_btn1:
    analyze_clicked = st.button("🔍 Check Scam Risk", type="primary", use_container_width=True)
with col_btn2:
    if st.button("🗑️ Clear", use_container_width=True):
        if st.session_state.thread_id:
            runner.clear_session(st.session_state.thread_id)
        st.session_state.thread_id = None
        st.session_state.outcome = None
        st.session_state.user_text_input = ""
        st.session_state.last_active_time = time.time()
        st.rerun()

# Run Assessment
if analyze_clicked and user_text.strip():
    # Purge any previous session from runner before initiating a new assessment
    if st.session_state.thread_id:
        runner.clear_session(st.session_state.thread_id)
    st.session_state.last_active_time = time.time()
    with st.spinner("Analyzing message with threat intelligence & agent reasoning..."):
        try:
            outcome = runner.assess(user_text.strip())
            st.session_state.outcome = outcome
            st.session_state.thread_id = outcome.thread_id
        except Exception as exc:
            st.error(f"Error during assessment: {exc}")

# Display Outcome
outcome: AssessmentOutcome | None = st.session_state.outcome

if outcome is not None:
    st.markdown("---")

    # If Needs Follow-up (Interactive Interview)
    if outcome.status == "needs_followup":
        st.warning("⚠️ **ScamSaathi needs a little more information to be sure:**")
        st.markdown("Please answer these quick clarifying questions:")

        user_selections: dict[str, bool] = {}
        for idx, q in enumerate(outcome.questions, 1):
            fact_key = q.get("fact") or q.get("id") or f"q_{idx}"
            q_text = q.get("text", "")
            user_selections[fact_key] = st.checkbox(
                q_text,
                key=f"interview_check_{idx}_{fact_key}",
            )

        col_sub1, col_sub2 = st.columns(2)
        with col_sub1:
            if st.button("Submit Answers", type="primary", use_container_width=True):
                with st.spinner("Refining assessment with your answers..."):
                    # Map each question's fact directly to its checkbox value
                    structured_answers = {
                        q.get("fact", f"q_{idx}"): user_selections.get(
                            q.get("fact") or q.get("id") or f"q_{idx}", False
                        )
                        for idx, q in enumerate(outcome.questions, 1)
                    }
                    resumed = runner.resume(outcome.thread_id, {"answers": structured_answers})
                    st.session_state.outcome = resumed
                    st.session_state.last_active_time = time.time()
                    st.rerun()
        with col_sub2:
            if st.button("Skip / Give Best Guess", use_container_width=True):
                with st.spinner("Completing assessment..."):
                    resumed = runner.resume(outcome.thread_id, "skip")
                    st.session_state.outcome = resumed
                    st.session_state.last_active_time = time.time()
                    st.rerun()

    # Complete Assessment
    elif outcome.status == "complete" and outcome.risk is not None:
        level = outcome.risk.level
        score = outcome.risk.value

        badge_class = {
            "CRITICAL": "risk-critical",
            "HIGH": "risk-high",
            "MEDIUM": "risk-medium",
            "LOW": "risk-low",
        }.get(level, "risk-medium")

        badge_icon = {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "MEDIUM": "⚡",
            "LOW": "✅",
        }.get(level, "🛡️")

        st.markdown(
            f"""
            <div class="risk-badge {badge_class}">
                <span>{badge_icon} RISK LEVEL: {level}</span>
                <span>Score: {score} / 100</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Headline & Reasons
        if outcome.explanation is not None:
            st.markdown(f"### {outcome.explanation.headline}")
            st.markdown("#### **Key Reasons Detected:**")
            for reason in outcome.explanation.reasons:
                st.markdown(f"• {reason.text}")

        # Ordered Advice
        if outcome.advice is not None and outcome.advice.actions:
            st.markdown("#### **What You Should Do Now:**")
            for action in outcome.advice.actions:
                st.markdown(f"**{action.priority}.** {action.text}")

            if not outcome.advice.urgent_recovery_mode:
                with st.expander("⚠️ **Already Sent Money or Entered Bank / Card Details?**"):
                    st.markdown(
                        """
                        **If you already transferred money, scanned a QR code, or shared bank/UPI details:**
                        1. **Call 1930 promptly:** Contact the National Cyber Crime Helpline (24x7) to report the incident and request assistance with beneficiary lien procedures.
                        2. **Contact your bank via verified channels:** Immediately inform your bank's fraud desk to block compromised cards, UPI handles, or net banking access.
                        3. **Obtain UTR numbers:** Request a bank statement noting each 12-digit transaction reference (UTR).
                        4. **File an official complaint:** Lodge an online complaint at [cybercrime.gov.in](https://cybercrime.gov.in).
                        """
                    )

        # Official Reporting Section (Protect Others)
        if outcome.advice is not None and outcome.advice.contacts:
            st.markdown("---")
            st.markdown("### 📢 **Protect Others: Report this Scammer**")
            st.markdown(
                "Even if you did not lose money, reporting the scammer's number, link, or message "
                "helps Indian government authorities block them and prevents them from harming others:"
            )

            for contact in outcome.advice.contacts:
                if contact.channel == "url":
                    st.markdown(
                        f"""
                        <div class="portal-card">
                            <div class="portal-title">🌐 {contact.name}</div>
                            <div>Direct Official Portal: <a href="{contact.value}" target="_blank"><b>{contact.value}</b></a></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif contact.channel in ("phone", "sms"):
                    st.markdown(
                        f"""
                        <div class="portal-card">
                            <div class="portal-title">📞 {contact.name}</div>
                            <div>Dial or SMS: <b>{contact.value}</b></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            st.caption("🛡️ *All channels are verified official Indian government portals (DoT Sanchar Saathi & MHA I4C).*")

        # Technical Evidence / Threat Intel Expander (For Viva / Demo)
        with st.expander("🔬 Technical Evidence & Agent Intelligence (Examiner / Audit View)"):
            st.markdown(f"**Masked Text (What the AI sees):** `{outcome.masked_text}`")
            st.markdown(f"**Detected Typologies:** `{', '.join(outcome.typologies) or 'None'}`")
            st.markdown(f"**Explanation Source:** `{outcome.explanation_source}`")
            st.markdown(f"**LLM Calls:** `{outcome.llm_calls}` (Cache served if repeated)")
            if outcome.signals:
                st.markdown("**Extracted Behavioral Signals:**")
                for s in outcome.signals:
                    sig_name = s.name.value if hasattr(s.name, "value") else str(s.name)
                    st.markdown(f"- `{sig_name}` ({s.evidence_id}): *\"{s.evidence_span}\"*")
            if outcome.intel and outcome.intel.findings:
                st.markdown("**Threat Intel Findings:**")
                for f in outcome.intel.findings:
                    sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
                    st.markdown(f"- `[{sev.upper()}]` {f.check}: {f.detail} ({f.evidence_id})")

    # Advisory Disclaimer (FR-065)
    st.markdown(
        """
        <div class="disclaimer-box">
            🛡️ <b>Disclaimer (FR-065):</b> ScamSaathi provides risk assessments for guidance only. 
            It is not a legal or definitive determination. Always verify independently through official bank or government channels.
        </div>
        """,
        unsafe_allow_html=True,
    )

