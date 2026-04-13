import streamlit as st
import tempfile
import os
import cv2
import zipfile
import shutil
import random
import sqlite3
import hashlib
from ultralytics import YOLO
from streamlit_option_menu import option_menu

# ==========================================
# Page Config
# ==========================================
st.set_page_config(
    page_title="AI-Dataset Pro",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# Database
# ==========================================
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()

def create_usertable():
    c.execute('CREATE TABLE IF NOT EXISTS userstable(username TEXT, password TEXT)')

def add_userdata(username, password):
    hashed = hashlib.sha256(str.encode(password)).hexdigest()
    c.execute('INSERT INTO userstable(username, password) VALUES (?,?)', (username, hashed))
    conn.commit()

def login_user(username, password):
    hashed = hashlib.sha256(str.encode(password)).hexdigest()
    c.execute('SELECT * FROM userstable WHERE username=? AND password=?', (username, hashed))
    return c.fetchall()

create_usertable()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""

# ==========================================
# Global CSS — "Obsidian Terminal" Theme
# ==========================================
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@400;600;700;800&display=swap');

/* ── ROOT TOKENS ──────────────────────────────── */
:root {
    --bg-deep:    #060a12;
    --bg-surface: #0d1422;
    --bg-raised:  #121c30;
    --bg-hover:   #182338;
    --border:     #1e2e45;
    --border-hi:  #2a4060;
    --accent:     #3b9eff;
    --accent-dim: rgba(59,158,255,0.12);
    --accent-glow:rgba(59,158,255,0.25);
    --green:      #22d3a0;
    --red:        #f05252;
    --amber:      #f59e0b;
    --text-1:     #e8f0fa;
    --text-2:     #7a96b4;
    --text-3:     #3d5570;
    --font-ui:    'Syne', sans-serif;
    --font-mono:  'DM Mono', monospace;
    --r:          10px;
    --r-lg:       14px;
}

/* ── BASE ─────────────────────────────────────── */
html, body, .stApp {
    background-color: var(--bg-deep) !important;
    color: var(--text-1);
    font-family: var(--font-ui);
}

/* ── HIDE STREAMLIT DEFAULT CHROME ───────────── */
/* Top header bar */
header[data-testid="stHeader"] {
    background-color: var(--bg-deep) !important;
    border-bottom: none !important;
    box-shadow: none !important;
}
/* Toolbar icons area */
[data-testid="stToolbar"] { display: none !important; }
/* Decoration / top line */
[data-testid="stDecoration"] { display: none !important; }
/* Main menu hamburger */
#MainMenu { visibility: hidden !important; }
/* Footer */
footer { visibility: hidden !important; }
/* App view container top padding fix */
.appview-container { background-color: var(--bg-deep) !important; }
.main > div { padding-top: 0.5rem !important; }

/* ── SCROLLBAR ───────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-deep); }
::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 2px; }

/* ── SIDEBAR ─────────────────────────────────── */
/* Outer wrapper — kill white gap on the right edge of sidebar */
[data-testid="stSidebar"] {
    background-color: var(--bg-deep) !important;
    border-right: none !important;
    padding: 12px 10px 12px 12px !important;
}
/* Inner card with rounded corners */
[data-testid="stSidebar"] > div:first-child {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    overflow: hidden !important;
    height: 100% !important;
}
[data-testid="stSidebar"] > div { padding-top: 0 !important; }
[data-testid="stSidebar"] * { font-family: var(--font-ui) !important; }

/* Sidebar top logo strip */
.sidebar-brand {
    padding: 22px 20px 18px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 8px;
}
.sidebar-brand .logo-mark {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
}
.sidebar-brand .hex {
    width: 32px; height: 32px;
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; color: var(--accent); font-weight: 700;
}
.sidebar-brand h2 {
    font-size: 15px !important;
    font-weight: 700 !important;
    color: var(--text-1) !important;
    letter-spacing: 0.3px;
    margin: 0 !important;
}
.sidebar-brand p {
    font-family: var(--font-mono) !important;
    font-size: 10px !important;
    color: var(--text-3) !important;
    letter-spacing: 2px;
    margin: 0 !important;
}

/* User badge in sidebar */
.user-badge {
    margin: 8px 16px;
    padding: 10px 14px;
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: var(--r);
    display: flex; align-items: center; gap: 10px;
}
.user-badge .avatar {
    width: 28px; height: 28px; border-radius: 50%;
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; color: var(--accent);
    flex-shrink: 0;
    font-family: var(--font-mono) !important;
}
.user-badge .uname {
    font-size: 12px; font-weight: 600; color: var(--text-1);
    font-family: var(--font-mono) !important;
}
.user-badge .ustatus {
    font-size: 10px; color: var(--green);
    font-family: var(--font-mono) !important;
    letter-spacing: 1px;
}

/* ── OPTION MENU OVERRIDE ─────────────────────── */
div[data-testid="stSidebar"] .nav-link {
    font-size: 13px !important;
    border-radius: var(--r) !important;
    margin: 2px 8px !important;
    color: var(--text-2) !important;
    font-weight: 500 !important;
}
div[data-testid="stSidebar"] .nav-link:hover {
    background: var(--bg-hover) !important;
    color: var(--text-1) !important;
}
div[data-testid="stSidebar"] .nav-link-selected {
    background: var(--accent-dim) !important;
    color: var(--accent) !important;
    border: 1px solid rgba(59,158,255,0.3) !important;
    font-weight: 600 !important;
}
div[data-testid="stSidebar"] .nav-link-selected i { color: var(--accent) !important; }

/* ── PAGE HEADER ─────────────────────────────── */
.page-header {
    padding: 28px 0 20px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
}
.page-header .eyebrow {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--accent);
    letter-spacing: 2.5px;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.page-header h1 {
    font-size: 26px !important;
    font-weight: 800 !important;
    color: var(--text-1) !important;
    letter-spacing: -0.5px;
    margin: 0 !important;
    line-height: 1.2 !important;
}
.page-header .sub {
    font-size: 13px;
    color: var(--text-2);
    margin-top: 6px;
    font-family: var(--font-mono);
}

/* ── SECTION CARD ────────────────────────────── */
.section-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 20px;
    margin-bottom: 16px;
}
.section-card .card-label {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-3);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 14px;
    display: flex; align-items: center; gap: 8px;
}
.section-card .card-label::before {
    content: '';
    display: inline-block;
    width: 14px; height: 1px;
    background: var(--accent);
}

