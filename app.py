"""
PharmAI - نظام التعليم الصيدلاني الذكي
Main Streamlit Application Entry Point
"""

import streamlit as st
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import init_db
from src.pages import upload_page, daily_test_page, review_page, question_bank_page, dashboard_page

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PharmAI - نظام التعليم الذكي",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "PharmAI - نظام تعليم صيدلاني مدعوم بالذكاء الاصطناعي"}
)

# ─── Inject Mobile-First CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --bg: #0a0e1a;
    --surface: #111827;
    --surface2: #1a2233;
    --accent: #00d4aa;
    --accent2: #6c63ff;
    --accent3: #ff6b6b;
    --text: #e8eaf0;
    --text-muted: #8892a4;
    --border: #1e2d40;
    --success: #00d4aa;
    --error: #ff6b6b;
    --warning: #ffd166;
    --radius: 16px;
    --radius-sm: 10px;
}

* { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Cairo', sans-serif !important;
    direction: rtl;
}

[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

[data-testid="stAppViewContainer"] > .main {
    padding: 0 !important;
    max-width: 100% !important;
}

.main .block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* ── Top Nav ── */
.pharmai-nav {
    background: linear-gradient(135deg, #0d1b2e 0%, #111827 100%);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 999;
    backdrop-filter: blur(20px);
}

.pharmai-logo {
    font-size: 22px;
    font-weight: 900;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
}

/* ── Bottom Tab Bar (Mobile) ── */
.tab-bar {
    position: fixed;
    bottom: 0;
    left: 0; right: 0;
    background: rgba(17, 24, 39, 0.97);
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-around;
    padding: 8px 0 env(safe-area-inset-bottom, 8px);
    z-index: 1000;
    backdrop-filter: blur(20px);
}

.tab-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    padding: 6px 12px;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s;
    color: var(--text-muted);
    font-size: 10px;
    font-family: 'Cairo', sans-serif;
    font-weight: 600;
    border: none;
    background: none;
    min-width: 56px;
}

.tab-item:hover { color: var(--accent); }
.tab-item.active { color: var(--accent); }
.tab-item.active .tab-icon {
    background: rgba(0, 212, 170, 0.15);
    color: var(--accent);
}

.tab-icon {
    font-size: 20px;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    transition: all 0.2s;
}

/* ── Content Area ── */
.page-content {
    padding: 16px;
    padding-bottom: 90px;
    min-height: 100vh;
}

/* ── Cards ── */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
    transition: all 0.2s;
}

.card:hover { border-color: var(--accent); }

.card-accent {
    background: linear-gradient(135deg, rgba(0,212,170,0.08) 0%, rgba(108,99,255,0.08) 100%);
    border-color: rgba(0,212,170,0.3);
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, var(--accent), #00b894) !important;
    color: #0a0e1a !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    padding: 12px 24px !important;
    width: 100% !important;
    transition: all 0.2s !important;
    box-shadow: 0 4px 20px rgba(0,212,170,0.25) !important;
}

.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 28px rgba(0,212,170,0.4) !important;
}

.btn-secondary > button {
    background: var(--surface2) !important;
    color: var(--text) !important;
    box-shadow: none !important;
    border: 1px solid var(--border) !important;
}

.btn-danger > button {
    background: linear-gradient(135deg, var(--error), #e55555) !important;
    box-shadow: 0 4px 20px rgba(255,107,107,0.25) !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text) !important;
    font-family: 'Cairo', sans-serif !important;
    font-size: 15px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(0,212,170,0.15) !important;
}

/* ── File Uploader ── */
[data-testid="stFileUploader"] {
    background: var(--surface2) !important;
    border: 2px dashed var(--border) !important;
    border-radius: var(--radius) !important;
    transition: all 0.2s !important;
}

[data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
}

/* ── Progress ── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent2)) !important;
    border-radius: 99px !important;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 16px !important;
}

[data-testid="stMetricValue"] {
    color: var(--accent) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 600 !important;
}

[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-family: 'Cairo', sans-serif !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface2) !important;
    border-radius: var(--radius-sm) !important;
    padding: 4px !important;
    gap: 4px !important;
    border: none !important;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-muted) !important;
    border-radius: 8px !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 600 !important;
    border: none !important;
}

.stTabs [aria-selected="true"] {
    background: var(--accent) !important;
    color: #0a0e1a !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}

/* ── Success/Error Boxes ── */
.success-box {
    background: rgba(0,212,170,0.1);
    border: 1px solid rgba(0,212,170,0.4);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    color: var(--accent);
    font-weight: 600;
    margin: 8px 0;
}

