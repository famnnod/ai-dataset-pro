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
# Page Config (บังคับ Sidebar ให้ซ่อนตั้งแต่เริ่ม)
# ==========================================
st.set_page_config(
    page_title="AI-Dataset Pro",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# Database System
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
# Global CSS (Modern Clean & Orange Theme - Top Menu)
# ==========================================
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg-deep:     #f8fafc; 
    --bg-surface:  #ffffff; 
    --bg-raised:   #f1f5f9; 
    --bg-hover:    #e2e8f0;
    --border:      #e2e8f0; 
    --border-hi:   #cbd5e1;
    --accent:      #ff6b00; 
    --accent-dim:  rgba(255, 107, 0, 0.1); 
    --accent-glow: rgba(255, 107, 0, 0.2);
    --green:       #10b981; 
    --red:         #ef4444; 
    --amber:       #f59e0b; 
    --text-1:      #000000; 
    --text-2:      #111827; 
    --text-3:      #374151; 
    --font-ui:     'Inter', sans-serif;
    --font-mono:   'DM Mono', monospace;
    --r:           10px;
    --r-lg:        16px;
}

html, body, .stApp { background-color: var(--bg-deep) !important; color: var(--text-1) !important; font-family: var(--font-ui); }

/* ── ซ่อน Sidebar และเครื่องมือ Streamlit ── */
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
header[data-testid="stHeader"] { background-color: transparent !important; border-bottom: none !important; box-shadow: none !important; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
.appview-container { background-color: var(--bg-deep) !important; } 
.main > div { padding-top: 1.5rem !important; }
::-webkit-scrollbar { width: 6px; height: 6px; } ::-webkit-scrollbar-track { background: transparent; } ::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 3px; }

/* ── TOP HEADER (Brand & User) ── */
.top-brand { display: flex; align-items: center; gap: 12px; }
.top-brand .hex { width: 36px; height: 36px; background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.3); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; color: var(--accent); font-weight: 800; }
.top-brand h2 { font-size: 20px !important; font-weight: 800 !important; color: var(--text-1) !important; margin: 0 !important; letter-spacing: -0.5px; }
.top-user { display: flex; align-items: center; gap: 12px; justify-content: flex-end; padding: 4px 0;}
.top-user .avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--accent); color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; box-shadow: 0 2px 4px rgba(255,107,0,0.3); }
.top-user .uname { font-size: 14px; font-weight: 800; color: var(--text-1) !important; line-height: 1.2; text-transform: uppercase;}
.top-user .ustatus { font-size: 11px; font-weight: 700; color: var(--green); letter-spacing: 0.5px; }

/* ── PAGE HEADER ── */
.page-header { padding: 12px 0 24px; border-bottom: 2px solid var(--border); margin-bottom: 32px; }
.page-header .eyebrow { font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; }
.page-header h1 { font-size: 32px !important; font-weight: 800 !important; color: var(--text-1) !important; margin: 0 !important; letter-spacing: -1px; line-height: 1.2 !important; }
.page-header .sub { font-size: 15px; font-weight: 500; color: var(--text-2); margin-top: 8px; }

/* ── LABELS & TEXTS ── */
.section-label { font-family: var(--font-ui); font-size: 12px; font-weight: 800; color: var(--text-1) !important; letter-spacing: 1px; text-transform: uppercase; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.section-label::before { content: ''; width: 16px; height: 3px; background: var(--accent); display: inline-block; border-radius: 2px; }
.col-header { font-family: var(--font-ui); font-size: 11px; font-weight: 800; color: var(--text-1) !important; letter-spacing: 1px; text-transform: uppercase; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.dot-status { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-blue   { background: var(--text-1); } .dot-green  { background: var(--accent); } .dot-red    { background: var(--red); }

/* ── STAT PILLS ── */
.stat-row  { display: flex; gap: 16px; margin-top: 16px; flex-wrap: wrap; }
.stat-pill { flex: 1; min-width: 130px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 20px 16px; text-align: left; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); transition: transform 0.2s; }
.stat-pill:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); }
.stat-pill .sp-label { font-family: var(--font-ui); font-size: 11px; font-weight: 700; color: var(--text-2); letter-spacing: 0.5px; text-transform: uppercase; display: block; margin-bottom: 8px; }
.stat-pill .sp-val { font-size: 28px; font-weight: 800; color: var(--text-1); letter-spacing: -0.5px;}