/* ── UPLOAD ZONE ─────────────────────────────── */
.upload-zone {
    border: 1.5px dashed var(--border-hi);
    border-radius: var(--r-lg);
    padding: 32px 20px;
    text-align: center;
    background: var(--bg-surface);
    transition: all 0.25s;
    cursor: pointer;
    margin-bottom: 16px;
    position: relative;
}
.upload-zone::before {
    content: '';
    position: absolute; inset: 0;
    border-radius: var(--r-lg);
    background: radial-gradient(circle at 50% 0%, rgba(59,158,255,0.04), transparent 60%);
}
.upload-zone:hover {
    border-color: var(--accent);
    background: var(--bg-raised);
}
.upload-zone .uz-icon {
    font-size: 28px;
    margin-bottom: 10px;
    display: block;
    opacity: 0.6;
}
.upload-zone .uz-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-1);
    margin-bottom: 4px;
}
.upload-zone .uz-sub {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-3);
}

/* ── STAT PILL ROW ───────────────────────────── */
.stat-row {
    display: flex; gap: 10px; margin-top: 16px;
}
.stat-pill {
    flex: 1;
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 12px 14px;
    text-align: center;
}
.stat-pill .sp-label {
    font-family: var(--font-mono);
    font-size: 9px;
    color: var(--text-3);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    display: block;
    margin-bottom: 4px;
}
.stat-pill .sp-val {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-1);
    font-family: var(--font-mono);
}