.error-box {
    background: rgba(255,107,107,0.1);
    border: 1px solid rgba(255,107,107,0.4);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    color: var(--error);
    font-weight: 600;
    margin: 8px 0;
}

.warning-box {
    background: rgba(255,209,102,0.1);
    border: 1px solid rgba(255,209,102,0.4);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    color: var(--warning);
    font-weight: 600;
    margin: 8px 0;
}

/* ── MCQ Option Cards ── */
.option-card {
    background: var(--surface);
    border: 2px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 16px;
    margin: 8px 0;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 15px;
    font-weight: 500;
}

.option-card:hover { border-color: var(--accent2); background: rgba(108,99,255,0.08); }
.option-card.correct { border-color: var(--success); background: rgba(0,212,170,0.1); }
.option-card.wrong { border-color: var(--error); background: rgba(255,107,107,0.1); }

/* ── Flashcard ── */
.flashcard {
    background: linear-gradient(135deg, var(--surface), var(--surface2));
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 36px 24px;
    text-align: center;
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 600;
    line-height: 1.8;
    box-shadow: 0 8px 40px rgba(0,0,0,0.4);
    cursor: pointer;
    transition: transform 0.3s;
}

.flashcard:hover { transform: scale(1.01); }

/* ── Stat Pill ── */
.stat-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 99px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* ── Selectbox ── */
.stSelectbox label, .stTextInput label, .stTextArea label, .stFileUploader label {
    color: var(--text-muted) !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 20px 0 !important; }

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── Tooltip ── */
.tooltip {
    position: relative;
    display: inline-block;
}

/* ── Badge ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 12px;
    font-weight: 700;
}
.badge-easy { background: rgba(0,212,170,0.15); color: var(--accent); }
.badge-medium { background: rgba(255,209,102,0.15); color: var(--warning); }
.badge-hard { background: rgba(255,107,107,0.15); color: var(--error); }

/* ── Mobile Responsive ── */
@media (max-width: 768px) {
    .page-content { padding: 12px; padding-bottom: 90px; }
    .flashcard { padding: 28px 18px; font-size: 16px; }
}
</style>
""", unsafe_allow_html=True)

# ─── Initialize DB ────────────────────────────────────────────────────────────
init_db()

# ─── Session State ────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "upload"
if "user_id" not in st.session_state:
    st.session_state.user_id = 1  # Single-user MVP

# ─── Navigation Bar ───────────────────────────────────────────────────────────
st.markdown("""
<div class="pharmai-nav">
    <span class="pharmai-logo">💊 PharmAI</span>
    <span style="color: var(--text-muted); font-size: 13px; font-weight: 600;">نظام التعليم الصيدلاني</span>
</div>
""", unsafe_allow_html=True)

# ─── Bottom Tab Bar ───────────────────────────────────────────────────────────
PAGES = [
    ("upload", "📤", "رفع"),
    ("daily", "🎯", "يومي"),
    ("review", "🔁", "مراجعة"),
    ("bank", "📚", "بنك"),
    ("dashboard", "📊", "تقدمي"),
]

tabs_html = '<div class="tab-bar">'
for page_id, icon, label in PAGES:
    active = "active" if st.session_state.page == page_id else ""
    tabs_html += f"""
    <button class="tab-item {active}" onclick="void(0)">
        <div class="tab-icon">{icon}</div>
        {label}
    </button>
    """
tabs_html += '</div>'
st.markdown(tabs_html, unsafe_allow_html=True)

# ─── Tab Navigation via columns ───────────────────────────────────────────────
cols = st.columns(5)
for i, (page_id, icon, label) in enumerate(PAGES):
    with cols[i]:
        if st.button(f"{icon} {label}", key=f"nav_{page_id}",
                     help=label, use_container_width=True):
            st.session_state.page = page_id
            # Clear question state on navigation
            for key in ["current_q", "answered", "show_explanation", "flip"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

st.markdown('<div class="page-content">', unsafe_allow_html=True)

# ─── Route Pages ──────────────────────────────────────────────────────────────
page = st.session_state.page
if page == "upload":
    upload_page.render()
elif page == "daily":
    daily_test_page.render()
elif page == "review":
    review_page.render()
elif page == "bank":
    question_bank_page.render()
elif page == "dashboard":
    dashboard_page.render()

st.markdown('</div>', unsafe_allow_html=True)
