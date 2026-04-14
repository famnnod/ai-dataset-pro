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
import requests
from ultralytics import YOLO
from streamlit_option_menu import option_menu

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(
    page_title="AI-Dataset Pro",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. Database & Security Functions
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

def send_telegram_notify(bot_token, chat_id, message):
    if not bot_token or not chat_id: return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=data, timeout=5)
    except Exception:
        pass

create_tables()

if 'logged_in'       not in st.session_state: st.session_state['logged_in']       = False
if 'username'        not in st.session_state: st.session_state['username']         = ""
if 'reg_attempts'    not in st.session_state: st.session_state['reg_attempts']     = 0
if 'reg_last_time'   not in st.session_state: st.session_state['reg_last_time']    = datetime.datetime.now()
if 'just_registered' not in st.session_state: st.session_state['just_registered']  = False

# ==========================================
# 3. Global CSS (Modern Clean & Orange Theme)
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
    --text-1:      #0f172a;
    --text-2:      #1e293b;
    --text-3:      #475569;
    --font-ui:     'Inter', sans-serif;
    --font-mono:   'DM Mono', monospace;
    --r:           10px;
    --r-lg:        16px;
}

html, body, .stApp { background-color: var(--bg-deep) !important; color: var(--text-1) !important; font-family: var(--font-ui); }

/* ซ่อน Sidebar และ Streamlit Chrome */
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
header[data-testid="stHeader"] { background-color: transparent !important; border-bottom: none !important; box-shadow: none !important; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
.appview-container { background-color: var(--bg-deep) !important; }
.main > div { padding-top: 1.5rem !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 3px; }

/* ── TOP HEADER ── */
.top-brand { display: flex; align-items: center; gap: 12px; }
.top-brand .hex { width: 36px; height: 36px; background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.3); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; color: var(--accent); font-weight: 800; }
.top-brand h2 { font-size: 20px !important; font-weight: 800 !important; color: var(--text-1) !important; margin: 0 !important; letter-spacing: -0.5px; }
.top-user { display: flex; align-items: center; gap: 12px; justify-content: flex-end; padding: 4px 0; }
.top-user .avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--accent); color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; box-shadow: 0 2px 4px rgba(255,107,0,0.3); }
.top-user .uname { font-size: 14px; font-weight: 800; color: var(--text-1) !important; line-height: 1.2; text-transform: uppercase; }
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
.dot-blue  { background: var(--text-1); }
.dot-green { background: var(--accent); }
.dot-red   { background: var(--red); }

/* ── STAT PILLS ── */
.stat-row  { display: flex; gap: 16px; margin-top: 16px; flex-wrap: wrap; }
.stat-pill { flex: 1; min-width: 130px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 20px 16px; text-align: left; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); transition: transform 0.2s; }
.stat-pill:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); }
.stat-pill .sp-label { font-family: var(--font-ui); font-size: 11px; font-weight: 700; color: var(--text-2); letter-spacing: 0.5px; text-transform: uppercase; display: block; margin-bottom: 8px; }
.stat-pill .sp-val { font-size: 28px; font-weight: 800; color: var(--text-1); letter-spacing: -0.5px; }