/* ── BUTTONS ─────────────────────────────────── */
.stButton > button {
    font-family: var(--font-ui) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    letter-spacing: 0.8px !important;
    border-radius: var(--r) !important;
    border: 1px solid var(--border-hi) !important;
    background: var(--bg-raised) !important;
    color: var(--text-1) !important;
    padding: 10px 20px !important;
    transition: all 0.2s !important;
    height: auto !important;
}
.stButton > button:hover {
    border-color: var(--accent) !important;
    background: var(--accent-dim) !important;
    color: var(--accent) !important;
}
/* Primary action button */
.primary-btn > button,
div[data-testid="stButton"]:has(button[kind="primary"]) > button {
    background: var(--accent-dim) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
.primary-btn > button:hover {
    background: var(--accent) !important;
    color: var(--bg-deep) !important;
}

/* ── DOWNLOAD BUTTON ─────────────────────────── */
.stDownloadButton > button {
    font-family: var(--font-ui) !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.8px !important;
    border-radius: var(--r) !important;
    background: var(--accent) !important;
    color: var(--bg-deep) !important;
    border: none !important;
    padding: 12px 20px !important;
}
.stDownloadButton > button:hover {
    opacity: 0.9 !important;
}

/* ── INPUTS ──────────────────────────────────── */
.stTextInput > label,
.stMultiselect > label,
.stSlider > label,
.stFileUploader > label {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    color: var(--text-3) !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    font-weight: 500 !important;
}
.stTextInput > div > div > input {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text-1) !important;
    font-family: var(--font-mono) !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-glow) !important;
}
.stTextInput > div > div > input::placeholder { color: var(--text-3) !important; }

/* Multiselect */
[data-baseweb="select"] > div {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
}
[data-baseweb="select"] span { color: var(--text-1) !important; font-size: 13px !important; }
[data-baseweb="tag"] {
    background: var(--accent-dim) !important;
    border: 1px solid rgba(59,158,255,0.3) !important;
    border-radius: 6px !important;
}
[data-baseweb="tag"] span { color: var(--accent) !important; font-size: 11px !important; }

/* Dropdown list */
[data-baseweb="menu"] { background: var(--bg-raised) !important; border: 1px solid var(--border-hi) !important; border-radius: var(--r) !important; }
[data-baseweb="option"] { background: transparent !important; color: var(--text-2) !important; font-size: 13px !important; }
[data-baseweb="option"]:hover { background: var(--bg-hover) !important; color: var(--text-1) !important; }

/* ── SLIDER ──────────────────────────────────── */
[data-baseweb="slider"] { padding: 6px 0 !important; }
[data-baseweb="track-background"] { background: var(--border-hi) !important; height: 3px !important; border-radius: 2px !important; }
[data-baseweb="track-fill"] { background: var(--accent) !important; height: 3px !important; border-radius: 2px !important; }
[data-baseweb="thumb"] {
    background: var(--bg-deep) !important;
    border: 2px solid var(--accent) !important;
    width: 16px !important; height: 16px !important;
    box-shadow: 0 0 0 4px var(--accent-glow) !important;
}
.stSlider [data-testid="stTickBar"] { display: none !important; }

/* ── EXPANDER ────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    margin-bottom: 16px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    color: var(--text-2) !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    font-weight: 500 !important;
    padding: 16px 20px !important;
    background: var(--bg-surface) !important;
}
[data-testid="stExpander"] summary:hover { background: var(--bg-raised) !important; }
[data-testid="stExpander"] > div > div { padding: 0 20px 20px !important; }

/* ── TABS ────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-3) !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    padding: 12px 22px !important;
    border-radius: 0 !important;
    transition: all 0.2s !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text-1) !important; }
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 24px 0 0 !important; }

/* ── PROGRESS BAR ────────────────────────────── */
.stProgress > div > div {
    background: var(--bg-raised) !important;
    border-radius: 2px !important;
    height: 3px !important;
}
.stProgress > div > div > div {
    background: var(--accent) !important;
    border-radius: 2px !important;
    height: 3px !important;
}

/* ── ALERTS ──────────────────────────────────── */
[data-testid="stAlert"] {
    background: var(--bg-raised) !important;
    border-radius: var(--r) !important;
    font-size: 13px !important;
    font-family: var(--font-mono) !important;
}
[data-testid="stAlert"][data-type="success"] {
    border-left: 3px solid var(--green) !important;
    border-top: none !important; border-right: none !important; border-bottom: none !important;
}
[data-testid="stAlert"][data-type="error"] {
    border-left: 3px solid var(--red) !important;
}
[data-testid="stAlert"][data-type="warning"] {
    border-left: 3px solid var(--amber) !important;
}
[data-testid="stAlert"][data-type="info"] {
    border-left: 3px solid var(--accent) !important;
}
.stSuccess, .element-container .stAlert {
    border: 1px solid var(--border) !important;
}

/* ── DIVIDER ─────────────────────────────────── */
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 20px 0 !important; }

