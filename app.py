import streamlit as st
import tempfile
import os
import cv2
import zipfile
import shutil
import random
import sqlite3
import hashlib
import numpy as np
import re
import pandas as pd
import datetime
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

def create_tables():
    c.execute('CREATE TABLE IF NOT EXISTS userstable(username TEXT, password TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS historytable(username TEXT, total_img INTEGER, blur_skip INTEGER, timestamp TEXT)')

def add_userdata(username, password):
    hashed = hashlib.sha256(str.encode(password)).hexdigest()
    c.execute('INSERT INTO userstable(username, password) VALUES (?,?)', (username, hashed))
    conn.commit()

def login_user(username, password):
    hashed = hashlib.sha256(str.encode(password)).hexdigest()
    c.execute('SELECT * FROM userstable WHERE username=? AND password=?', (username, hashed))
    return c.fetchall()

def add_history(username, total_img, blur_skip):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO historytable VALUES (?,?,?,?)', (username, total_img, blur_skip, now))
    conn.commit()

create_tables()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""

# ==========================================
# Global CSS
# ==========================================
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@400;600;700;800&display=swap');

:root {
    --bg-deep:     #060a12;
    --bg-surface:  #0d1422;
    --bg-raised:   #121c30;
    --bg-hover:    #182338;
    --border:      #1e2e45;
    --border-hi:   #2a4060;
    --accent:      #3b9eff;
    --accent-dim:  rgba(59,158,255,0.12);
    --accent-glow: rgba(59,158,255,0.22);
    --green:       #22d3a0;
    --red:         #f05252;
    --amber:       #f59e0b;
    --text-1:      #e8f0fa;
    --text-2:      #7a96b4;
    --text-3:      #3d5570;
    --font-ui:     'Syne', sans-serif;
    --font-mono:   'DM Mono', monospace;
    --r:           10px;
    --r-lg:        14px;
}

html, body, .stApp {
    background-color: var(--bg-deep) !important;
    color: var(--text-1);
    font-family: var(--font-ui);
}

/* ── HIDE STREAMLIT DEFAULT CHROME ── */
header[data-testid="stHeader"] {
    background-color: var(--bg-deep) !important;
    border-bottom: none !important;
    box-shadow: none !important;
}
[data-testid="stToolbar"]    { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
#MainMenu                    { visibility: hidden !important; }
footer                       { visibility: hidden !important; }
.appview-container           { background-color: var(--bg-deep) !important; }
.main > div                  { padding-top: 0.5rem !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar       { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-deep); }
::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 2px; }

/* ── SIDEBAR ──
   ใช้ padding บน outer เพื่อให้ inner card ดูลอย
   ไม่ใช้ overflow:hidden บน inner เพราะจะตัด option_menu dropdown
*/
[data-testid="stSidebar"] {
    background-color: var(--bg-deep) !important;
    border-right: none !important;
    padding: 12px 8px 12px 12px !important;
}
[data-testid="stSidebar"] > div:first-child {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    /* ไม่ใส่ overflow:hidden — ทำให้ menu items มองเห็นได้ทั้งหมด */
}
[data-testid="stSidebar"] > div { padding-top: 0 !important; }
[data-testid="stSidebar"] * { font-family: var(--font-ui) !important; }

/* ── SIDEBAR BRAND ── */
.sidebar-brand {
    padding: 20px 18px 16px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 6px;
}
.sidebar-brand .logo-mark {
    display: flex; align-items: center; gap: 10px; margin-bottom: 4px;
}
.sidebar-brand .hex {
    width: 30px; height: 30px;
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; color: var(--accent); font-weight: 700;
}
.sidebar-brand h2 {
    font-size: 14px !important; font-weight: 700 !important;
    color: var(--text-1) !important; margin: 0 !important;
}
.sidebar-brand p {
    font-family: var(--font-mono) !important; font-size: 9px !important;
    color: var(--text-3) !important; letter-spacing: 2px; margin: 0 !important;
}