/* ── BUTTONS & OTHERS ── */
.stButton > button { font-family: var(--font-ui) !important; font-size: 14px !important; font-weight: 700 !important; border-radius: 8px !important; border: 1px solid var(--border-hi) !important; background: var(--bg-surface) !important; color: var(--text-1) !important; transition: all 0.2s ease !important; padding: 10px 24px !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; }
.stButton > button:hover { border-color: var(--accent) !important; background: var(--bg-raised) !important; color: var(--accent) !important; }
.stDownloadButton > button { font-family: var(--font-ui) !important; font-weight: 800 !important; font-size: 14px !important; border-radius: 8px !important; background: var(--accent) !important; color: white !important; border: none !important; padding: 12px 24px !important; box-shadow: 0 4px 6px rgba(255,107,0,0.2) !important; }
.stDownloadButton > button:hover { opacity: 0.9 !important; transform: translateY(-1px) !important; }
video { border-radius: 12px !important; border: 1px solid var(--border) !important; width: 100% !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important; }
[data-testid="stImage"] img { border-radius: 12px !important; border: 1px solid var(--border) !important; width: 100% !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important;}
</style>
"""

# ==========================================
# 4. Authentication UI
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

        if st.session_state.get('just_registered'):
            tab1, tab2 = st.tabs(["LOGIN", "REGISTER"])
            with tab1:
                st.success("✅ Account created successfully — please log in")
                st.session_state['just_registered'] = False
                login_user_input = st.text_input("Username", key="login_user_post_reg", placeholder="your username")
                login_pass_input = st.text_input("Password", type="password", key="login_pass_post_reg", placeholder="••••••••")
                if st.button("INITIATE LOGIN", use_container_width=True, key="btn_login_post_reg"):
                    if login_user_input and login_pass_input:
                        if login_user(login_user_input, login_pass_input):
                            st.session_state['logged_in'] = True
                            st.session_state['username']  = login_user_input
                            st.rerun()
                        else:
                            st.error("Access denied — invalid credentials")
                    else:
                        st.warning("Please fill in all fields")
            with tab2:
                st.info("Registration complete. Switch to LOGIN tab to continue.")
            return

        tab1, tab2 = st.tabs(["LOGIN", "REGISTER"])
        with tab1:
            login_user_input = st.text_input("Username", key="login_user", placeholder="your username")
            login_pass_input = st.text_input("Password", type="password", key="login_pass", placeholder="••••••••")
            if st.button("INITIATE LOGIN", use_container_width=True, key="btn_login"):
                if login_user_input and login_pass_input:
                    if login_user(login_user_input, login_pass_input):
                        st.session_state['logged_in'] = True
                        st.session_state['username']  = login_user_input
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
                lbl = "WEAK"       if score <= 2 else "FAIR"         if score <= 4 else "STRONG"
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
                now     = datetime.datetime.now()
                elapsed = (now - st.session_state['reg_last_time']).total_seconds()
                if elapsed > 60:
                    st.session_state['reg_attempts']  = 0
                    st.session_state['reg_last_time'] = now

                if st.session_state['reg_attempts'] >= 3:
                    remaining = max(0, int(60 - elapsed))
                    st.error(f"⚠️ Too many attempts — please wait {remaining}s before trying again")
                elif new_user and new_pass:
                    if not is_strong:
                        st.error("Please use a stronger password (STRONG level required)")
                    else:
                        c.execute('SELECT * FROM userstable WHERE username=?', (new_user,))
                        if c.fetchone():
                            st.session_state['reg_attempts'] += 1
                            st.error("Username already exists")
                        else:
                            add_userdata(new_user, new_pass)
                            st.session_state['reg_attempts'] += 1
                            for k in ['reg_user', 'reg_pass']:
                                if k in st.session_state: del st.session_state[k]
                            st.session_state['just_registered'] = True
                            st.rerun()
                else:
                    st.warning("Please fill in all fields")

# ==========================================
# 5. Main Application Logic
# ==========================================
def show_main_app():
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    # ── Top Header ──
    init = st.session_state['username'][0].upper() if st.session_state['username'] else "?"
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("""
        <div class="top-brand">
            <div class="hex">⬡</div>
            <h2>AI-Dataset Pro</h2>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="top-user">
            <div style="text-align:right;">
                <div class="uname">{st.session_state['username']}</div>
                <div class="ustatus">● ACTIVE SESSION</div>
            </div>
            <div class="avatar">{init}</div>
        </div>
        """, unsafe_allow_html=True)
    st.write("")

    is_admin = (st.session_state['username'].lower() == 'admin')

    # ── Top Navigation ──
    selected_menu = option_menu(
        menu_title=None,
        options=["Dashboard", "AI Engine", "Logout"],
        icons=["grid-1x2", "cpu", "box-arrow-right"],
        default_index=1,
        orientation="horizontal",
        styles={
            "container": { "background-color": "var(--bg-surface)", "border": "1px solid var(--border)", "border-radius": "12px", "padding": "5px", "box-shadow": "0 4px 6px -1px rgba(0,0,0,0.02)", "margin-bottom": "30px" },
            "icon": {"color": "var(--text-3)", "font-size": "16px"},
            "nav-link": { "font-size": "14px", "font-weight": "700", "color": "var(--text-2)", "font-family": "var(--font-ui)", "border-radius": "8px", "padding": "10px", "margin": "0 4px" },
            "nav-link-selected": { "background-color": "var(--accent-dim)", "color": "var(--accent)", "border": "1px solid rgba(255,107,0,0.2)" },
        }
    )

    if selected_menu == "Logout":
        st.session_state.clear()
        st.rerun()

    # ══════════════════════════════════════════
    # AI ENGINE PAGE
    # ══════════════════════════════════════════
    if selected_menu == "AI Engine":

        st.markdown("""
        <div class="page-header">
            <div class="eyebrow">MODULE / AI ENGINE</div>
            <h1>Dataset Generation</h1>
            <div class="sub">สกัดข้อมูลภาพ คัดกรองคุณภาพ และเพิ่มจำนวนข้อมูล (Augmentation) อัตโนมัติด้วย AI</div>
        </div>
        """, unsafe_allow_html=True)

        # 📌 1. ระบบโหลด Custom Model
        st.markdown('<div class="section-label">Neural Network Override</div>', unsafe_allow_html=True)
        custom_model_file = st.file_uploader("🧠 อัปโหลดไฟล์โมเดล .pt ที่เทรนเอง (ปล่อยว่างเพื่อใช้ YOLOv8n มาตรฐาน)", type=['pt'], help="รองรับไฟล์ Weights จาก YOLOv8")
        
        @st.cache_resource
        def load_default_model():
            return YOLO('yolov8n.pt')
        
        # จัดการโหลด Model
        try:
            if custom_model_file:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pt') as tmp_model:
                    tmp_model.write(custom_model_file.read())
                    model = YOLO(tmp_model.name)
                    st.success(f"✅ โหลดโมเดลที่กำหนดเองสำเร็จ: {custom_model_file.name}")
            else:
                model = load_default_model()
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการโหลดโมเดล: {str(e)}")
            model = load_default_model()
            
        available_classes = model.names

        # 📌 2. System Configuration
        with st.expander("⚙  NEURAL NETWORK & SYSTEM CONFIGURATION", expanded=True):
            col1, col2, col3, col4 = st.columns(4, gap="medium")
            with col1:
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">AI TARGETS</p>', unsafe_allow_html=True)
                # ดึงคลาสเริ่มต้น (ถ้ามีคลาส person/car ให้เลือกไว้ก่อน ถ้าไม่มีให้เลือกคลาสแรก)
                default_classes = []
                if "person" in available_classes.values(): default_classes.append("person")
                elif len(available_classes) > 0: default_classes.append(available_classes[0])
                if "car" in available_classes.values(): default_classes.append("car")
                
                selected_class_names = st.multiselect("Detection Targets", list(available_classes.values()), default=default_classes, label_visibility="collapsed")
                selected_class_ids   = [k for k, v in available_classes.items() if v in selected_class_names]
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-top:10px;margin-bottom:6px;text-transform:uppercase;">CONFIDENCE (%)</p>', unsafe_allow_html=True)
                conf_threshold = st.slider("Min Confidence", 10, 90, 25, 5, label_visibility="collapsed") / 100.0
            with col2:
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">DATASET SPLIT</p>', unsafe_allow_html=True)
                split_ratio = st.slider("Train Split (%)", 50, 95, 80, label_visibility="collapsed")
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-top:10px;margin-bottom:6px;text-transform:uppercase;">FRAME SKIP</p>', unsafe_allow_html=True)
                frame_skip  = st.slider("Frame Skip Interval", 1, 30, 5, label_visibility="collapsed")
            with col3:
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">DATA AUGMENTATION</p>', unsafe_allow_html=True)
                do_flip   = st.checkbox("Horizontal Flip")
                do_bright = st.checkbox("Brightness Boost")
                do_noise  = st.checkbox("Add Noise")
            with col4:
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">QUALITY CONTROL</p>', unsafe_allow_html=True)
                do_blur_filter = st.checkbox("Blur Filter", value=True)
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-top:10px;margin-bottom:6px;text-transform:uppercase;">THRESHOLD</p>', unsafe_allow_html=True)
                blur_threshold = st.slider("Blur Threshold", 20, 200, 60, label_visibility="collapsed")

            # ── Telegram Notification ──
            st.markdown('<hr style="margin:16px 0;">', unsafe_allow_html=True)
            col_tele_head, col_tele_toggle = st.columns([3, 1])
            with col_tele_head:
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:2px;text-transform:uppercase;">📱 TELEGRAM NOTIFICATION (OPTIONAL)</p>', unsafe_allow_html=True)
            with col_tele_toggle:
                tele_enabled = st.toggle("Enable Notifications", value=True, key="tele_toggle")

            if tele_enabled:
                col_t1, col_t2, col_t3 = st.columns([2, 1.5, 1])
                with col_t1:
                    st.markdown('<p style="font-family:var(--font-ui);font-size:10px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:4px;text-transform:uppercase;">🔑 Bot Token</p>', unsafe_allow_html=True)
                    tele_token = st.text_input("Bot Token", value="", type="password", placeholder="e.g. 123456789:AAF...", label_visibility="collapsed")
                with col_t2:
                    st.markdown('<p style="font-family:var(--font-ui);font-size:10px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:4px;text-transform:uppercase;">💬 Chat ID</p>', unsafe_allow_html=True)
                    tele_chat_id = st.text_input("Chat ID", value="", placeholder="e.g. 849818556", label_visibility="collapsed")
                with col_t3:
                    st.markdown('<p style="font-family:var(--font-ui);font-size:10px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:4px;text-transform:uppercase;">🧪 TEST</p>', unsafe_allow_html=True)
                    if st.button("Send Test", use_container_width=True, key="btn_test_tele"):
                        if tele_token and tele_chat_id:
                            try:
                                requests.post(f"https://api.telegram.org/bot{tele_token}/sendMessage", data={"chat_id": tele_chat_id, "text": f"✅ AI-Dataset Pro\nการเชื่อมต่อสำเร็จ!"}, timeout=5)
                                st.success("✅ ส่งสำเร็จ!")
                            except: st.error("❌ ขัดข้อง")
                        else: st.warning("กรุณากรอกข้อมูล")
            else:
                tele_token, tele_chat_id = "", ""
                st.markdown('<p style="font-family:var(--font-ui);font-size:12px;color:var(--text-3);font-weight:500;padding:8px 0;">🔕 Notification ถูกปิดอยู่</p>', unsafe_allow_html=True)

        # 📌 3. Media Source & Video Processing
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
                for f in ['images/train', 'images/val', 'labels/train', 'labels/val']: os.makedirs(os.path.join(output_folder, f))

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
                            class_counts[cname] = class_counts.get(cname, 0) + 1
                            new_id = selected_class_names.index(cname) if selected_class_names and cname in selected_class_names else cid
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
                                blur_warning.markdown(f'<div style="color:var(--red);font-size:13px;font-weight:700;padding:8px;border:1px solid var(--red);border-radius:8px;background:var(--bg-surface);">⚠️ BLUR DETECTED (score:{score:.1f}) — FRAME SKIPPED</div>', unsafe_allow_html=True)
                                frame_count += 1; continue
                            else: blur_warning.empty()

                        results = model(frame, classes=selected_class_ids if selected_class_ids else None, conf=conf_threshold, verbose=False)
                        boxes   = results[0].boxes
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
                cap.release(); blur_warning.empty()

                # สร้าง data.yaml
                classes_for_yaml = selected_class_names if selected_class_names else list(available_classes.values())
                with open(os.path.join(output_folder, "data.yaml"), 'w', encoding='utf-8') as yf:
                    yf.write("train: images/train\nval: images/val\n\n")
                    yf.write(f"nc: {len(classes_for_yaml)}\n")
                    yf.write(f"names: [{', '.join([repr(n) for n in classes_for_yaml])}]\n")

                add_history(st.session_state['username'], len(dataset_records), skipped_blur_count)

                # ยิง Telegram
                if tele_token and tele_chat_id:
                    noti_msg = f"✅ AI-Dataset Pro ทำงานเสร็จสิ้น!\n👤 ผู้ใช้งาน: {st.session_state['username']}\n📸 สกัดรูปภาพได้: {len(dataset_records)} รูป\n❌ เตะภาพเบลอทิ้ง: {skipped_blur_count} รูป"
                    send_telegram_notify(tele_token, tele_chat_id, noti_msg)

                # 📌 4. Advanced Data Analytics (ฟีเจอร์ใหม่)
                if len(dataset_records) > 0:
                    st.markdown('<hr style="margin:40px 0 20px;">', unsafe_allow_html=True)
                    st.markdown('<div class="section-label" style="color:var(--accent);">🚀 Advanced Data Analytics</div>', unsafe_allow_html=True)
                    
                    col_an1, col_an2 = st.columns([1, 1], gap="large")
                    with col_an1:
                        st.markdown('<p class="col-header">📊 Class Distribution</p>', unsafe_allow_html=True)
                        df_classes = pd.DataFrame(list(class_counts.items()), columns=['Class', 'Detected Boxes'])
                        df_classes = df_classes[df_classes['Detected Boxes'] > 0]
                        if not df_classes.empty:
                            st.bar_chart(df_classes.set_index('Class'), color="#ff6b00")
                        else:
                            st.info("ไม่พบข้อมูลวัตถุที่จะนำมาวิเคราะห์")

                    with col_an2:
                        st.markdown('<p class="col-header">📁 Extracted Files Preview (Top 10)</p>', unsafe_allow_html=True)
                        recent_files = pd.DataFrame(dataset_records).tail(10)
                        recent_files.columns = ['Split', 'Filename']
                        st.dataframe(recent_files, use_container_width=True, hide_index=True)

                # แสดง Pill สถิติรวม
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
                st.success("🎉 Dataset generation & Data Analysis complete!")

                # ซิปไฟล์และให้ดาวน์โหลด
                zip_filename = "ai_dataset.zip"
                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                    for root, dirs, files in os.walk(output_folder):
                        for file in files: zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), output_folder))
                with open(zip_filename, "rb") as fp:
                    st.download_button("⬇  DOWNLOAD DATASET (PRO)", fp, "ai_dataset_pro.zip", "application/zip", use_container_width=True)
                
                os.remove(video_path); shutil.rmtree(output_folder); os.remove(zip_filename)

    # ══════════════════════════════════════════
    # DASHBOARD PAGE
    # ══════════════════════════════════════════
    elif selected_menu == "Dashboard":
        title_text = "System Admin Dashboard" if is_admin else "Personal Dashboard"
        sub_text   = "Real-time global analytics & user activity" if is_admin else "Your personal AI generation statistics"

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
            df_history  = pd.read_sql_query(
                "SELECT * FROM historytable WHERE username=? ORDER BY timestamp DESC",
                conn, params=(st.session_state['username'],)
            )

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