/* ── FILE UPLOADER ───────────────────────────── */
[data-testid="stFileUploaderDropzone"] {
    background: var(--bg-surface) !important;
    border: 1.5px dashed var(--border-hi) !important;
    border-radius: var(--r-lg) !important;
    padding: 28px !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--accent) !important;
    background: var(--bg-raised) !important;
}
[data-testid="stFileUploaderDropzone"] button {
    background: var(--accent-dim) !important;
    border: 1px solid var(--accent) !important;
    color: var(--accent) !important;
    border-radius: var(--r) !important;
    font-family: var(--font-ui) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
}
[data-testid="stFileUploaderDropzone"] small {
    color: var(--text-3) !important;
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
}

/* ── IMAGE (preview) ─────────────────────────── */
[data-testid="stImage"] img {
    border-radius: var(--r) !important;
    border: 1px solid var(--border) !important;
}

/* ── VIDEO ───────────────────────────────────── */
video {
    border-radius: var(--r) !important;
    border: 1px solid var(--border) !important;
    width: 100% !important;
}

/* ── COLUMNS ─────────────────────────────────── */
[data-testid="stHorizontalBlock"] { gap: 16px !important; }

/* ── MARKDOWN BODY TEXT ──────────────────────── */
.stMarkdown p {
    color: var(--text-2) !important;
    font-size: 13px !important;
    font-family: var(--font-mono) !important;
    line-height: 1.7 !important;
}
.stMarkdown h3 {
    font-family: var(--font-ui) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--text-2) !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    margin-bottom: 8px !important;
}
.stMarkdown strong { color: var(--text-1) !important; font-weight: 600 !important; }

/* ── MAIN AREA PADDING ───────────────────────── */
.main .block-container {
    padding: 0 2rem 2rem !important;
    max-width: 1200px;
}

/* ── STATUS TEXT ─────────────────────────────── */
.status-text {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--accent);
    letter-spacing: 1px;
    padding: 8px 0;
}

/* ── AUTH PAGE ───────────────────────────────── */
.auth-container {
    max-width: 440px;
    margin: 60px auto 0;
}
.auth-header {
    text-align: center;
    padding: 32px 0 28px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 28px;
}
.auth-header .auth-logo {
    width: 48px; height: 48px;
    background: var(--accent-dim);
    border: 1px solid rgba(59,158,255,0.4);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
    margin: 0 auto 16px;
}
.auth-header h1 {
    font-size: 22px !important;
    font-weight: 800 !important;
    color: var(--text-1) !important;
    letter-spacing: -0.3px;
    margin: 0 0 4px !important;
}
.auth-header .auth-tagline {
    font-family: var(--font-mono) !important;
    font-size: 10px !important;
    color: var(--text-3) !important;
    letter-spacing: 2.5px !important;
}

/* ── SECTION LABEL ───────────────────────────── */
.section-label {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-3);
    letter-spacing: 2px;
    text-transform: uppercase;
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 10px;
}
.section-label::before {
    content: '';
    width: 12px; height: 1px;
    background: var(--border-hi);
    display: inline-block;
}

/* Video column headers */
.col-header {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-3);
    letter-spacing: 2px;
    text-transform: uppercase;
    display: flex; align-items: center; gap: 6px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}