/* ── USER BADGE ── */
.user-badge {
    margin: 6px 12px 4px;
    padding: 9px 12px;
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: var(--r);
    display: flex; align-items: center; gap: 10px;
}
.user-badge .avatar {
    width: 26px; height: 26px; border-radius: 50%;
    background: var(--accent-dim); border: 1px solid var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; color: var(--accent); flex-shrink: 0;
}
.user-badge .uname   { font-size: 12px; font-weight: 600; color: var(--text-1); }
.user-badge .ustatus { font-size: 10px; color: var(--green); letter-spacing: 1px; }

/* ── OPTION MENU ── */
div[data-testid="stSidebar"] .nav-link {
    font-size: 13px !important;
    border-radius: 10px !important;
    margin: 2px 8px !important;
    color: var(--text-2) !important;
    padding: 10px 14px !important;
    transition: all 0.18s !important;
}
div[data-testid="stSidebar"] .nav-link:hover {
    background: var(--bg-hover) !important;
    color: var(--text-1) !important;
}
div[data-testid="stSidebar"] .nav-link-selected {
    background: var(--accent-dim) !important;
    color: var(--accent) !important;
    border: 1px solid rgba(59,158,255,0.28) !important;
    font-weight: 600 !important;
}

/* ── COLLAPSE BUTTON ── */
[data-testid="collapsedControl"] {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border-hi) !important;
    border-radius: 8px !important;
    color: var(--accent) !important;
    margin: 12px !important;
}
[data-testid="collapsedControl"]:hover {
    border-color: var(--accent) !important;
    background: var(--accent-dim) !important;
}

/* ── PAGE HEADER ── */
.page-header {
    padding: 24px 0 18px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 22px;
}
.page-header .eyebrow {
    font-family: var(--font-mono); font-size: 10px; color: var(--accent);
    letter-spacing: 2.5px; text-transform: uppercase; margin-bottom: 6px;
}
.page-header h1 {
    font-size: 26px !important; font-weight: 800 !important;
    color: var(--text-1) !important; margin: 0 !important; letter-spacing: -0.4px;
}
.page-header .sub {
    font-size: 13px; color: var(--text-2); margin-top: 6px;
    font-family: var(--font-mono);
}

/* ── SECTION / COL LABELS ── */
.section-label {
    font-family: var(--font-mono); font-size: 10px; color: var(--text-3);
    letter-spacing: 2px; text-transform: uppercase;
    display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
}
.section-label::before {
    content: ''; width: 12px; height: 1px; background: var(--border-hi); display: inline-block;
}
.col-header {
    font-family: var(--font-mono); font-size: 10px; color: var(--text-3);
    letter-spacing: 2px; text-transform: uppercase;
    display: flex; align-items: center; gap: 6px;
    margin-bottom: 8px; padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}