/* ── BUTTONS ── */
.stButton > button { font-family: var(--font-ui) !important; font-size: 14px !important; font-weight: 700 !important; border-radius: 8px !important; border: 1px solid var(--border-hi) !important; background: var(--bg-surface) !important; color: var(--text-1) !important; transition: all 0.2s ease !important; padding: 10px 24px !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; }
.stButton > button:hover { border-color: var(--accent) !important; background: var(--bg-raised) !important; color: var(--accent) !important; }
.stDownloadButton > button { font-family: var(--font-ui) !important; font-weight: 800 !important; font-size: 14px !important; border-radius: 8px !important; background: var(--accent) !important; color: white !important; border: none !important; padding: 12px 24px !important; box-shadow: 0 4px 6px rgba(255,107,0,0.2) !important; }
.stDownloadButton > button:hover { opacity: 0.9 !important; transform: translateY(-1px) !important; }

/* ── INPUTS & CHECKBOXES ── */
.stTextInput > label, .stMultiselect > label, .stSlider > label, .stFileUploader > label { font-family: var(--font-ui) !important; font-size: 12px !important; font-weight: 700 !important; color: var(--text-1) !important; margin-bottom: 8px !important; }
.stCheckbox > label span { font-weight: 600 !important; color: var(--text-1) !important; }
.stTextInput > div > div > input { background: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; border-radius: 8px !important; color: var(--text-1) !important; font-size: 14px !important; padding: 12px 16px !important; transition: all 0.2s !important; }
.stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-dim) !important; }
.stTextInput > div > div > input::placeholder { color: var(--text-3) !important; }
[data-baseweb="select"] > div { background: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; border-radius: 8px !important; transition: all 0.2s !important; }
[data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-dim) !important;}
[data-baseweb="tag"] { background: var(--accent-dim) !important; border: none !important; border-radius: 6px !important; padding: 4px 8px !important; }
[data-baseweb="tag"] span { color: var(--accent) !important; font-size: 12px !important; font-weight: 700 !important; }

/* ── EXPANDER ── */
[data-testid="stExpander"] { background: var(--bg-surface) !important; border: 1px solid var(--border) !important; border-radius: var(--r-lg) !important; margin-bottom: 24px !important; overflow: hidden !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02) !important; }
[data-testid="stExpander"] summary { font-family: var(--font-ui) !important; font-size: 13px !important; font-weight: 700 !important; color: var(--text-1) !important; padding: 16px 24px !important; background: var(--bg-raised) !important; border-bottom: 1px solid var(--border) !important; }
[data-testid="stExpander"] summary:hover { background: var(--bg-hover) !important; }
[data-testid="stExpander"] > div > div   { padding: 24px !important; }

/* ── TABS & PROGRESS ── */
.stTabs [data-baseweb="tab-list"] { background: transparent !important; border-bottom: 1px solid var(--border) !important; gap: 16px !important; }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: var(--text-3) !important; border: none !important; border-bottom: 3px solid transparent !important; font-family: var(--font-ui) !important; font-size: 13px !important; font-weight: 700 !important; letter-spacing: 0.5px !important; text-transform: uppercase !important; padding: 12px 4px !important; border-radius: 0 !important; transition: color 0.2s; }
.stTabs [data-baseweb="tab"]:hover { color: var(--text-1) !important; }
.stTabs [aria-selected="true"] { color: var(--accent) !important; border-bottom: 3px solid var(--accent) !important; font-weight: 800 !important; }
.stTabs [data-baseweb="tab-panel"] { padding: 32px 0 0 !important; }
.stProgress > div > div { background: var(--border) !important; border-radius: 4px !important; height: 6px !important; }
.stProgress > div > div > div { background: var(--accent) !important; height: 6px !important; border-radius: 4px !important; }