.dot-status {
    width: 6px; height: 6px;
    border-radius: 50%;
    display: inline-block;
}
.dot-blue { background: var(--accent); }
.dot-green { background: var(--green); }
</style>
"""

# ==========================================
# Auth Page
# ==========================================
def show_auth_page():
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    # Centered narrow column
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div class="auth-header">
            <div class="auth-logo">⬡</div>
            <h1>AI-Dataset Pro</h1>
            <div class="auth-tagline">COMPUTER VISION PLATFORM</div>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["LOGIN", "REGISTER"])

        with tab1:
            login_user_input = st.text_input("Username", key="login_user", placeholder="your username")
            login_pass_input = st.text_input("Password", type="password", key="login_pass", placeholder="••••••••")
            if st.button("INITIATE LOGIN", use_container_width=True, key="btn_login"):
                if login_user_input and login_pass_input:
                    result = login_user(login_user_input, login_pass_input)
                    if result:
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = login_user_input
                        st.rerun()
                    else:
                        st.error("Access denied — invalid credentials")
                else:
                    st.warning("Please fill in all fields")

        with tab2:
            new_user = st.text_input("New Username", key="reg_user", placeholder="choose a username")
            new_pass = st.text_input("New Password", type="password", key="reg_pass", placeholder="••••••••")
            if st.button("CREATE ACCOUNT", use_container_width=True, key="btn_register"):
                if new_user and new_pass:
                    c.execute('SELECT * FROM userstable WHERE username=?', (new_user,))
                    if c.fetchone():
                        st.error("Username already exists")
                    else:
                        add_userdata(new_user, new_pass)
                        st.success("Account created — you can now log in")
                else:
                    st.warning("Please fill in all fields")

# ==========================================
# Main Application
# ==========================================
def show_main_app():
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    # ── SIDEBAR ──────────────────────────────
    with st.sidebar:
        init = st.session_state['username'][0].upper() if st.session_state['username'] else "?"
        st.markdown(f"""
        <div class="sidebar-brand">
            <div class="logo-mark">
                <div class="hex">⬡</div>
                <h2>AI-Dataset Pro</h2>
            </div>
            <p>COMPUTER VISION · v2.0</p>
        </div>
        <div class="user-badge">
            <div class="avatar">{init}</div>
            <div>
                <div class="uname">{st.session_state['username'].upper()}</div>
                <div class="ustatus">● ACTIVE SESSION</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        selected_menu = option_menu(
            menu_title=None,
            options=["Dashboard", "AI Engine", "Logout"],
            icons=["grid-1x2", "cpu", "box-arrow-right"],
            default_index=1,
            styles={
                "container": {"background-color": "transparent", "padding": "8px 0"},
                "icon": {"font-size": "14px"},
                "nav-link": {
                    "font-size": "13px",
                    "font-weight": "500",
                    "color": "#7a96b4",
                    "border-radius": "10px",
                    "margin": "2px 8px",
                    "padding": "10px 16px",
                },
                "nav-link-selected": {
                    "background-color": "rgba(59,158,255,0.12)",
                    "color": "#3b9eff",
                    "border": "1px solid rgba(59,158,255,0.3)",
                    "font-weight": "600",
                },
            }
        )
        if selected_menu == "Logout":
            st.session_state.clear()
            st.rerun()

    # ── AI ENGINE PAGE ────────────────────────
    if selected_menu == "AI Engine":
        st.markdown("""
        <div class="page-header">
            <div class="eyebrow">MODULE / AI ENGINE</div>
            <h1>Dataset Generation</h1>
            <div class="sub">Extract & label training data from video using YOLOv8</div>
        </div>
        """, unsafe_allow_html=True)

        @st.cache_resource
        def load_model():
            return YOLO('yolov8n.pt')
        model = load_model()
        available_classes = model.names

        # ── SETTINGS EXPANDER ─────────────────
        with st.expander("⚙  NEURAL NETWORK CONFIGURATION"):
            col1, col2 = st.columns(2, gap="large")
            with col1:
                selected_class_names = st.multiselect(
                    "Detection Targets",
                    list(available_classes.values()),
                    default=["person", "car"]
                )
                selected_class_ids = [k for k, v in available_classes.items() if v in selected_class_names]
            with col2:
                split_ratio = st.slider("Train / Val Split (%)", 50, 95, 80)
                frame_skip  = st.slider("Frame Extraction Interval", 1, 30, 10)

        # ── FILE UPLOAD ───────────────────────
        st.markdown('<div class="section-label">Media Source</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Drop video file here",
            type=['mp4', 'avi', 'mov'],
            label_visibility="collapsed"
        )

        if uploaded_file is not None:
            tfile = tempfile.NamedTemporaryFile(delete=False)
            tfile.write(uploaded_file.read())
            tfile.close()
            video_path = tfile.name

            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.markdown('<div class="col-header"><span class="dot-status dot-blue"></span>SOURCE</div>', unsafe_allow_html=True)
                st.video(uploaded_file)
            with col2:
                st.markdown('<div class="col-header"><span class="dot-status dot-green"></span>AI VISION</div>', unsafe_allow_html=True)
                image_preview = st.empty()

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("▶  EXECUTE AI PROCESSING", use_container_width=True):
                output_folder = "dataset_workspace"
                if os.path.exists(output_folder): shutil.rmtree(output_folder)
                for f in ['images/train', 'images/val', 'labels/train', 'labels/val']:
                    os.makedirs(os.path.join(output_folder, f))

                cap = cv2.VideoCapture(video_path)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                progress_bar = st.progress(0)
                status_text  = st.empty()

                frame_count = 0
                dataset_records = []
                class_counts = {n: 0 for n in selected_class_names} if selected_class_names else {v: 0 for v in available_classes.values()}

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret: break
                    if frame_count % frame_skip == 0:
                        results = model(frame, classes=selected_class_ids if selected_class_ids else None, verbose=False)
                        boxes = results[0].boxes
                        if len(boxes) > 0:
                            subset    = "train" if random.random() < (split_ratio / 100.0) else "val"
                            base_name = f"frame_{frame_count:06d}"
                            cv2.imwrite(f"{output_folder}/images/{subset}/{base_name}.jpg", frame)
                            with open(f"{output_folder}/labels/{subset}/{base_name}.txt", 'w') as f:
                                for box in boxes:
                                    c_id   = int(box.cls)
                                    c_name = available_classes[c_id]
                                    class_counts[c_name] += 1
                                    new_id = selected_class_names.index(c_name) if selected_class_names else c_id
                                    x, y, w, h = box.xywhn[0]
                                    f.write(f"{new_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")
                            dataset_records.append({"subset": subset, "file": base_name})
                            annotated = results[0].plot()
                            image_preview.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_container_width=True)
                    frame_count += 1
                    progress_bar.progress(min(frame_count / total_frames, 1.0))
                    status_text.markdown(f'<div class="status-text">PROCESSING  {frame_count} / {total_frames}  FRAMES</div>', unsafe_allow_html=True)
                cap.release()

                # YAML
                classes_for_yaml = selected_class_names if selected_class_names else list(available_classes.values())
                with open(os.path.join(output_folder, "data.yaml"), 'w', encoding='utf-8') as f:
                    f.write("train: images/train\nval: images/val\n\n")
                    f.write(f"nc: {len(classes_for_yaml)}\n")
                    f.write(f"names: [{', '.join([repr(n) for n in classes_for_yaml])}]\n")

                # Stats
                train_count = sum(1 for r in dataset_records if r['subset'] == 'train')
                val_count   = len(dataset_records) - train_count
                total_labels = sum(class_counts.values())

                st.markdown(f"""
                <div class="stat-row">
                    <div class="stat-pill"><span class="sp-label">Total Images</span><span class="sp-val">{len(dataset_records)}</span></div>
                    <div class="stat-pill"><span class="sp-label">Train</span><span class="sp-val">{train_count}</span></div>
                    <div class="stat-pill"><span class="sp-label">Val</span><span class="sp-val">{val_count}</span></div>
                    <div class="stat-pill"><span class="sp-label">Labels</span><span class="sp-val">{total_labels}</span></div>
                </div>
                """, unsafe_allow_html=True)

                st.divider()
                st.success("Dataset generation complete")

                zip_filename = "ai_dataset.zip"
                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                    for root, dirs, files in os.walk(output_folder):
                        for file in files:
                            zipf.write(
                                os.path.join(root, file),
                                os.path.relpath(os.path.join(root, file), output_folder)
                            )
                with open(zip_filename, "rb") as fp:
                    st.download_button(
                        "⬇  DOWNLOAD DATASET",
                        fp, "ai_dataset.zip", "application/zip",
                        use_container_width=True
                    )
                os.remove(video_path)
                shutil.rmtree(output_folder)
                os.remove(zip_filename)

    # ── DASHBOARD PAGE ────────────────────────
    elif selected_menu == "Dashboard":
        st.markdown("""
        <div class="page-header">
            <div class="eyebrow">MODULE / OVERVIEW</div>
            <h1>System Dashboard</h1>
            <div class="sub">Analytics and dataset metrics — coming soon</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="section-card" style="text-align:center; padding: 48px 20px;">
            <div style="font-size: 32px; margin-bottom: 16px; opacity: 0.3;">◫</div>
            <div style="font-family: 'DM Mono', monospace; font-size: 11px; color: var(--text-3); letter-spacing: 2px;">UNDER CONSTRUCTION</div>
            <div style="margin-top: 8px; font-size: 13px; color: var(--text-2);">Analytics module is being developed</div>
        </div>
        """, unsafe_allow_html=True)


# ── ROUTER ────────────────────────────────────
if not st.session_state['logged_in']:
    show_auth_page()
else:
    show_main_app()