.dot-status { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.dot-blue   { background: var(--accent); }
.dot-green  { background: var(--green); }
.dot-red    { background: var(--red); }

/* ── STAT PILLS ── */
.stat-row  { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
.stat-pill {
    flex: 1; min-width: 110px;
    background: var(--bg-raised); border: 1px solid var(--border);
    border-radius: var(--r); padding: 12px 14px; text-align: center;
}
.stat-pill .sp-label {
    font-family: var(--font-mono); font-size: 9px; color: var(--text-3);
    letter-spacing: 1.5px; text-transform: uppercase; display: block; margin-bottom: 4px;
}
.stat-pill .sp-val {
    font-size: 22px; font-weight: 700; color: var(--text-1); font-family: var(--font-mono);
}

/* ── BUTTONS ── */
.stButton > button {
    font-family: var(--font-ui) !important; font-size: 13px !important;
    font-weight: 600 !important; letter-spacing: 0.8px !important;
    border-radius: var(--r) !important;
    border: 1px solid var(--border-hi) !important;
    background: var(--bg-raised) !important;
    color: var(--text-1) !important;
    transition: all 0.2s !important; padding: 10px 20px !important;
}
.stButton > button:hover {
    border-color: var(--accent) !important;
    background: var(--accent-dim) !important;
    color: var(--accent) !important;
}
.stDownloadButton > button {
    font-family: var(--font-ui) !important; font-weight: 700 !important;
    font-size: 13px !important; letter-spacing: 0.8px !important;
    border-radius: var(--r) !important;
    background: var(--accent) !important;
    color: var(--bg-deep) !important; border: none !important;
    padding: 12px 20px !important;
}

/* ── INPUTS ── */
.stTextInput > label, .stMultiselect > label,
.stSlider > label, .stFileUploader > label, .stCheckbox > label {
    font-family: var(--font-mono) !important; font-size: 11px !important;
    color: var(--text-3) !important; letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
}
.stTextInput > div > div > input {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text-1) !important;
    font-family: var(--font-mono) !important;
    font-size: 13px !important; padding: 10px 14px !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-glow) !important;
}
.stTextInput > div > div > input::placeholder { color: var(--text-3) !important; }
[data-baseweb="select"] > div {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
}
[data-baseweb="tag"] {
    background: var(--accent-dim) !important;
    border: 1px solid rgba(59,158,255,0.3) !important;
    border-radius: 6px !important;
}
[data-baseweb="tag"] span { color: var(--accent) !important; font-size: 11px !important; }
[data-baseweb="menu"] {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border-hi) !important;
    border-radius: var(--r) !important;
}
[data-baseweb="option"] { background: transparent !important; color: var(--text-2) !important; }
[data-baseweb="option"]:hover { background: var(--bg-hover) !important; color: var(--text-1) !important; }

/* ── SLIDER ── */
[data-baseweb="slider"]           { padding: 6px 0 !important; }
[data-baseweb="track-background"] { background: var(--border-hi) !important; height: 3px !important; border-radius: 2px !important; }
[data-baseweb="track-fill"]       { background: var(--accent) !important; height: 3px !important; }
[data-baseweb="thumb"] {
    background: var(--bg-deep) !important;
    border: 2px solid var(--accent) !important;
    width: 16px !important; height: 16px !important;
    box-shadow: 0 0 0 4px var(--accent-glow) !important;
}

/* ── EXPANDER ── */
[data-testid="stExpander"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    margin-bottom: 16px !important; overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-family: var(--font-mono) !important; font-size: 11px !important;
    color: var(--text-2) !important; letter-spacing: 1.5px !important;
    text-transform: uppercase !important; padding: 14px 18px !important;
    background: var(--bg-surface) !important;
}
[data-testid="stExpander"] summary:hover { background: var(--bg-raised) !important; }
[data-testid="stExpander"] > div > div   { padding: 0 18px 18px !important; }

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; color: var(--text-3) !important;
    border: none !important; border-bottom: 2px solid transparent !important;
    font-family: var(--font-mono) !important; font-size: 11px !important;
    letter-spacing: 1.5px !important; text-transform: uppercase !important;
    padding: 12px 22px !important; border-radius: 0 !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text-1) !important; }
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 24px 0 0 !important; }

/* ── PROGRESS BAR ── */
.stProgress > div > div       { background: var(--bg-raised) !important; border-radius: 2px !important; height: 3px !important; }
.stProgress > div > div > div { background: var(--accent) !important; height: 3px !important; }

/* ── ALERTS ── */
[data-testid="stAlert"] {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    font-family: var(--font-mono) !important; font-size: 13px !important;
}
[data-testid="stAlert"][data-type="success"] { border-left: 3px solid var(--green) !important; }
[data-testid="stAlert"][data-type="error"]   { border-left: 3px solid var(--red) !important; }
[data-testid="stAlert"][data-type="warning"] { border-left: 3px solid var(--amber) !important; }
[data-testid="stAlert"][data-type="info"]    { border-left: 3px solid var(--accent) !important; }