/* ── ALERTS & MISC ── */
[data-testid="stAlert"] { background: var(--bg-surface) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; font-family: var(--font-ui) !important; font-size: 14px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;}
[data-testid="stAlert"][data-type="success"] { border-left: 4px solid var(--green) !important; }
[data-testid="stAlert"][data-type="error"]   { border-left: 4px solid var(--red) !important; }
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 32px 0 !important; }
[data-testid="stFileUploaderDropzone"] { background: var(--bg-surface) !important; border: 2px dashed var(--border-hi) !important; border-radius: var(--r-lg) !important; padding: 40px 24px !important; transition: all 0.2s ease !important; }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent) !important; background: var(--accent-dim) !important; }
[data-testid="stFileUploaderDropzone"] button { background: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; color: var(--text-1) !important; border-radius: 8px !important; font-family: var(--font-ui) !important; font-size: 13px !important; font-weight: 700 !important; padding: 8px 16px !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;}
video { border-radius: var(--r-lg) !important; border: 1px solid var(--border) !important; width: 100% !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important; }
[data-testid="stImage"] img { border-radius: var(--r-lg) !important; border: 1px solid var(--border) !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important;}
.stMarkdown p { color: var(--text-1) !important; font-size: 15px !important; font-family: var(--font-ui) !important; font-weight: 500 !important; line-height: 1.6 !important; }
.main .block-container { padding: 0 2rem 2rem !important; max-width: 1200px; }
.status-text { font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: var(--text-2); letter-spacing: 0.5px; padding: 12px 0; }
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
        <div style="text-align:center;padding:32px 0 28px;border-bottom:2px solid var(--border);margin-bottom:28px;">
            <div style="width:48px;height:48px;background:var(--accent-dim);border:1px solid rgba(255,107,0,0.3);
                        border-radius:12px;display:flex;align-items:center;justify-content:center;
                        font-size:24px;margin:0 auto 16px;color:var(--accent);font-weight:800;">⬡</div>
            <h1 style="font-size:26px;font-weight:800;color:var(--text-1);margin:0 0 4px;letter-spacing:-0.5px;">AI-Dataset Pro</h1>
            <div style="font-family:var(--font-mono);font-size:10px;color:var(--text-3);letter-spacing:2.5px;font-weight:600;">
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
                                font-size:10px;color:var(--text-2);margin-bottom:5px;font-weight:600;">
                        <span>SECURITY LEVEL</span>
                        <span style="color:{clr};font-weight:800;">{lbl}</span>
                    </div>
                    <div style="width:100%;height:4px;background:var(--border);border-radius:2px;">
                        <div style="width:{(score/5)*100}%;height:100%;background:{clr};border-radius:2px;transition:all 0.3s;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if score < 5:
                    st.markdown('<div style="font-family:var(--font-ui);font-size:12px;color:var(--text-3);margin-bottom:12px;font-weight:500;">Require: 8+ chars, A-Z, a-z, 0-9, special char</div>', unsafe_allow_html=True)
                else:
                    is_strong = True

            if st.button("CREATE ACCOUNT", use_container_width=True, key="btn_register"):
                if new_user and new_pass:
                    if not is_strong:
                        st.error("Please use a stronger password (STRONG level required)")
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

    # 📌 1. Top Header (Logo & User Profile)
    init = st.session_state['username'][0].upper() if st.session_state['username'] else "?"
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"""
        <div class="top-brand">
            <div class="hex">⬡</div>
            <h2>AI-Dataset Pro</h2>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="top-user">
            <div style="text-align: right;">
                <div class="uname">{st.session_state['username']}</div>
                <div class="ustatus">● ACTIVE SESSION</div>
            </div>
            <div class="avatar">{init}</div>
        </div>
        """, unsafe_allow_html=True)
    st.write("") 

    # 📌 2. Top Navigation Menu แนวนอน
    is_admin = (st.session_state['username'].lower() == 'admin')
    
    selected_menu = option_menu(
        menu_title=None,
        options=["Dashboard", "AI Engine", "Logout"],
        icons=["grid-1x2", "cpu", "box-arrow-right"],
        default_index=1,
        orientation="horizontal",
        styles={
            "container": {
                "background-color": "var(--bg-surface)", 
                "border": "1px solid var(--border)", 
                "border-radius": "12px", 
                "padding": "5px", 
                "box-shadow": "0 4px 6px -1px rgba(0,0,0,0.02)",
                "margin-bottom": "30px"
            },
            "icon": {"color": "var(--text-3)", "font-size": "16px"},
            "nav-link": {
                "font-size": "14px", 
                "font-weight": "700", 
                "color": "var(--text-2)", 
                "font-family": "var(--font-ui)", 
                "border-radius": "8px", 
                "padding": "10px",
                "margin": "0 4px"
            },
            "nav-link-selected": {
                "background-color": "var(--accent-dim)", 
                "color": "var(--accent)", 
                "border": "1px solid rgba(255,107,0,0.2)"
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
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">AI TARGETS</p>', unsafe_allow_html=True)
                selected_class_names = st.multiselect("Detection Targets", list(available_classes.values()), default=["person", "car"], label_visibility="collapsed")
                selected_class_ids = [k for k, v in available_classes.items() if v in selected_class_names]
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-top:10px;margin-bottom:6px;text-transform:uppercase;">CONFIDENCE (%)</p>', unsafe_allow_html=True)
                conf_threshold = st.slider("Min Confidence", 10, 90, 25, 5, label_visibility="collapsed") / 100.0
            with col2:
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">DATASET SPLIT</p>', unsafe_allow_html=True)
                split_ratio = st.slider("Train Split (%)", 50, 95, 80)
                frame_skip  = st.slider("Frame Skip Interval", 1, 30, 5)
            with col3:
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">DATA AUGMENTATION</p>', unsafe_allow_html=True)
                do_flip   = st.checkbox("Horizontal Flip")
                do_bright = st.checkbox("Brightness Boost")
                do_noise  = st.checkbox("Add Noise")
            with col4:
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">QUALITY CONTROL</p>', unsafe_allow_html=True)
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
                                blur_warning.markdown(f'<div style="color:var(--red);font-size:13px;font-family:var(--font-ui);font-weight:700;">BLUR DETECTED (score:{score:.1f}) — FRAME SKIPPED</div>', unsafe_allow_html=True)
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
                    <div class="stat-pill"><span class="sp-label">Train Data</span><span class="sp-val">{train_c}</span></div>
                    <div class="stat-pill"><span class="sp-label">Val Data</span><span class="sp-val">{val_c}</span></div>
                    <div class="stat-pill"><span class="sp-label">Total Labels</span><span class="sp-val">{total_labels}</span></div>
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
                    st.download_button("⬇  DOWNLOAD DATASET (PRO)", fp, "ai_dataset_pro.zip", "application/zip", use_container_width=True)
                os.remove(video_path); shutil.rmtree(output_folder); os.remove(zip_filename)

    # ── DASHBOARD PAGE (Personalized) ────────────────────────
    elif selected_menu == "Dashboard":
        title_text = "System Admin Dashboard" if is_admin else "Personal Dashboard"
        sub_text = "Real-time global analytics & user activity" if is_admin else "Your personal AI generation statistics"
        
        st.markdown(f"""
        <div class="page-header">
            <div class="eyebrow">MODULE / OVERVIEW</div>
            <h1>{title_text}</h1>
            <div class="sub">{sub_text}</div>
        </div>
        """, unsafe_allow_html=True)

        if is_admin:
            c.execute('SELECT COUNT(*) FROM userstable')
            total_users = c.fetchone()[0]
            df_history  = pd.read_sql_query("SELECT * FROM historytable ORDER BY timestamp DESC", conn)
        else:
            total_users = 1
            query = "SELECT * FROM historytable WHERE username=? ORDER BY timestamp DESC"
            df_history = pd.read_sql_query(query, conn, params=(st.session_state['username'],))

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
                st.bar_chart(chart_data.set_index('timestamp'), color="#ff6b00")
            else:
                st.markdown("""
                <div style="background:var(--bg-surface);border:1px solid var(--border);
                            border-radius:var(--r-lg);padding:40px;text-align:center;">
                    <div style="font-family:var(--font-ui);font-size:13px;font-weight:700;color:var(--text-3);letter-spacing:1px;">NO DATA YET</div>
                    <div style="font-size:14px;color:var(--text-2);margin-top:8px;">Run the AI Engine to see your trends here</div>
                </div>
                """, unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="section-label">Recent Activity</div>', unsafe_allow_html=True)
            if not df_history.empty:
                display_df = df_history[['username', 'total_img', 'timestamp']].head(8).copy()
                display_df.columns = ['User', 'Images', 'Time']
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.markdown('<div style="font-family:var(--font-ui);font-size:13px;color:var(--text-3);font-weight:500;">No recent activity</div>', unsafe_allow_html=True)

# ── ROUTER ──
if not st.session_state['logged_in']:
    show_auth_page()
else:
    show_main_app()