/* ── MISC ── */
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 20px 0 !important; }
[data-testid="stFileUploaderDropzone"] {
    background: var(--bg-surface) !important;
    border: 1.5px dashed var(--border-hi) !important;
    border-radius: var(--r-lg) !important; padding: 24px !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--accent) !important; background: var(--bg-raised) !important;
}
[data-testid="stFileUploaderDropzone"] button {
    background: var(--accent-dim) !important; border: 1px solid var(--accent) !important;
    color: var(--accent) !important; border-radius: var(--r) !important;
    font-family: var(--font-ui) !important; font-size: 12px !important; font-weight: 600 !important;
}
video {
    border-radius: var(--r) !important;
    border: 1px solid var(--border) !important;
    width: 100% !important;
}
[data-testid="stImage"] img { border-radius: var(--r) !important; border: 1px solid var(--border) !important; }
.stMarkdown p { color: var(--text-2) !important; font-size: 13px !important; font-family: var(--font-mono) !important; line-height: 1.7 !important; }
.main .block-container { padding: 0 2rem 2rem !important; max-width: 1200px; }
.status-text { font-family: var(--font-mono); font-size: 11px; color: var(--accent); letter-spacing: 1px; padding: 8px 0; }
</style>
"""

# ==========================================
# Auth Page
# ==========================================
def show_auth_page():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:32px 0 28px;border-bottom:1px solid var(--border);margin-bottom:28px;">
            <div style="width:48px;height:48px;background:var(--accent-dim);border:1px solid rgba(59,158,255,0.4);
                        border-radius:12px;display:flex;align-items:center;justify-content:center;
                        font-size:22px;margin:0 auto 16px;">⬡</div>
            <h1 style="font-size:22px;font-weight:800;color:var(--text-1);margin:0 0 4px;">AI-Dataset Pro</h1>
            <div style="font-family:var(--font-mono);font-size:10px;color:var(--text-3);letter-spacing:2.5px;">
                COMPUTER VISION PLATFORM
            </div>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["LOGIN", "REGISTER"])
        with tab1:
            login_user_input = st.text_input("Username", key="login_user", placeholder="your username")
            login_pass_input = st.text_input("Password", type="password", key="login_pass", placeholder="••••••••")
            if st.button("INITIATE LOGIN", use_container_width=True, key="btn_login"):
                if login_user_input and login_pass_input:
                    if login_user(login_user_input, login_pass_input):
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
            is_strong = False
            if new_pass:
                score = sum([
                    len(new_pass) >= 8,
                    bool(re.search(r"[A-Z]", new_pass)),
                    bool(re.search(r"[a-z]", new_pass)),
                    bool(re.search(r"[0-9]", new_pass)),
                    bool(re.search(r"[@$!%*?&_#^-]", new_pass))
                ])
                clr = "var(--red)" if score <= 2 else "var(--amber)" if score <= 4 else "var(--green)"
                lbl = "WEAK" if score <= 2 else "FAIR" if score <= 4 else "STRONG"
                st.markdown(f"""
                <div style="margin-top:-10px;margin-bottom:15px;">
                    <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);
                                font-size:10px;color:var(--text-2);margin-bottom:5px;">
                        <span>SECURITY LEVEL</span>
                        <span style="color:{clr};font-weight:bold;">{lbl}</span>
                    </div>
                    <div style="width:100%;height:3px;background:var(--bg-raised);border-radius:2px;">
                        <div style="width:{(score/5)*100}%;height:100%;background:{clr};border-radius:2px;transition:all 0.3s;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if score < 5:
                    st.markdown('<div style="font-family:var(--font-mono);font-size:11px;color:var(--text-3);margin-bottom:12px;">Require: 8+ chars, A-Z, a-z, 0-9, special char</div>', unsafe_allow_html=True)
                else:
                    is_strong = True

            if st.button("CREATE ACCOUNT", use_container_width=True, key="btn_register"):
                if new_user and new_pass:
                    if not is_strong:
                        st.error("Please use a stronger password")
                    else:
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

    with st.sidebar:
        init = st.session_state['username'][0].upper() if st.session_state['username'] else "?"
        st.markdown(f"""
        <div class="sidebar-brand">
            <div class="logo-mark">
                <div class="hex">⬡</div>
                <h2>AI-Dataset Pro</h2>
            </div>
            <p>COMPUTER VISION · v6.0</p>
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
                "icon": {"font-size": "14px", "color": "#7a96b4"},
                "nav-link": {
                    "font-size": "13px",
                    "font-weight": "500",
                    "color": "#7a96b4",
                    "border-radius": "10px",
                    "margin": "2px 8px",
                    "padding": "10px 14px",
                    "font-family": "'Syne', sans-serif",
                },
                "nav-link-selected": {
                    "background-color": "rgba(59,158,255,0.12)",
                    "color": "#3b9eff",
                    "border": "1px solid rgba(59,158,255,0.28)",
                    "font-weight": "600",
                },
            }
        )
        if selected_menu == "Logout":
            st.session_state.clear()
            st.rerun()

    # ── AI ENGINE ──
    if selected_menu == "AI Engine":
        st.markdown("""
        <div class="page-header">
            <div class="eyebrow">MODULE / AI ENGINE</div>
            <h1>Dataset Generation</h1>
            <div class="sub">Extract, label, filter & augment training data from video</div>
        </div>
        """, unsafe_allow_html=True)

        @st.cache_resource
        def load_model():
            return YOLO('yolov8n.pt')
        model = load_model()
        available_classes = model.names

        with st.expander("⚙  NEURAL NETWORK & SYSTEM CONFIGURATION"):
            col1, col2, col3, col4 = st.columns(4, gap="medium")
            with col1:
                st.markdown('<p style="font-family:var(--font-mono);font-size:11px;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;">AI TARGETS</p>', unsafe_allow_html=True)
                selected_class_names = st.multiselect("Detection Targets", list(available_classes.values()), default=["person", "car"], label_visibility="collapsed")
                selected_class_ids = [k for k, v in available_classes.items() if v in selected_class_names]
                st.markdown('<p style="font-family:var(--font-mono);font-size:11px;color:var(--text-3);letter-spacing:1px;margin-top:10px;margin-bottom:6px;">CONFIDENCE (%)</p>', unsafe_allow_html=True)
                conf_threshold = st.slider("Min Confidence", 10, 90, 25, 5, label_visibility="collapsed") / 100.0
            with col2:
                st.markdown('<p style="font-family:var(--font-mono);font-size:11px;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;">DATASET SPLIT</p>', unsafe_allow_html=True)
                split_ratio = st.slider("Train Split (%)", 50, 95, 80)
                frame_skip  = st.slider("Frame Skip Interval", 1, 30, 10)
            with col3:
                st.markdown('<p style="font-family:var(--font-mono);font-size:11px;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;">DATA AUGMENTATION</p>', unsafe_allow_html=True)
                do_flip   = st.checkbox("Horizontal Flip")
                do_bright = st.checkbox("Brightness Boost")
                do_noise  = st.checkbox("Add Noise")
            with col4:
                st.markdown('<p style="font-family:var(--font-mono);font-size:11px;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;">QUALITY CONTROL</p>', unsafe_allow_html=True)
                do_blur_filter = st.checkbox("Blur Filter", value=True)
                blur_threshold = st.slider("Blur Threshold", 20, 200, 60)

        st.markdown('<div class="section-label">Media Source</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Drop video file here", type=['mp4', 'avi', 'mov'], label_visibility="collapsed")

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
                st.markdown('<div class="col-header"><span class="dot-status dot-green"></span>AI VISION PREVIEW</div>', unsafe_allow_html=True)
                image_preview = st.empty()
                blur_warning  = st.empty()

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("▶  EXECUTE AI PROCESSING", use_container_width=True):
                output_folder = "dataset_workspace"
                if os.path.exists(output_folder): shutil.rmtree(output_folder)
                for f in ['images/train', 'images/val', 'labels/train', 'labels/val']:
                    os.makedirs(os.path.join(output_folder, f))

                cap          = cv2.VideoCapture(video_path)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                progress_bar = st.progress(0)
                status_text  = st.empty()

                frame_count        = 0
                skipped_blur_count = 0
                dataset_records    = []
                class_counts = {n: 0 for n in selected_class_names} if selected_class_names else {v: 0 for v in available_classes.values()}

                def save_data(img, boxes, modifier, is_flipped=False):
                    subset    = "train" if random.random() < (split_ratio / 100.0) else "val"
                    base_name = f"frame_{frame_count:06d}_{modifier}"
                    cv2.imwrite(f"{output_folder}/images/{subset}/{base_name}.jpg", img)
                    with open(f"{output_folder}/labels/{subset}/{base_name}.txt", 'w') as lf:
                        for box in boxes:
                            cid   = int(box.cls)
                            cname = available_classes[cid]
                            class_counts[cname] += 1
                            new_id = selected_class_names.index(cname) if selected_class_names else cid
                            x, y, w, h = box.xywhn[0]
                            if is_flipped: x = 1.0 - x
                            lf.write(f"{new_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")
                    dataset_records.append({"subset": subset, "file": base_name})

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret: break
                    if frame_count % frame_skip == 0:
                        if do_blur_filter:
                            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            score = cv2.Laplacian(gray, cv2.CV_64F).var()
                            if score < blur_threshold:
                                skipped_blur_count += 1
                                blur_warning.markdown(f'<div style="color:var(--red);font-size:12px;font-family:var(--font-mono);">BLUR DETECTED (score:{score:.1f}) — FRAME SKIPPED</div>', unsafe_allow_html=True)
                                frame_count += 1
                                continue
                            else:
                                blur_warning.empty()

                        results = model(frame, classes=selected_class_ids if selected_class_ids else None, conf=conf_threshold, verbose=False)
                        boxes = results[0].boxes
                        if len(boxes) > 0:
                            save_data(frame, boxes, "original")
                            if do_flip:   save_data(cv2.flip(frame, 1), boxes, "flip", is_flipped=True)
                            if do_bright: save_data(cv2.convertScaleAbs(frame, alpha=1.2, beta=30), boxes, "bright")
                            if do_noise:  save_data(cv2.add(frame, np.random.randint(0, 50, frame.shape, dtype='uint8')), boxes, "noise")
                            annotated = results[0].plot()
                            image_preview.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_container_width=True)

                    frame_count += 1
                    progress_bar.progress(min(frame_count / total_frames, 1.0))
                    status_text.markdown(f'<div class="status-text">PROCESSING  {frame_count} / {total_frames}  FRAMES | EXTRACTED: {len(dataset_records)}</div>', unsafe_allow_html=True)
                cap.release()
                blur_warning.empty()

                classes_for_yaml = selected_class_names if selected_class_names else list(available_classes.values())
                with open(os.path.join(output_folder, "data.yaml"), 'w', encoding='utf-8') as yf:
                    yf.write("train: images/train\nval: images/val\n\n")
                    yf.write(f"nc: {len(classes_for_yaml)}\n")
                    yf.write(f"names: [{', '.join([repr(n) for n in classes_for_yaml])}]\n")

                add_history(st.session_state['username'], len(dataset_records), skipped_blur_count)

                train_c = sum(1 for r in dataset_records if r['subset'] == 'train')
                val_c   = len(dataset_records) - train_c
                total_labels = sum(class_counts.values())

                st.markdown(f"""
                <div class="stat-row">
                    <div class="stat-pill"><span class="sp-label" style="color:var(--accent);">Good Images</span><span class="sp-val">{len(dataset_records)}</span></div>
                    <div class="stat-pill"><span class="sp-label" style="color:var(--red);">Blurry Skipped</span><span class="sp-val">{skipped_blur_count}</span></div>
                    <div class="stat-pill"><span class="sp-label">Train</span><span class="sp-val">{train_c}</span></div>
                    <div class="stat-pill"><span class="sp-label">Val</span><span class="sp-val">{val_c}</span></div>
                    <div class="stat-pill"><span class="sp-label">Labels</span><span class="sp-val">{total_labels}</span></div>
                </div>
                """, unsafe_allow_html=True)

                st.divider()
                st.success("Dataset generation & QC complete")

                zip_filename = "ai_dataset.zip"
                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                    for root, dirs, files in os.walk(output_folder):
                        for file in files:
                            zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), output_folder))
                with open(zip_filename, "rb") as fp:
                    st.download_button("⬇  DOWNLOAD DATASET", fp, "ai_dataset_pro.zip", "application/zip", use_container_width=True)
                os.remove(video_path); shutil.rmtree(output_folder); os.remove(zip_filename)

    # ── DASHBOARD ──
    elif selected_menu == "Dashboard":
        st.markdown("""
        <div class="page-header">
            <div class="eyebrow">MODULE / OVERVIEW</div>
            <h1>System Dashboard</h1>
            <div class="sub">Real-time analytics & user activity</div>
        </div>
        """, unsafe_allow_html=True)

        c.execute('SELECT COUNT(*) FROM userstable')
        total_users = c.fetchone()[0]
        df_history  = pd.read_sql_query("SELECT * FROM historytable ORDER BY timestamp DESC", conn)
        total_runs    = len(df_history)
        total_images  = int(df_history['total_img'].sum()) if not df_history.empty else 0
        total_skipped = int(df_history['blur_skip'].sum()) if not df_history.empty else 0

        st.markdown(f"""
        <div class="stat-row" style="margin-bottom:24px;">
            <div class="stat-pill"><span class="sp-label">Registered Users</span><span class="sp-val">{total_users}</span></div>
            <div class="stat-pill"><span class="sp-label">AI Executions</span><span class="sp-val">{total_runs}</span></div>
            <div class="stat-pill"><span class="sp-label" style="color:var(--green);">Images Generated</span><span class="sp-val">{total_images:,}</span></div>
            <div class="stat-pill"><span class="sp-label" style="color:var(--red);">Blurry Skipped</span><span class="sp-val">{total_skipped:,}</span></div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([2, 1], gap="large")
        with col1:
            st.markdown('<div class="section-label">AI Generation Trend</div>', unsafe_allow_html=True)
            if not df_history.empty:
                chart_data = df_history[['timestamp', 'total_img']].copy()
                chart_data['timestamp'] = pd.to_datetime(chart_data['timestamp']).dt.strftime('%H:%M')
                st.bar_chart(chart_data.set_index('timestamp'), color="#3b9eff")
            else:
                st.markdown("""
                <div style="background:var(--bg-surface);border:1px solid var(--border);
                            border-radius:var(--r-lg);padding:40px;text-align:center;">
                    <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-3);letter-spacing:2px;">NO DATA YET</div>
                    <div style="font-size:13px;color:var(--text-2);margin-top:8px;">Run the AI Engine to see trends here</div>
                </div>
                """, unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="section-label">Recent Activity</div>', unsafe_allow_html=True)
            if not df_history.empty:
                display_df = df_history[['username', 'total_img', 'timestamp']].head(8).copy()
                display_df.columns = ['User', 'Images', 'Time']
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.markdown('<div style="font-family:var(--font-mono);font-size:12px;color:var(--text-3);">No recent activity</div>', unsafe_allow_html=True)


# ── ROUTER ──
if not st.session_state['logged_in']:
    show_auth_page()
else:
    show_main_app()