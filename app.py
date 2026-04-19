import streamlit as st
import streamlit.components.v1 as components
import tempfile
import os
import cv2
import zipfile
import shutil
import random
import hashlib
import numpy as np
import re
import pandas as pd
import datetime
import requests
from ultralytics import YOLO
from streamlit_option_menu import option_menu
from supabase import create_client, Client

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
# 2. Database & Security Functions (SUPABASE CLOUD)
# ==========================================
SUPABASE_URL = "https://dkbyzgowhrhxobcmyfxx.supabase.co"
SUPABASE_KEY = "sb_publishable_1DP6M9cfybXvSJ5a-j8eZg_39gUZg5h"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Database Connection Error: โปรดตรวจสอบ URL และ Key ของ Supabase")

def add_userdata(username, password):
    hashed = hashlib.sha256(str.encode(password)).hexdigest()
    supabase.table("userstable").insert({"username": username, "password": hashed}).execute()

def login_user(username, password):
    hashed = hashlib.sha256(str.encode(password)).hexdigest()
    response = supabase.table("userstable").select("*").eq("username", username).eq("password", hashed).execute()
    return response.data

def add_history(username, total_img, blur_skip):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    supabase.table("historytable").insert({
        "username": username, 
        "total_img": total_img, 
        "blur_skip": blur_skip, 
        "timestamp": now
    }).execute()

def send_telegram_notify(bot_token, chat_id, message):
    if not bot_token or not chat_id: return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try: requests.post(url, data=data, timeout=5)
    except Exception: pass

# ==========================================
# ── State Management & Auto-Login Persistence ──
# ==========================================
SESSION_SALT = "ai_dataset_pro_secret_2026" 

if 'logged_in' not in st.session_state:
    if "session_user" in st.query_params and "session_token" in st.query_params:
        url_user = st.query_params["session_user"]
        url_token = st.query_params["session_token"]
        expected_token = hashlib.sha256((url_user + SESSION_SALT).encode()).hexdigest()
        
        if url_token == expected_token:
            st.session_state['logged_in'] = True
            st.session_state['username'] = url_user
            st.session_state['current_page'] = 'main'
        else:
            st.session_state['logged_in'] = False
    else:
        st.session_state['logged_in'] = False

if 'current_page'    not in st.session_state: st.session_state['current_page']    = 'landing'
if 'username'        not in st.session_state: st.session_state['username']         = ""
if 'reg_attempts'    not in st.session_state: st.session_state['reg_attempts']     = 0
if 'reg_last_time'   not in st.session_state: st.session_state['reg_last_time']    = datetime.datetime.now()
if 'just_registered' not in st.session_state: st.session_state['just_registered']  = False

if 'process_done'       not in st.session_state: st.session_state['process_done']       = False
if 'last_uploaded_file' not in st.session_state: st.session_state['last_uploaded_file'] = ""
if 'dataset_records'    not in st.session_state: st.session_state['dataset_records']    = []
if 'class_counts'       not in st.session_state: st.session_state['class_counts']       = {}
if 'skipped_blur_count' not in st.session_state: st.session_state['skipped_blur_count'] = 0

if 'dark_mode' not in st.session_state: st.session_state['dark_mode'] = False

if st.session_state.get('logged_in'):
    st.session_state['current_page'] = 'main'

# ==========================================
# 3. Global CSS & Frontend Theme Toggle
# ==========================================
def frontend_theme_toggle():
    components.html("""
    <style>
        body { margin:0; padding:0; display:flex; align-items:center; justify-content:center; background:transparent; font-family:sans-serif; }
        .toggle-btn {
            cursor: pointer;
            background: transparent;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 8px 0;
            width: 100%;
            text-align: center;
            font-size: 16px;
            transition: 0.2s;
            user-select: none;
            color: #0f172a;
        }
        .toggle-btn:hover { border-color: #ff6b00 !important; }
    </style>
    <div class="toggle-btn" id="btn" onclick="toggleTheme()">🌙</div>
    <script>
        var root = window.parent.document.documentElement;
        var btn = document.getElementById('btn');
        
        function syncUI() {
            var theme = root.getAttribute('data-custom-theme') || 'light';
            btn.innerHTML = theme === 'dark' ? '☀️' : '🌙';
            if (theme === 'dark') {
                btn.style.borderColor = '#475569';
                btn.style.color = '#f8fafc';
            } else {
                btn.style.borderColor = '#cbd5e1';
                btn.style.color = '#0f172a';
            }
        }

        function toggleTheme() {
            var currentTheme = root.getAttribute('data-custom-theme') || 'light';
            var newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            root.setAttribute('data-custom-theme', newTheme);
            syncUI();
        }
        
        syncUI();
        var observer = new MutationObserver(syncUI);
        observer.observe(root, { attributes: true, attributeFilter: ['data-custom-theme'] });
    </script>
    """, height=40)

def get_theme_css():
    css_base = """
    :root {
        --bg-deep:     #f8fafc;
        --bg-surface:  #ffffff;
        --bg-raised:   #f1f5f9;
        --bg-hover:    #e2e8f0;
        --border:      #e2e8f0;
        --border-hi:   #cbd5e1;
        --text-1:      #0f172a;
        --text-2:      #1e293b;
        --text-3:      #475569;
        --chart-filter: none;
        --menu-filter: none;
        
        --accent:      #ff6b00;
        --accent-dim:  rgba(255, 107, 0, 0.15);
        --accent-glow: rgba(255, 107, 0, 0.25);
        --green:       #10b981;
        --red:         #ef4444;
        --amber:       #f59e0b;
        --blue:        #3b82f6;
        --font-display:'Outfit', sans-serif;
        --font-ui:     'Plus Jakarta Sans', sans-serif;
        --font-mono:   'DM Mono', monospace;
        --r:           10px;
        --r-lg:        16px;
    }

    :root[data-custom-theme="dark"] {
        --bg-deep:     #0f172a;
        --bg-surface:  #1e293b;
        --bg-raised:   #334155;
        --bg-hover:    #475569;
        --border:      #334155;
        --border-hi:   #475569;
        --text-1:      #f8fafc;
        --text-2:      #e2e8f0;
        --text-3:      #94a3b8;
        --chart-filter: invert(0.88) hue-rotate(180deg) contrast(1.1);
        --menu-filter: invert(0.88) hue-rotate(180deg) contrast(1.1);
    }
    
    [data-testid="stArrowVegaLiteChart"] { filter: var(--chart-filter); border-radius: 12px; }
    iframe[title="streamlit_option_menu.option_menu"] { filter: var(--menu-filter); }

    html, body, .stApp { background-color: var(--bg-deep) !important; color: var(--text-1) !important; font-family: var(--font-ui); transition: background-color 0.3s, color 0.3s; }

    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
    header[data-testid="stHeader"] { background-color: transparent !important; border-bottom: none !important; box-shadow: none !important; }
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
    .appview-container { background-color: var(--bg-deep) !important; transition: background-color 0.3s; }
    .main > div { padding-top: 0 !important; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 3px; }

    .top-brand { display: flex; align-items: center; gap: 12px; }
    .top-brand .hex { width: 36px; height: 36px; background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.3); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; color: var(--accent); font-weight: 800; }
    .top-brand h2 { font-size: 20px !important; font-weight: 800 !important; color: var(--text-1) !important; margin: 0 !important; letter-spacing: -0.5px; font-family: var(--font-display) !important; }
    .top-user { display: flex; align-items: center; gap: 12px; justify-content: flex-end; padding: 4px 0; }
    .top-user .avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--accent); color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; box-shadow: 0 2px 4px rgba(255,107,0,0.3); }
    .top-user .uname { font-size: 14px; font-weight: 800; color: var(--text-1) !important; line-height: 1.2; text-transform: uppercase; font-family: var(--font-display) !important; }
    .top-user .ustatus { font-size: 11px; font-weight: 700; color: var(--green); letter-spacing: 0.5px; }

    .page-header { padding: 12px 0 24px; border-bottom: 2px solid var(--border); margin-bottom: 32px; }
    .page-header .eyebrow { font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; }
    .page-header h1 { font-size: 32px !important; font-weight: 800 !important; color: var(--text-1) !important; margin: 0 !important; letter-spacing: -1px; line-height: 1.2 !important; font-family: var(--font-display) !important; }
    .page-header .sub { font-size: 15px; font-weight: 500; color: var(--text-2); margin-top: 8px; }

    .section-label { font-family: var(--font-display); font-size: 14px; font-weight: 800; color: var(--text-1) !important; letter-spacing: 1px; text-transform: uppercase; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
    .section-label::before { content: ''; width: 16px; height: 4px; background: var(--accent); display: inline-block; border-radius: 2px; }
    .col-header { font-family: var(--font-display); font-size: 11px; font-weight: 800; color: var(--text-1) !important; letter-spacing: 1px; text-transform: uppercase; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
    .dot-status { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .dot-blue  { background: var(--blue); }
    .dot-green { background: var(--accent); }
    .dot-red   { background: var(--red); }

    .stat-row  { display: flex; gap: 16px; margin-top: 16px; flex-wrap: wrap; }
    .stat-pill { flex: 1; min-width: 130px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 20px 16px; text-align: left; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); transition: all 0.3s; }
    .stat-pill:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); }
    .stat-pill .sp-label { font-family: var(--font-display); font-size: 11px; font-weight: 700; color: var(--text-2); letter-spacing: 0.5px; text-transform: uppercase; display: block; margin-bottom: 8px; }
    .stat-pill .sp-val { font-size: 28px; font-weight: 800; color: var(--text-1); letter-spacing: -0.5px; font-family: var(--font-display); }

    .custom-table { width: 100%; border-collapse: collapse; font-family: var(--font-ui); font-size: 13px; color: var(--text-1); background: var(--bg-surface); border-radius: var(--r-lg); overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); margin-top: 8px; transition: all 0.3s; }
    .custom-table th { background-color: var(--bg-raised); color: var(--text-2); font-family: var(--font-display); font-size: 11px; font-weight: 800; letter-spacing: 0.5px; text-transform: uppercase; padding: 14px 16px; text-align: left; border-bottom: 2px solid var(--border); transition: all 0.3s; }
    .custom-table td { padding: 14px 16px; border-bottom: 1px solid var(--border); font-weight: 500; border-color: var(--border); transition: all 0.3s; }
    .custom-table tr:last-child td { border-bottom: none; }
    .custom-table tr:hover td { background-color: var(--bg-hover); }

    [data-testid="stForm"] { border: none !important; padding: 0 !important; }
    
    .stButton > button { font-family: var(--font-display) !important; font-size: 14px !important; font-weight: 700 !important; border-radius: 8px !important; border: 1px solid var(--border-hi) !important; background: var(--bg-surface) !important; color: var(--text-1) !important; transition: all 0.2s ease !important; padding: 10px 24px !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; }
    .stButton > button:hover { border-color: var(--accent) !important; background: var(--bg-raised) !important; color: var(--accent) !important; }
    
    [data-testid="stFormSubmitButton"] > button {
        background-color: var(--accent) !important;
        color: #ffffff !important;
        border: none !important;
        font-family: var(--font-display) !important;
        font-weight: 800 !important;
        font-size: 14px !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 6px rgba(255, 107, 0, 0.2) !important;
    }
    [data-testid="stFormSubmitButton"] > button:hover { opacity: 0.9 !important; transform: translateY(-1px) !important; color: #ffffff !important; }

    .stDownloadButton > button { font-family: var(--font-display) !important; font-weight: 800 !important; font-size: 14px !important; border-radius: 8px !important; background: var(--accent) !important; color: white !important; border: none !important; padding: 12px 24px !important; box-shadow: 0 4px 6px rgba(255,107,0,0.2) !important; }
    .stDownloadButton > button:hover { opacity: 0.9 !important; transform: translateY(-1px) !important; }

    .stTextInput > label, .stMultiselect > label, .stSlider > label, .stFileUploader > label, .stRadio > label { font-family: var(--font-ui) !important; font-size: 12px !important; font-weight: 700 !important; color: var(--text-1) !important; margin-bottom: 8px !important; transition: color 0.3s; }
    
    div[data-testid="stCheckbox"] p, div[data-testid="stRadio"] p, div[data-testid="stToggle"] p, div[data-testid="stFileUploaderDropzone"] span, div[data-testid="stFileUploaderDropzone"] small { color: var(--text-1) !important; transition: color 0.3s; }
    div[data-testid="stSliderTickBarMin"], div[data-testid="stSliderTickBarMax"] { color: var(--text-3) !important; transition: color 0.3s; }

    div[data-baseweb="input"] { background-color: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; border-radius: 8px !important; transition: all 0.3s !important; overflow: hidden !important; }
    div[data-baseweb="input"]:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-dim) !important; }
    div[data-baseweb="input"] > div { background-color: transparent !important; }
    div[data-baseweb="input"] input { color: var(--text-1) !important; background-color: transparent !important; font-size: 14px !important; padding: 12px 16px !important; transition: color 0.3s; }
    div[data-baseweb="input"] input::placeholder { color: var(--text-3) !important; }
    div[data-baseweb="input"] svg { fill: var(--text-3) !important; transition: fill 0.3s; }

    [data-baseweb="select"] > div { background: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; border-radius: 8px !important; transition: all 0.3s !important; }
    [data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-dim) !important; }
    [data-baseweb="tag"] { background: var(--accent-dim) !important; border: none !important; border-radius: 6px !important; padding: 4px 8px !important; transition: background 0.3s; }
    [data-baseweb="tag"] span { color: var(--accent) !important; font-size: 12px !important; font-weight: 700 !important; }

    [data-testid="stExpander"] { background: var(--bg-surface) !important; border: 1px solid var(--border) !important; border-radius: var(--r-lg) !important; margin-bottom: 24px !important; overflow: hidden !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02) !important; transition: all 0.3s; }
    [data-testid="stExpander"] summary { font-family: var(--font-display) !important; font-size: 13px !important; font-weight: 700 !important; color: var(--text-1) !important; padding: 16px 24px !important; background: var(--bg-raised) !important; border-bottom: 1px solid var(--border) !important; transition: all 0.3s; }
    [data-testid="stExpander"] summary:hover { background: var(--bg-hover) !important; }
    [data-testid="stExpander"] > div > div { padding: 24px !important; }
    
    .stTabs [data-baseweb="tab-list"] { background: transparent !important; border-bottom: 1px solid var(--border) !important; gap: 16px !important; transition: border 0.3s; }
    .stTabs [data-baseweb="tab"] { background: transparent !important; color: var(--text-3) !important; border: none !important; font-family: var(--font-display) !important; font-size: 13px !important; font-weight: 700 !important; letter-spacing: 0.5px !important; text-transform: uppercase !important; padding: 12px 4px !important; border-radius: 0 !important; transition: color 0.3s; }
    .stTabs [data-baseweb="tab"]:hover { color: var(--text-1) !important; }
    .stTabs [aria-selected="true"] { color: var(--accent) !important; border-bottom: 3px solid var(--accent) !important; font-weight: 800 !important; }
    .stTabs [data-baseweb="tab-panel"] { padding: 32px 0 0 !important; }
    .stProgress > div > div { background: var(--border) !important; border-radius: 4px !important; height: 6px !important; transition: background 0.3s; }
    .stProgress > div > div > div { background: var(--accent) !important; height: 6px !important; border-radius: 4px !important; }

    [data-testid="stAlert"] { background: var(--bg-surface) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; font-family: var(--font-ui) !important; font-size: 14px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important; color: var(--text-1) !important; transition: all 0.3s; }
    [data-testid="stAlert"][data-type="success"] { border-left: 4px solid var(--green) !important; }
    [data-testid="stAlert"][data-type="error"]   { border-left: 4px solid var(--red) !important; }
    [data-testid="stAlert"][data-type="warning"] { border-left: 4px solid var(--amber) !important; }
    hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 32px 0 !important; transition: border 0.3s; }
    [data-testid="stFileUploaderDropzone"] { background: var(--bg-surface) !important; border: 2px dashed var(--border-hi) !important; border-radius: var(--r-lg) !important; padding: 40px 24px !important; transition: all 0.3s ease !important; }
    [data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent) !important; background: var(--accent-dim) !important; }
    [data-testid="stFileUploaderDropzone"] button { background: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; color: var(--text-1) !important; border-radius: 8px !important; font-family: var(--font-display) !important; font-size: 13px !important; font-weight: 700 !important; padding: 8px 16px !important; transition: all 0.3s; }
    video { border-radius: 12px !important; border: 1px solid var(--border) !important; width: 100% !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important; transition: border 0.3s; }
    [data-testid="stImage"] img { border-radius: 12px !important; border: 1px solid var(--border) !important; width: 100% !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important; transition: border 0.3s; }
    .stMarkdown p { color: var(--text-1) !important; font-size: 15px !important; font-family: var(--font-ui) !important; font-weight: 500 !important; line-height: 1.6 !important; transition: color 0.3s; }
    .main .block-container { padding: 0 2rem 2rem !important; max-width: 1200px; }

    .land-logo-badge { font-family: var(--font-mono); font-size: 9px; font-weight: 700; color: var(--accent); background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.2); border-radius: 4px; padding: 2px 6px; letter-spacing: 1.5px; text-transform: uppercase; margin-left: 4px; vertical-align: middle; }
    .hero-eyebrow { display: inline-flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.25); border-radius: 100px; padding: 6px 14px; margin-bottom: 28px; }
    .hero-eyebrow .pulse { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); animation: pulse-dot 1.8s ease-in-out infinite; }
    @keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.7); } }
    .hero-title { font-family: var(--font-display) !important; font-size: 60px !important; font-weight: 900 !important; color: var(--text-1) !important; margin: 0 0 16px !important; letter-spacing: -2px; line-height: 1.05 !important; transition: color 0.3s; }
    .hero-title .accent-word { color: var(--accent); position: relative; display: inline-block; }
    .hero-sub { font-size: 17px !important; font-weight: 400 !important; color: var(--text-3) !important; margin: 0 0 40px !important; line-height: 1.75 !important; max-width: 500px; transition: color 0.3s; }
    .hero-stats { display: flex; align-items: center; gap: 28px; padding: 18px 24px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); max-width: 480px; margin-top: 32px; transition: all 0.3s; }
    .hero-stat-num { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--text-1); letter-spacing: -1px; line-height: 1; transition: color 0.3s; }
    .hero-stat-label { font-size: 10px; font-weight: 600; color: var(--text-3); letter-spacing: 0.5px; margin-top: 3px; text-transform: uppercase; transition: color 0.3s; }
    .hero-stat-div { width: 1px; height: 32px; background: var(--border); transition: background 0.3s; }
    .hero-visual { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 20px; overflow: hidden; box-shadow: 0 20px 48px -12px rgba(0,0,0,0.10); transition: all 0.3s; }
    .hero-visual-bar { background: var(--bg-raised); border-bottom: 1px solid var(--border); padding: 13px 18px; display: flex; align-items: center; gap: 6px; transition: all 0.3s; }
    .win-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    .hero-visual-body { padding: 18px; }
    .mock-label { font-family: var(--font-mono); font-size: 10px; font-weight: 600; color: var(--text-3); letter-spacing: 1px; text-transform: uppercase; display: flex; justify-content: space-between; margin-bottom: 5px; transition: color 0.3s; }
    .mock-bar-bg { width: 100%; height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; margin-bottom: 14px; transition: background 0.3s; }
    .mock-bar-fill { height: 100%; border-radius: 3px; background: var(--accent); animation: fill-anim 2.6s ease-in-out infinite alternate; }
    @keyframes fill-anim { from { width: 38%; } to { width: 79%; } }
    .mock-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; }
    .mock-thumb { aspect-ratio: 4/3; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); position: relative; display: flex; align-items: center; justify-content: center; transition: border 0.3s; }
    .mock-thumb-label { position: absolute; bottom: 5px; left: 5px; font-family: var(--font-mono); font-size: 9px; font-weight: 700; color: white; background: rgba(0,0,0,0.5); padding: 2px 5px; border-radius: 3px; letter-spacing: 0.5px; }
    .mock-detect-box { position: absolute; border: 2px solid var(--accent); border-radius: 3px; animation: box-pulse 2s ease-in-out infinite; }
    @keyframes box-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }
    .mock-stat-row { display: flex; gap: 7px; margin-top: 10px; }
    .mock-stat { flex: 1; background: var(--bg-raised); border-radius: 8px; padding: 9px 10px; border: 1px solid var(--border); transition: all 0.3s; }
    .mock-stat-n { font-family: var(--font-display); font-size: 17px; font-weight: 800; color: var(--text-1); transition: color 0.3s; }
    .mock-stat-l { font-family: var(--font-mono); font-size: 9px; font-weight: 600; color: var(--text-3); letter-spacing: 0.8px; text-transform: uppercase; transition: color 0.3s; }

    .section-sep { display: flex; align-items: center; gap: 16px; padding: 56px 0 44px; }
    .section-sep-line { flex: 1; height: 1px; background: var(--border); transition: background 0.3s; }
    .section-sep-label { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-3); letter-spacing: 2px; text-transform: uppercase; white-space: nowrap; transition: color 0.3s; }
    .features-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; margin-bottom: 60px; }
    .feat-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 18px; padding: 26px 22px; transition: all 0.3s ease; position: relative; overflow: hidden; }
    .feat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, var(--accent), transparent); opacity: 0; transition: opacity 0.3s; }
    .feat-card:hover { transform: translateY(-4px); border-color: rgba(255,107,0,0.3); box-shadow: 0 16px 32px -8px rgba(255,107,0,0.1); }
    .feat-card:hover::before { opacity: 1; }
    .feat-icon-wrap { width: 42px; height: 42px; border-radius: 11px; background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.2); display: flex; align-items: center; justify-content: center; font-size: 20px; margin-bottom: 16px; }
    .feat-title { font-family: var(--font-display); font-size: 16px; font-weight: 700; color: var(--text-1); margin-bottom: 9px; letter-spacing: -0.3px; transition: color 0.3s; }
    .feat-desc { font-size: 13px; color: var(--text-3); line-height: 1.65; transition: color 0.3s; }
    .feat-tag { display: inline-block; margin-top: 13px; font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--accent); background: var(--accent-dim); border-radius: 4px; padding: 3px 8px; letter-spacing: 1px; text-transform: uppercase; }

    .steps-row { display: flex; gap: 0; margin-bottom: 60px; position: relative; }
    .steps-row::before { content: ''; position: absolute; top: 23px; left: 48px; right: 48px; height: 1px; background: repeating-linear-gradient(90deg, var(--border) 0, var(--border) 6px, transparent 6px, transparent 12px); z-index: 0; }
    .step-item { flex: 1; text-align: center; position: relative; z-index: 1; padding: 0 10px; }
    .step-num { width: 46px; height: 46px; border-radius: 50%; background: var(--bg-surface); border: 2px solid var(--border); display: flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 15px; font-weight: 800; color: var(--text-3); margin: 0 auto 14px; transition: all 0.3s; }
    .step-item:hover .step-num { background: var(--accent); border-color: var(--accent); color: white; box-shadow: 0 6px 14px rgba(255,107,0,0.3); }
    .step-title { font-family: var(--font-display); font-size: 13px; font-weight: 700; color: var(--text-1); margin-bottom: 5px; transition: color 0.3s; }
    .step-desc { font-size: 12px; color: var(--text-3); line-height: 1.5; transition: color 0.3s; }

    .cta-banner { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 24px; padding: 52px 44px; margin-bottom: 60px; display: flex; align-items: center; justify-content: space-between; gap: 32px; position: relative; overflow: hidden; transition: all 0.3s; }
    .cta-banner-eyebrow { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 12px; }
    .cta-banner-title { font-family: var(--font-display); font-size: 32px; font-weight: 800; color: var(--text-1); letter-spacing: -1px; line-height: 1.2; margin-bottom: 10px; transition: color 0.3s; }
    .cta-banner-sub { font-size: 14px; color: var(--text-3); line-height: 1.5; max-width: 380px; transition: color 0.3s; }

    .land-footer { border-top: 1px solid var(--border); padding: 28px 0; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; transition: border 0.3s; }
    .land-footer-left { font-family: var(--font-mono); font-size: 11px; color: var(--text-3); font-weight: 600; letter-spacing: 0.5px; transition: color 0.3s; }
    .land-footer-tags { display: flex; gap: 8px; }
    .land-footer-tag { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-3); background: var(--bg-raised); border: 1px solid var(--border); border-radius: 4px; padding: 3px 8px; letter-spacing: 1px; text-transform: uppercase; transition: all 0.3s; }
    
    @media (max-width: 768px) {
        .hero-title { font-size: 42px !important; }
        .hero-sub { font-size: 15px !important; }
        .hero-stats { display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 16px !important; padding: 16px !important; text-align: center !important; }
        .hero-stat-div { display: none !important; }
        .features-grid { grid-template-columns: 1fr !important; }
        .mock-grid { grid-template-columns: repeat(2, 1fr) !important; }
        .mock-stat-row { flex-wrap: wrap !important; }
        .mock-stat { min-width: 40% !important; }
        
        .steps-row {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 20px 12px !important;
            background: var(--bg-surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 16px !important;
            padding: 24px 16px !important;
            margin-bottom: 40px !important;
        }
        .step-item { padding: 0 !important; }
        .step-item:last-child { grid-column: span 2 !important; } 
        .step-num { width: 38px !important; height: 38px !important; font-size: 13px !important; margin: 0 auto 8px !important; }
        .steps-row::before { display: none !important; }
        
        .cta-banner { padding: 32px 24px !important; text-align: center !important; }
        .cta-banner-sub { margin: 0 auto !important; }
    }
    """
    
    return f"<style>\n@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Outfit:wght@400;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');\n{css_base}</style>"

# ==========================================
# 4. Landing Page
# ==========================================
def show_landing_page():
    st.markdown(get_theme_css(), unsafe_allow_html=True)
    nav1, nav2 = st.columns([1, 1])
    with nav1:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;padding:22px 0 18px;border-bottom:1px solid var(--border);">
            <div style="width:32px;height:32px;background:var(--accent);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:15px;color:white;font-weight:900;box-shadow:0 3px 8px rgba(255,107,0,0.3);">⬡</div>
            <span style="font-family:var(--font-display);font-size:17px;font-weight:800;color:var(--text-1);letter-spacing:-0.5px;">AI-Dataset Pro</span>
            <span class="land-logo-badge">Beta</span>
        </div>
        """, unsafe_allow_html=True)
    
    with nav2:
        st.markdown('<div style="padding:16px 0; border-bottom:1px solid var(--border);">', unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns([0.85, 0.15])
        with btn_col1:
            if st.button("Sign In / Register →", key="nav_signin", use_container_width=True):
                st.session_state['current_page'] = 'auth'
                st.rerun()
        with btn_col2:
            frontend_theme_toggle()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="padding-top:16px;">', unsafe_allow_html=True)
    h_left, h_right = st.columns([1.05, 0.95], gap="large")

    with h_left:
        st.markdown("""
        <div style="padding-top:44px;padding-bottom:16px;">
            <div class="hero-eyebrow"><span class="pulse"></span>YOLOv8 Powered · Auto Dataset</div>
            <h1 class="hero-title">Turn Video into<br><span class="accent-word">AI-Ready</span><br>Dataset.</h1>
            <p class="hero-sub">สกัดภาพ คัดกรองคุณภาพ และเพิ่มข้อมูล Augmentation จากวิดีโอของคุณโดยอัตโนมัติ — พร้อมเทรน YOLOv8 ทันที</p>
        </div>
        """, unsafe_allow_html=True)
        btn1, btn2, _ = st.columns([1, 1, 0.4])
        with btn1:
            if st.button("🚀  Get Started Free", key="hero_main_cta", use_container_width=True):
                st.session_state['current_page'] = 'auth'
                st.rerun()
        with btn2:
            st.button("↓  See Features", key="hero_sec_cta", use_container_width=True)

        st.markdown("""
        <div class="hero-stats">
            <div><div class="hero-stat-num">80+</div><div class="hero-stat-label">YOLO Classes</div></div>
            <div class="hero-stat-div"></div>
            <div><div class="hero-stat-num">4×</div><div class="hero-stat-label">Augmentation</div></div>
            <div class="hero-stat-div"></div>
            <div><div class="hero-stat-num">Auto</div><div class="hero-stat-label">QC Filter</div></div>
            <div class="hero-stat-div"></div>
            <div><div class="hero-stat-num">ZIP</div><div class="hero-stat-label">Export Ready</div></div>
        </div>
        """, unsafe_allow_html=True)

    with h_right:
        st.markdown("""
        <div style="padding-top:36px;">
        <div class="hero-visual">
            <div class="hero-visual-bar">
                <div class="win-dot" style="background:#ef4444;"></div>
                <div class="win-dot" style="background:#f59e0b;margin-left:4px;"></div>
                <div class="win-dot" style="background:#10b981;margin-left:4px;"></div>
                <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-3);margin-left:10px;font-weight:600;letter-spacing:0.5px;">AI VISION PREVIEW</span>
                <span style="margin-left:auto;font-family:var(--font-mono);font-size:10px;font-weight:700;color:var(--accent);">▶ LIVE</span>
            </div>
            <div class="hero-visual-body">
                <div class="mock-label"><span>Processing Frames</span><span style="color:var(--accent);">frame_000482</span></div>
                <div class="mock-bar-bg"><div class="mock-bar-fill"></div></div>
                <div class="mock-grid">
                    <div class="mock-thumb" style="background:var(--bg-raised);"><div class="mock-detect-box" style="top:20%;left:15%;width:55%;height:50%;"></div><div class="mock-thumb-label">person ✓</div></div>
                    <div class="mock-thumb" style="background:var(--bg-hover);"><div class="mock-detect-box" style="top:25%;left:20%;width:60%;height:45%;animation-delay:0.5s;"></div><div class="mock-thumb-label">car ✓</div></div>
                    <div class="mock-thumb" style="background:var(--bg-raised);"><div class="mock-detect-box" style="top:18%;left:10%;width:70%;height:55%;animation-delay:1s;"></div><div class="mock-thumb-label">person ✓</div></div>
                    <div class="mock-thumb" style="background:var(--bg-hover);"><div class="mock-thumb-label">flip ↔</div></div>
                    <div class="mock-thumb" style="background:var(--bg-raised);"><div class="mock-thumb-label">bright ☀</div></div>
                    <div class="mock-thumb" style="background:var(--bg-hover);"><div class="mock-thumb-label">noise ~</div></div>
                </div>
                <div class="mock-stat-row">
                    <div class="mock-stat"><div class="mock-stat-n" style="color:var(--accent);">247</div><div class="mock-stat-l">Extracted</div></div>
                    <div class="mock-stat"><div class="mock-stat-n" style="color:var(--red);">12</div><div class="mock-stat-l">Blurry</div></div>
                    <div class="mock-stat"><div class="mock-stat-n" style="color:var(--green);">198</div><div class="mock-stat-l">Train</div></div>
                    <div class="mock-stat"><div class="mock-stat-n">49</div><div class="mock-stat-l">Val</div></div>
                </div>
            </div>
        </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="section-sep"><div class="section-sep-line"></div><div class="section-sep-label">Core Features</div><div class="section-sep-line"></div></div>
    <div class="features-grid">
        <div class="feat-card"><div class="feat-icon-wrap">🎯</div><div class="feat-title">Smart Object Detection</div><div class="feat-desc">เลือกเฉพาะ Class ที่ต้องการ เช่น คน รถ จักรยาน ระบบสกัดเฉพาะเฟรมที่ตรวจพบวัตถุเป้าหมาย พร้อม Label YOLO Format อัตโนมัติ</div><span class="feat-tag">YOLOv8n · 80 Classes</span></div>
        <div class="feat-card"><div class="feat-icon-wrap">🛡️</div><div class="feat-title">Automated Quality Control</div><div class="feat-desc">ระบบ Blur Detection ด้วย Laplacian Variance คัดทิ้งภาพที่เบลอหรือสั่นไหวออกอัตโนมัติ ปรับค่า Threshold ได้ตามต้องการ</div><span class="feat-tag">Blur Filter · Auto QC</span></div>
        <div class="feat-card"><div class="feat-icon-wrap">🧬</div><div class="feat-title">4× Data Augmentation</div><div class="feat-desc">ขยาย Dataset อัตโนมัติ 4 รูปแบบ: ต้นฉบับ / พลิกแนวนอน / เพิ่มความสว่าง / เพิ่ม Noise พร้อม YOLO Label ที่ถูกต้องทุกรูป</div><span class="feat-tag">Flip · Bright · Noise</span></div>
        <div class="feat-card"><div class="feat-icon-wrap">📦</div><div class="feat-title">One-Click Export</div><div class="feat-desc">ดาวน์โหลด Dataset ในรูปแบบ ZIP พร้อมโครงสร้าง images/labels train/val และ data.yaml สำหรับ Import เข้า YOLOv8 ได้ทันที</div><span class="feat-tag">YOLO Format · data.yaml</span></div>
    </div>
    <div class="section-sep"><div class="section-sep-line"></div><div class="section-sep-label">How It Works</div><div class="section-sep-line"></div></div>
    <div class="steps-row">
        <div class="step-item"><div class="step-num">01</div><div class="step-title">Upload Video</div><div class="step-desc">MP4 / AVI / MOV</div></div>
        <div class="step-item"><div class="step-num">02</div><div class="step-title">Configure</div><div class="step-desc">เลือก Class & ตั้งค่า</div></div>
        <div class="step-item"><div class="step-num">03</div><div class="step-title">AI Scan</div><div class="step-desc">YOLO สแกนทุกเฟรม</div></div>
        <div class="step-item"><div class="step-num">04</div><div class="step-title">Augment</div><div class="step-desc">ขยายข้อมูล 4×</div></div>
        <div class="step-item"><div class="step-num">05</div><div class="step-title">Download</div><div class="step-desc">ZIP + data.yaml</div></div>
    </div>
    <div class="cta-banner">
        <div style="position:relative;z-index:1;flex:1;">
            <div class="cta-banner-eyebrow">Ready to Start?</div>
            <div class="cta-banner-title">Build Your Dataset<br>in Minutes.</div>
            <div class="cta-banner-sub">ไม่ต้องเขียนโค้ด ไม่ต้องมีประสบการณ์ด้าน AI — ระบบทำทุกอย่างให้คุณ</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    _, cta_mid, _ = st.columns([1.15, 0.7, 1.15])
    with cta_mid:
        if st.button("🚀  Start Building Dataset", key="cta_bottom", use_container_width=True):
            st.session_state['current_page'] = 'auth'
            st.rerun()
    st.markdown("""
    <div class="land-footer">
        <div class="land-footer-left">© 2026 AI-Dataset Pro · Computer Vision Platform</div>
        <div class="land-footer-tags"><span class="land-footer-tag">YOLOv8</span><span class="land-footer-tag">Streamlit</span><span class="land-footer-tag">OpenCV</span></div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 5. Authentication Page
# ==========================================
def show_auth_page():
    st.markdown(get_theme_css(), unsafe_allow_html=True)
    
    top1, top2 = st.columns([0.85, 0.15])
    with top1:
        if st.button("← Back to Home", key="back_home"):
            st.session_state['current_page'] = 'landing'
            st.rerun()
    with top2:
        frontend_theme_toggle()

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:12px 0 28px;border-bottom:2px solid var(--border);margin-bottom:28px;">
            <div style="width:48px;height:48px;background:var(--accent-dim);border:1px solid rgba(255,107,0,0.3);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:24px;margin:0 auto 16px;color:var(--accent);font-weight:800;">⬡</div>
            <h1 style="font-family:var(--font-display);font-size:26px;font-weight:800;color:var(--text-1);margin:0 0 4px;letter-spacing:-0.5px;">AI-Dataset Pro</h1>
            <div style="font-family:var(--font-mono);font-size:10px;color:var(--text-3);letter-spacing:2.5px;font-weight:600;">SECURE LOGIN PORTAL</div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.get('just_registered'):
            st.success("✅ สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ")
            
            with st.form("login_form_post_reg"):
                login_user_input = st.text_input("Username", placeholder="your username")
                login_pass_input = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("INITIATE LOGIN", use_container_width=True)
                
                if submitted:
                    if login_user_input and login_pass_input:
                        if login_user(login_user_input, login_pass_input):
                            st.session_state['logged_in'] = True
                            st.session_state['username']  = login_user_input
                            st.session_state['current_page'] = 'main'
                            st.session_state['just_registered'] = False
                            
                            st.query_params["session_user"] = login_user_input
                            st.query_params["session_token"] = hashlib.sha256((login_user_input + SESSION_SALT).encode()).hexdigest()
                            
                            st.rerun()
                        else: st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
                    else: st.warning("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน")
            
            if st.button("ย้อนกลับ", use_container_width=True):
                st.session_state['just_registered'] = False
                st.rerun()
            return

        tab1, tab2 = st.tabs(["LOGIN", "REGISTER"])
        
        with tab1:
            with st.form("login_form"):
                login_user_input = st.text_input("Username", placeholder="your username")
                login_pass_input = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("INITIATE LOGIN", use_container_width=True)
                if submitted:
                    if login_user_input and login_pass_input:
                        if login_user(login_user_input, login_pass_input):
                            st.session_state['logged_in'] = True
                            st.session_state['username']  = login_user_input
                            st.session_state['current_page'] = 'main'
                            
                            st.query_params["session_user"] = login_user_input
                            st.query_params["session_token"] = hashlib.sha256((login_user_input + SESSION_SALT).encode()).hexdigest()
                            
                            st.rerun()
                        else: st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
                    else: st.warning("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน")

        with tab2:
            with st.form("register_form", clear_on_submit=False):
                new_user = st.text_input("New Username", placeholder="choose a username")
                new_pass = st.text_input("New Password", type="password", placeholder="••••••••")
                
                st.markdown('<div style="font-family:var(--font-ui);font-size:12px;color:var(--text-3);margin-top:-8px;margin-bottom:12px;font-weight:500;">💡 รหัสผ่านต้องมี 8 ตัวอักษรขึ้นไป, ประกอบด้วย A-Z, a-z, 0-9 และอักขระพิเศษ</div>', unsafe_allow_html=True)
                
                confirm_pass = st.text_input("Confirm Password", type="password", placeholder="••••••••")
                
                reg_submitted = st.form_submit_button("CREATE ACCOUNT", use_container_width=True)

            if reg_submitted:
                now = datetime.datetime.now()
                elapsed = (now - st.session_state['reg_last_time']).total_seconds()
                
                if elapsed > 60:
                    st.session_state['reg_attempts'] = 0
                    st.session_state['reg_last_time'] = now

                if st.session_state['reg_attempts'] >= 3:
                    remaining = max(0, int(60 - elapsed))
                    st.error(f"⚠️ ใช้งานบ่อยเกินไป กรุณารอ {remaining} วินาที")
                elif new_user and new_pass and confirm_pass:
                    is_strong = sum([len(new_pass) >= 8, bool(re.search(r"[A-Z]", new_pass)), bool(re.search(r"[a-z]", new_pass)), bool(re.search(r"[0-9]", new_pass)), bool(re.search(r"[@$!%*?&_#^-]", new_pass))]) >= 5
                    
                    if new_pass != confirm_pass:
                        st.error("❌ รหัสผ่านไม่ตรงกัน (Passwords do not match!)")
                    elif not is_strong: 
                        st.error("❌ กรุณาตั้งรหัสผ่านให้ถูกต้องตามเงื่อนไข (STRONG level required)")
                    else:
                        res = supabase.table("userstable").select("username").eq("username", new_user).execute()
                        if len(res.data) > 0:
                            st.session_state['reg_attempts'] += 1
                            st.error("❌ ชื่อผู้ใช้นี้มีคนใช้แล้ว (Username already exists)")
                        else:
                            add_userdata(new_user, new_pass)
                            st.session_state['reg_attempts'] += 1
                            st.session_state['just_registered'] = True
                            st.rerun()
                else: 
                    st.warning("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน")

# ==========================================
# 6. Main Application
# ==========================================
def show_main_app():
    st.markdown(get_theme_css(), unsafe_allow_html=True)
    
    user_workspace = f"dataset_workspace_{st.session_state.get('username', 'default')}"
    init = st.session_state['username'][0].upper() if st.session_state['username'] else "?"
    
    col1, col2, col3 = st.columns([1, 0.85, 0.15])
    with col1:
        st.markdown("""
        <div class="top-brand" style="padding-top:20px;">
            <div class="hex">⬡</div>
            <h2>AI-Dataset Pro</h2>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="top-user" style="padding-top:20px;">
            <div style="text-align:right;">
                <div class="uname">{st.session_state['username']}</div>
                <div class="ustatus">● ACTIVE SESSION</div>
            </div>
            <div class="avatar">{init}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        frontend_theme_toggle()
        
    st.write("")

    is_admin = (st.session_state['username'].lower() == 'admin')

    menu_bg        = "#ffffff"
    menu_border    = "#e2e8f0"
    menu_text      = "#1e293b"
    menu_icon      = "#475569"
    menu_active_bg = "rgba(255, 107, 0, 0.1)"

    selected_menu = option_menu(
        menu_title=None,
        options=["Dashboard", "AI Engine", "Training Guide", "Logout"],
        icons=["grid-1x2", "cpu", "book", "box-arrow-right"],
        default_index=1,
        orientation="horizontal",
        styles={
            "container": { "background-color": menu_bg, "border": f"1px solid {menu_border}", "border-radius": "12px", "padding": "5px", "box-shadow": "0 4px 6px -1px rgba(0,0,0,0.02)", "margin-bottom": "30px" },
            "icon": {"color": menu_icon, "font-size": "16px"},
            "nav-link": { "font-size": "14px", "font-weight": "700", "color": menu_text, "font-family": "var(--font-display)", "border-radius": "8px", "padding": "10px", "margin": "0 4px" },
            "nav-link-selected": { "background-color": menu_active_bg, "color": "#ff6b00", "border": "1px solid rgba(255,107,0,0.3)" },
        }
    )

    if selected_menu == "Logout":
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()

    # ══════════════════════════════════════════
    if selected_menu == "AI Engine":
        st.markdown("""
        <div class="page-header">
            <div class="eyebrow">MODULE / AI ENGINE</div>
            <h1>Dataset Generation</h1>
            <div class="sub">สกัดข้อมูลภาพ คัดกรองคุณภาพ และเพิ่มจำนวนข้อมูล (Augmentation) อัตโนมัติด้วย AI</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="section-label">Neural Network Override</div>', unsafe_allow_html=True)
        custom_model_file = st.file_uploader("🧠 อัปโหลดไฟล์โมเดล .pt ที่เทรนเอง (ปล่อยว่างเพื่อใช้ YOLOv8n มาตรฐาน)", type=['pt'])

        @st.cache_resource
        def load_default_model():
            return YOLO('yolov8n.pt')

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

        with st.expander("⚙  NEURAL NETWORK & SYSTEM CONFIGURATION", expanded=True):
            col1, col2, col3, col4 = st.columns(4, gap="medium")
            with col1:
                st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">AI TARGETS</p>', unsafe_allow_html=True)
                default_classes = []
                if "person" in available_classes.values(): default_classes.append("person")
                elif len(available_classes) > 0: default_classes.append(available_classes[0])
                if "car" in available_classes.values(): default_classes.append("car")
                selected_class_names = st.multiselect("Detection Targets", list(available_classes.values()), default=default_classes, label_visibility="collapsed")
                selected_class_ids   = [k for k, v in available_classes.items() if v in selected_class_names]
                st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-top:10px;margin-bottom:6px;text-transform:uppercase;">CONFIDENCE (%)</p>', unsafe_allow_html=True)
                conf_threshold = st.slider("Min Confidence", 10, 90, 25, 5, label_visibility="collapsed") / 100.0
            
            with col2:
                st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">DATASET SPLIT</p>', unsafe_allow_html=True)
                split_ratio = st.slider("Train Split (%)", 50, 95, 80, label_visibility="collapsed")
                
                st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-top:10px;margin-bottom:6px;text-transform:uppercase;">SAMPLING MODE</p>', unsafe_allow_html=True)
                intel_sample = st.toggle("Intelligent Sampling", value=False, help="เฉพาะโหมดวิดีโอ: สุ่มตรวจจับเฉพาะวัตถุที่มีการเคลื่อนไหวเพื่อลดภาพซ้ำซ้อน")
                if not intel_sample:
                    frame_skip = st.slider("Frame Skip Interval", 1, 30, 5, label_visibility="collapsed")
                else:
                    move_thresh = st.slider("Movement Threshold (%)", 5, 50, 10, label_visibility="collapsed") / 100.0

            with col3:
                st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">DATA AUGMENTATION</p>', unsafe_allow_html=True)
                do_flip   = st.checkbox("Horizontal Flip")
                do_bright = st.checkbox("Brightness Boost")
                do_noise  = st.checkbox("Add Noise")
                do_gray   = st.checkbox("Grayscale (B&W)")       # 📌 ใหม่!
                do_cutout = st.checkbox("Random Cutout")         # 📌 ใหม่!
            with col4:
                st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">QUALITY CONTROL</p>', unsafe_allow_html=True)
                do_blur_filter = st.checkbox("Blur Filter", value=True)
                st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-top:10px;margin-bottom:6px;text-transform:uppercase;">THRESHOLD</p>', unsafe_allow_html=True)
                blur_threshold = st.slider("Blur Threshold", 20, 200, 60, label_visibility="collapsed")

            st.markdown('<hr style="margin:16px 0;">', unsafe_allow_html=True)
            col_tele_head, col_tele_toggle = st.columns([3, 1])
            with col_tele_head:
                st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:2px;text-transform:uppercase;">📱 TELEGRAM NOTIFICATION (OPTIONAL)</p>', unsafe_allow_html=True)
                st.markdown('<p style="font-family:var(--font-ui);font-size:11px;color:var(--text-3);margin-bottom:6px;">รับแจ้งเตือนผ่าน Telegram Bot เมื่อประมวลผลเสร็จสิ้น</p>', unsafe_allow_html=True)
            with col_tele_toggle:
                tele_enabled = st.toggle("Enable Notifications", value=True, key="tele_toggle")

            if tele_enabled:
                col_t1, col_t2, col_t3 = st.columns([2, 1.5, 1])
                with col_t1:
                    st.markdown('<p style="font-family:var(--font-display);font-size:10px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:4px;text-transform:uppercase;">🔑 Bot Token</p>', unsafe_allow_html=True)
                    tele_token = st.text_input("Bot Token", value="", type="password", placeholder="e.g. 123456789:AAF...", label_visibility="collapsed")
                with col_t2:
                    st.markdown('<p style="font-family:var(--font-display);font-size:10px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:4px;text-transform:uppercase;">💬 Chat ID</p>', unsafe_allow_html=True)
                    tele_chat_id = st.text_input("Chat ID", value="", placeholder="e.g. 849818556", label_visibility="collapsed")
                with col_t3:
                    st.markdown('<p style="font-family:var(--font-display);font-size:10px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-bottom:4px;text-transform:uppercase;">🧪 TEST</p>', unsafe_allow_html=True)
                    
                    test_msg = st.empty()
                    
                    if st.button("Send Test", use_container_width=True, key="btn_test_tele"):
                        if tele_token and tele_chat_id:
                            try:
                                resp = requests.post(f"https://api.telegram.org/bot{tele_token}/sendMessage", data={"chat_id": tele_chat_id, "text": f"✅ AI-Dataset Pro\nการเชื่อมต่อสำเร็จ!\n👤 {st.session_state['username']}"}, timeout=5)
                                if resp.status_code == 200:
                                    test_msg.success("✅ ส่งสำเร็จ!")
                                else:
                                    test_msg.error(f"❌ ขัดข้อง (API Error: {resp.status_code})")
                            except Exception as e: 
                                test_msg.error("❌ ขัดข้อง (โปรดตรวจสอบเน็ตหรือ Token)")
                        else: 
                            test_msg.warning("กรุณากรอกข้อมูล")
            else:
                tele_token, tele_chat_id = "", ""
                st.markdown('<p style="font-family:var(--font-ui);font-size:12px;color:var(--text-3);font-weight:500;padding:8px 0;">🔕 Notification ถูกปิดอยู่</p>', unsafe_allow_html=True)

        st.markdown('<div class="section-label">Media Source</div>', unsafe_allow_html=True)
        
        input_mode = st.radio("รูปแบบข้อมูล (Input Mode)", ["🎥 อัปโหลดวิดีโอ (Video Processing)", "🖼️ อัปโหลดรูปภาพ (Image Batch Processing)"], horizontal=True, label_visibility="collapsed")
        st.write("") 
        
        uploaded_videos = []
        uploaded_images = []
        start_sec, end_sec = 0.0, 0.0
        
        if input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)":
            uploaded_videos = st.file_uploader("Drop video files here (อัปโหลดได้หลายคลิป)", type=['mp4', 'avi', 'mov'], accept_multiple_files=True, label_visibility="collapsed")
        else:
            uploaded_images = st.file_uploader("Drop image files or a folder here (ลากโฟลเดอร์มาวางได้เลย)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, label_visibility="collapsed")
            st.info("💡 **เคล็ดลับ:** คุณสามารถ **คลุมดำรูปภาพหลายๆ ไฟล์** หรือคลิกที่ **โฟลเดอร์รูปภาพ** แล้วลากมาวาง (Drag & Drop) ในกล่องด้านบนได้เลยครับ!")

        has_media = (input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)" and len(uploaded_videos) > 0) or \
                    (input_mode == "🖼️ อัปโหลดรูปภาพ (Image Batch Processing)" and len(uploaded_images) > 0)

        if has_media:
            current_upload_name = f"batch_{len(uploaded_videos)}_videos" if input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)" else f"batch_{len(uploaded_images)}_images"
            if st.session_state.get('last_uploaded_file') != current_upload_name:
                st.session_state['process_done'] = False
                st.session_state['last_uploaded_file'] = current_upload_name
                if os.path.exists(user_workspace):
                    shutil.rmtree(user_workspace)

            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.markdown('<div class="col-header"><span class="dot-status dot-blue"></span>SOURCE</div>', unsafe_allow_html=True)
                if input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)":
                    st.info(f"🎥 พร้อมประมวลผลวิดีโอทั้งหมด: {len(uploaded_videos)} คลิป")
                    
                    if len(uploaded_videos) == 1:
                        st.video(uploaded_videos[0])
                        video_bytes = uploaded_videos[0].getvalue()
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tfile:
                            tfile.write(video_bytes)
                            video_path = tfile.name
                            
                        cap_temp = cv2.VideoCapture(video_path)
                        fps = cap_temp.get(cv2.CAP_PROP_FPS)
                        total_f = int(cap_temp.get(cv2.CAP_PROP_FRAME_COUNT))
                        duration = total_f / fps if fps > 0 else 0
                        cap_temp.release()

                        st.markdown('<p style="font-family:var(--font-display);font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:1px;margin-top:16px;margin-bottom:6px;text-transform:uppercase;">✂️ TRIM VIDEO (SELECT TIME RANGE)</p>', unsafe_allow_html=True)
                        start_sec, end_sec = st.slider(
                            "เลือกช่วงเวลา (วินาที)", 
                            0.0, float(duration), 
                            (0.0, float(duration)), 
                            step=0.1, format="%.1f s", 
                            label_visibility="collapsed"
                        )
                        st.markdown(f'<p style="font-size:12px;color:var(--accent);font-weight:600;">🕒 ระบบจะประมวลผลวิดีโอความยาว: {end_sec - start_sec:.1f} วินาที</p>', unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ โหมดเลือกช่วงเวลา (Trim) จะใช้งานได้เมื่ออัปโหลดวิดีโอทีละ 1 คลิปเท่านั้น ระบบจะทำการประมวลผลวิดีโอทั้งหมดแบบเต็มความยาว")
                        start_sec, end_sec = 0.0, float('inf') 
                else:
                    st.info(f"📂 พร้อมประมวลผลไฟล์รูปภาพจำนวน: {len(uploaded_images)} รูป")
                    if len(uploaded_images) > 0:
                        st.image(uploaded_images[0], caption="Preview (ตัวอย่างรูปภาพแรก)", use_container_width=True)

            with col2:
                st.markdown('<div class="col-header"><span class="dot-status dot-green"></span>AI VISION PREVIEW</div>', unsafe_allow_html=True)
                image_preview = st.empty()
                blur_warning  = st.empty()

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("▶  EXECUTE AI PROCESSING", use_container_width=True):
                output_folder = user_workspace
                if os.path.exists(output_folder): shutil.rmtree(output_folder)
                for f in ['images/train', 'images/val', 'labels/train', 'labels/val']:
                    os.makedirs(os.path.join(output_folder, f))

                progress_bar = st.progress(0)
                status_text  = st.empty()

                frame_count        = 0
                skipped_blur_count = 0
                dataset_records    = []
                class_counts = {n: 0 for n in selected_class_names} if selected_class_names else {v: 0 for v in available_classes.values()}

                # 📌 ปรับปรุงให้เก็บขนาดความกว้าง/สูง สำหรับทำ XML
                def save_data(img, boxes, modifier, is_flipped=False):
                    subset = "train" if random.random() < (split_ratio / 100.0) else "val"
                    
                    detected_classes = set()
                    for box in boxes:
                        cid = int(box.cls)
                        detected_classes.add(available_classes[cid])
                    
                    class_str = "_".join(sorted(list(detected_classes)))
                    if not class_str: class_str = "unlabeled"
                    
                    base_name = f"frame_{frame_count:06d}_{class_str}_{modifier}"
                    
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
                    dataset_records.append({"subset": subset, "file": base_name, "w": img.shape[1], "h": img.shape[0]})

                if input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)":
                    total_videos = len(uploaded_videos)
                    
                    for vid_idx, video_file in enumerate(uploaded_videos):
                        video_bytes = video_file.getvalue()
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tfile:
                            tfile.write(video_bytes)
                            video_path = tfile.name
                        
                        cap          = cv2.VideoCapture(video_path)
                        fps          = cap.get(cv2.CAP_PROP_FPS)
                        total_f      = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        
                        if total_videos == 1:
                            start_frame = int(start_sec * fps)
                            end_frame   = int(end_sec * fps)
                        else:
                            start_frame = 0
                            end_frame   = total_f
                        
                        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                        total_frames_to_process = end_frame - start_frame
                        if total_frames_to_process <= 0: total_frames_to_process = 1

                        last_pos = {} 
                        processed_count = 0
                        
                        while cap.isOpened():
                            current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                            if current_pos > end_frame:
                                break
                                
                            ret, frame = cap.read()
                            if not ret: break
                            
                            process_this_frame = False
                            boxes_to_save = None
                            plot_annotated = None

                            if intel_sample:
                                results = model.track(frame, persist=True, classes=selected_class_ids if selected_class_ids else None, conf=conf_threshold, verbose=False)
                                boxes = results[0].boxes
                                if len(boxes) > 0:
                                    if boxes.id is not None:
                                        ids = boxes.id.int().cpu().tolist()
                                        coords = boxes.xywhn.cpu().numpy()
                                        for obj_id, coord in zip(ids, coords):
                                            cx, cy = coord[0], coord[1]
                                            if obj_id not in last_pos:
                                                process_this_frame = True
                                            else:
                                                last_cx, last_cy = last_pos[obj_id]
                                                dist = np.sqrt((cx - last_cx)**2 + (cy - last_cy)**2)
                                                if dist > move_thresh:
                                                    process_this_frame = True
                                            
                                            if process_this_frame:
                                                last_pos[obj_id] = (cx, cy)
                                        
                                        if process_this_frame:
                                            boxes_to_save = boxes
                                            plot_annotated = results[0].plot()
                                    else:
                                        process_this_frame = True
                                        boxes_to_save = boxes
                                        plot_annotated = results[0].plot()
                            else:
                                if frame_count % frame_skip == 0:
                                    results = model(frame, classes=selected_class_ids if selected_class_ids else None, conf=conf_threshold, verbose=False)
                                    boxes = results[0].boxes
                                    if len(boxes) > 0:
                                        process_this_frame = True
                                        boxes_to_save = boxes
                                        plot_annotated = results[0].plot()

                            if process_this_frame and boxes_to_save is not None:
                                if do_blur_filter:
                                    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                                    score = cv2.Laplacian(gray, cv2.CV_64F).var()
                                    if score < blur_threshold:
                                        skipped_blur_count += 1
                                        blur_warning.markdown(f'<div style="color:var(--red);font-size:13px;font-weight:700;padding:8px;border:1px solid var(--red);border-radius:8px;background:var(--bg-surface);">⚠️ BLUR DETECTED (score:{score:.1f}) — FRAME SKIPPED</div>', unsafe_allow_html=True)
                                        process_this_frame = False
                                    else: blur_warning.empty()

                                if process_this_frame:
                                    save_data(frame, boxes_to_save, "original")
                                    if do_flip:   save_data(cv2.flip(frame, 1), boxes_to_save, "flip", is_flipped=True)
                                    if do_bright: save_data(cv2.convertScaleAbs(frame, alpha=1.2, beta=30), boxes_to_save, "bright")
                                    if do_noise:  save_data(cv2.add(frame, np.random.randint(0, 50, frame.shape, dtype='uint8')), boxes_to_save, "noise")
                                    
                                    # 📌 โค้ดสำหรับ Advanced Augmentation (Video)
                                    if do_gray:
                                        gray_img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                                        gray_3c = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)
                                        save_data(gray_3c, boxes_to_save, "gray")
                                        
                                    if do_cutout:
                                        cut_img = frame.copy()
                                        h_img, w_img = cut_img.shape[:2]
                                        for _ in range(random.randint(3, 7)):
                                            bx = random.randint(0, int(w_img*0.8))
                                            by = random.randint(0, int(h_img*0.8))
                                            bw = random.randint(10, max(20, int(w_img*0.15)))
                                            bh = random.randint(10, max(20, int(h_img*0.15)))
                                            cv2.rectangle(cut_img, (bx, by), (bx+bw, by+bh), (0,0,0), -1)
                                        save_data(cut_img, boxes_to_save, "cutout")

                                    image_preview.image(cv2.cvtColor(plot_annotated, cv2.COLOR_BGR2RGB), use_container_width=True)

                            frame_count += 1
                            processed_count += 1
                            
                            overall_progress = (vid_idx + (processed_count / total_frames_to_process)) / total_videos
                            progress_bar.progress(min(overall_progress, 1.0))
                            status_text.markdown(f'<div class="status-text">🎬 VIDEO {vid_idx+1}/{total_videos} | PROCESSING  {processed_count} / {total_frames_to_process}  FRAMES | EXTRACTED: {len(dataset_records)}</div>', unsafe_allow_html=True)
                        
                        cap.release()
                        try: os.remove(video_path)
                        except: pass
                
                else:
                    total_frames = len(uploaded_images)
                    for img_file in uploaded_images:
                        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
                        frame = cv2.imdecode(file_bytes, 1)
                        
                        results = model(frame, classes=selected_class_ids if selected_class_ids else None, conf=conf_threshold, verbose=False)
                        boxes = results[0].boxes
                        
                        process_this_frame = False
                        if len(boxes) > 0:
                            process_this_frame = True
                            boxes_to_save = boxes
                            plot_annotated = results[0].plot()

                        if process_this_frame:
                            if do_blur_filter:
                                gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                                score = cv2.Laplacian(gray, cv2.CV_64F).var()
                                if score < blur_threshold:
                                    skipped_blur_count += 1
                                    blur_warning.markdown(f'<div style="color:var(--red);font-size:13px;font-weight:700;padding:8px;border:1px solid var(--red);border-radius:8px;background:var(--bg-surface);">⚠️ BLUR DETECTED (score:{score:.1f}) — IMAGE SKIPPED</div>', unsafe_allow_html=True)
                                    process_this_frame = False
                                else: blur_warning.empty()

                            if process_this_frame:
                                save_data(frame, boxes_to_save, "original")
                                if do_flip:   save_data(cv2.flip(frame, 1), boxes_to_save, "flip", is_flipped=True)
                                if do_bright: save_data(cv2.convertScaleAbs(frame, alpha=1.2, beta=30), boxes_to_save, "bright")
                                if do_noise:  save_data(cv2.add(frame, np.random.randint(0, 50, frame.shape, dtype='uint8')), boxes_to_save, "noise")
                                
                                # 📌 โค้ดสำหรับ Advanced Augmentation (Image)
                                if do_gray:
                                    gray_img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                                    gray_3c = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)
                                    save_data(gray_3c, boxes_to_save, "gray")
                                    
                                if do_cutout:
                                    cut_img = frame.copy()
                                    h_img, w_img = cut_img.shape[:2]
                                    for _ in range(random.randint(3, 7)):
                                        bx = random.randint(0, int(w_img*0.8))
                                        by = random.randint(0, int(h_img*0.8))
                                        bw = random.randint(10, max(20, int(w_img*0.15)))
                                        bh = random.randint(10, max(20, int(h_img*0.15)))
                                        cv2.rectangle(cut_img, (bx, by), (bx+bw, by+bh), (0,0,0), -1)
                                    save_data(cut_img, boxes_to_save, "cutout")

                                image_preview.image(cv2.cvtColor(plot_annotated, cv2.COLOR_BGR2RGB), use_container_width=True)

                        frame_count += 1
                        progress_bar.progress(min(frame_count / total_frames, 1.0))
                        status_text.markdown(f'<div class="status-text">PROCESSING  {frame_count} / {total_frames}  IMAGES | EXTRACTED: {len(dataset_records)}</div>', unsafe_allow_html=True)

                blur_warning.empty()
                
                st.session_state['dataset_records'] = dataset_records
                st.session_state['class_counts'] = class_counts
                st.session_state['skipped_blur_count'] = skipped_blur_count
                st.session_state['process_done'] = True

                classes_for_yaml = selected_class_names if selected_class_names else list(available_classes.values())
                with open(os.path.join(user_workspace, "data.yaml"), 'w', encoding='utf-8') as yf:
                    yf.write("train: images/train\nval: images/val\n\n")
                    yf.write(f"nc: {len(classes_for_yaml)}\n")
                    yf.write(f"names: [{', '.join([repr(n) for n in classes_for_yaml])}]\n")

                zip_filename = f"ai_dataset_{st.session_state['username']}.zip"
                if os.path.exists(user_workspace):
                    with zipfile.ZipFile(zip_filename, 'w') as zipf:
                        for root, dirs, files in os.walk(user_workspace):
                            for file in files: 
                                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), user_workspace))

                add_history(st.session_state['username'], len(dataset_records), skipped_blur_count)

                if tele_token and tele_chat_id:
                    send_telegram_notify(tele_token, tele_chat_id,
                        f"✅ AI-Dataset Pro ทำงานเสร็จสิ้น!\n👤 ผู้ใช้งาน: {st.session_state['username']}\n📸 สกัดรูปภาพได้: {len(dataset_records)} รูป\n❌ เตะภาพเบลอทิ้ง: {skipped_blur_count} รูป")

                st.rerun()

            # 🖼️ POST-PROCESSING (GALLERY, ANALYTICS & DOWNLOAD)
            if st.session_state.get('process_done'):
                dataset_records = st.session_state['dataset_records']
                class_counts    = st.session_state['class_counts']
                skipped_blur_count = st.session_state['skipped_blur_count']

                if len(dataset_records) > 0:
                    st.markdown('<hr style="margin:40px 0 20px;">', unsafe_allow_html=True)
                    st.markdown('<div class="section-label" style="color:var(--accent);">🖼️ Gallery & Edit Dataset</div>', unsafe_allow_html=True)
                    st.info("ตรวจสอบความถูกต้องของภาพ เลื่อนดูภาพทั้งหมด และ ติ๊ก ❌ ใต้ภาพที่คุณต้องการลบออกจาก Dataset จากนั้นกดปุ่มยืนยันด้านล่าง")
                    
                    with st.spinner(f"⏳ กำลังโหลดและจัดเรียงรูปภาพทั้งหมด {len(dataset_records)} รูป... อาจใช้เวลาสักครู่หากข้อมูลมีขนาดใหญ่"):
                        with st.form("gallery_form"):
                            with st.container(height=450):
                                cols = st.columns(4)
                                delete_flags = {}
                                
                                for i, r in enumerate(dataset_records):
                                    img_path = f"{user_workspace}/images/{r['subset']}/{r['file']}.jpg"
                                    if os.path.exists(img_path):
                                        with cols[i % 4]:
                                            st.image(img_path, use_container_width=True)
                                            delete_flags[r['file']] = st.checkbox(f"❌ ลบ {r['file']}", key=f"del_{r['file']}")
                                
                            if st.form_submit_button("🗑️ ยืนยันการลบภาพที่เลือก", use_container_width=True):
                                new_records = []
                                deleted_qty = 0
                                for r in dataset_records:
                                    if delete_flags.get(r['file']):
                                        img_p = f"{user_workspace}/images/{r['subset']}/{r['file']}.jpg"
                                        txt_p = f"{user_workspace}/labels/{r['subset']}/{r['file']}.txt"
                                        if os.path.exists(img_p): os.remove(img_p)
                                        if os.path.exists(txt_p): os.remove(txt_p)
                                        deleted_qty += 1
                                    else:
                                        new_records.append(r)
                                
                                if deleted_qty > 0:
                                    st.session_state['dataset_records'] = new_records
                                    
                                    updated_class_counts = {}
                                    for r in new_records:
                                        txt_p = f"{user_workspace}/labels/{r['subset']}/{r['file']}.txt"
                                        if os.path.exists(txt_p):
                                            with open(txt_p, 'r') as f:
                                                for line in f:
                                                    if line.strip():
                                                        lbl_id = int(line.split()[0])
                                                        name = selected_class_names[lbl_id] if selected_class_names else available_classes.get(lbl_id, str(lbl_id))
                                                        updated_class_counts[name] = updated_class_counts.get(name, 0) + 1
                                    st.session_state['class_counts'] = updated_class_counts

                                    zip_filename = f"ai_dataset_{st.session_state['username']}.zip"
                                    if os.path.exists(user_workspace):
                                        with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                            for root, dirs, files in os.walk(user_workspace):
                                                for file in files: 
                                                    zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), user_workspace))

                                    st.success(f"ลบภาพขยะสำเร็จ {deleted_qty} รูป! โครงสร้าง Dataset อัปเดตพร้อมดาวน์โหลดแล้ว")
                                    st.rerun()
                                else:
                                    st.info("ไม่ได้เลือกภาพที่ต้องการลบ")

                    st.markdown('<hr style="margin:20px 0;">', unsafe_allow_html=True)
                    st.markdown('<div class="section-label" style="color:var(--accent);">🚀 Dataset Overview</div>', unsafe_allow_html=True)
                    
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

                    st.markdown('<div class="section-label" style="color:var(--blue); margin-top: 36px;">📊 Data Analytics (วิเคราะห์คุณภาพ Dataset)</div>', unsafe_allow_html=True)
                    
                    if len(class_counts) > 0:
                        df_classes = pd.DataFrame(list(class_counts.items()), columns=['Class', 'Objects Detected'])
                        df_classes = df_classes.set_index('Class')
                        
                        col_c1, col_c2 = st.columns([1.5, 1], gap="large")
                        with col_c1:
                            st.bar_chart(df_classes, color="#3b82f6")
                        with col_c2:
                            st.markdown('<p style="font-family:var(--font-display);font-size:13px;font-weight:800;color:var(--text-1);margin-bottom:8px;">⚖️ ความสมดุลของข้อมูล</p>', unsafe_allow_html=True)
                            
                            max_class = max(class_counts.values()) if class_counts.values() else 0
                            min_class = min(class_counts.values()) if class_counts.values() else 0
                            
                            if max_class == 0:
                                st.warning("ไม่พบวัตถุใดๆ ใน Dataset นี้")
                            elif len(class_counts) == 1:
                                st.info("💡 **Single-Class Dataset:** ตรวจจับเพียงคลาสเดียว ถือว่าสมดุลดีสำหรับการเทรนเฉพาะทาง")
                            else:
                                ratio = min_class / max_class
                                if ratio < 0.3:
                                    st.error("⚠️ **Imbalance Detected!**\n\nมีบางคลาสที่ข้อมูลน้อยกว่าคลาสหลักมากเกินไป แนะนำให้อัปโหลดภาพของคลาสนั้นเพิ่ม เพื่อป้องกัน AI ลำเอียง (Bias)")
                                elif ratio < 0.6:
                                    st.warning("🚧 **Slight Imbalance**\n\nข้อมูลค่อนข้างเอียง ควรเพิ่มรูปของคลาสที่น้อยกว่าเพื่อประสิทธิภาพที่ดีขึ้น")
                                else:
                                    st.success("✅ **Well Balanced!**\n\nจำนวนข้อมูลแต่ละคลาสกระจายตัวได้ดีมาก เหมาะแก่การนำไปเทรนสุดๆ")
                            
                            st.markdown("<hr style='margin:12px 0;'>", unsafe_allow_html=True)
                            st.markdown('<p style="font-size:12px;font-weight:700;color:var(--text-3);margin-bottom:8px;">จำนวน Label ทั้งหมดแยกตามคลาส:</p>', unsafe_allow_html=True)
                            for c, v in class_counts.items():
                                st.markdown(f"- **{c}**: {v} ตัว")

                    st.divider()
                    
                    # 📌 2. เพิ่ม UI ให้เลือกรูปแบบไฟล์ก่อน Export (Multi-Format Export)
                    st.markdown('<div class="section-label" style="color:var(--accent);">📦 Export Options (รูปแบบไฟล์ Dataset)</div>', unsafe_allow_html=True)
                    export_format = st.radio("เลือกรูปแบบข้อมูลที่ต้องการดาวน์โหลด:", ["YOLOv8 (.txt) - สำหรับ YOLO Framework", "Pascal VOC (.xml) - สำหรับโมเดลและโปรแกรม AI อื่นๆ"], horizontal=True, label_visibility="collapsed")
                    
                    zip_filename = f"ai_dataset_{st.session_state['username']}.zip"
                    
                    with st.spinner(f"⏳ กำลังประมวลผลและแพ็กไฟล์เป็นรูปแบบ {export_format.split(' ')[0]} กรุณารอ..."):
                        if "YOLOv8" in export_format:
                            if os.path.exists(user_workspace):
                                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                    for root, dirs, files in os.walk(user_workspace):
                                        for file in files: 
                                            zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), user_workspace))
                        else: # ระบบแปลงเป็น Pascal VOC
                            voc_workspace = f"{user_workspace}_voc"
                            if os.path.exists(voc_workspace): shutil.rmtree(voc_workspace)
                            os.makedirs(f"{voc_workspace}/JPEGImages")
                            os.makedirs(f"{voc_workspace}/Annotations")
                            
                            classes_for_yaml = selected_class_names if selected_class_names else list(available_classes.values())
                            
                            for r in dataset_records:
                                img_src = f"{user_workspace}/images/{r['subset']}/{r['file']}.jpg"
                                txt_src = f"{user_workspace}/labels/{r['subset']}/{r['file']}.txt"
                                if os.path.exists(img_src) and os.path.exists(txt_src):
                                    shutil.copy(img_src, f"{voc_workspace}/JPEGImages/{r['file']}.jpg")
                                    
                                    width, height = r.get('w', 640), r.get('h', 640)
                                    xml_content = f"<annotation>\n  <folder>JPEGImages</folder>\n  <filename>{r['file']}.jpg</filename>\n  <size>\n    <width>{width}</width>\n    <height>{height}</height>\n    <depth>3</depth>\n  </size>\n"
                                    
                                    with open(txt_src, 'r') as f:
                                        for line in f:
                                            if not line.strip(): continue
                                            parts = line.strip().split()
                                            cid = int(parts[0])
                                            x_c, y_c, w_n, h_n = map(float, parts[1:5])
                                            cname = classes_for_yaml[cid] if cid < len(classes_for_yaml) else str(cid)
                                            
                                            xmin = int((x_c - w_n/2) * width)
                                            ymin = int((y_c - h_n/2) * height)
                                            xmax = int((x_c + w_n/2) * width)
                                            ymax = int((y_c + h_n/2) * height)
                                            
                                            xml_content += f"  <object>\n    <name>{cname}</name>\n    <bndbox>\n      <xmin>{max(0, xmin)}</xmin>\n      <ymin>{max(0, ymin)}</ymin>\n      <xmax>{min(width, xmax)}</xmax>\n      <ymax>{min(height, ymax)}</ymax>\n    </bndbox>\n  </object>\n"
                                    xml_content += "</annotation>"
                                    
                                    with open(f"{voc_workspace}/Annotations/{r['file']}.xml", 'w', encoding='utf-8') as f:
                                        f.write(xml_content)
                                        
                            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                for root, dirs, files in os.walk(voc_workspace):
                                    for file in files: 
                                        zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), voc_workspace))

                    st.success("🎉 Dataset พร้อมนำไปเทรนแล้ว!")
                    if os.path.exists(zip_filename):
                        with open(zip_filename, "rb") as fp:
                            st.download_button(
                                label="⬇  DOWNLOAD DATASET (ZIP)", 
                                data=fp, 
                                file_name=zip_filename, 
                                mime="application/zip", 
                                use_container_width=True
                            )

    # ══════════════════════════════════════════
    elif selected_menu == "Training Guide":
        st.markdown("""
        <div class="page-header">
            <div class="eyebrow">MODULE / KNOWLEDGE BASE</div>
            <h1>YOLOv8 Training Guide</h1>
            <div class="sub">คู่มือการนำ Dataset ที่สกัดได้ ไปสอน (Train) AI ของคุณเองบน Google Colab แบบจับมือทำ</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="section-label">Step 1: เตรียมไฟล์และพื้นที่ทำงาน</div>', unsafe_allow_html=True)
        st.info("1. ดาวน์โหลดไฟล์ ZIP Dataset จากเมนู **AI Engine**\n2. นำไฟล์ ZIP ไปอัปโหลดเก็บไว้ใน **Google Drive** ของคุณ")
        st.markdown('<a href="https://colab.research.google.com/" target="_blank" style="text-decoration:none;"><div style="background:var(--accent);color:white;padding:12px 24px;border-radius:8px;text-align:center;font-weight:800;font-family:var(--font-display);margin:16px 0 32px;width:250px;box-shadow: 0 4px 6px rgba(255,107,0,0.2); transition: 0.2s;">🚀 เปิด Google Colab</div></a>', unsafe_allow_html=True)

        st.markdown('<div class="section-label">Step 2: ติดตั้งเครื่องมือและแตกไฟล์</div>', unsafe_allow_html=True)
        st.markdown("เปิด Google Colab สร้างสมุดโน้ตใหม่ (New Notebook) แล้วก๊อปปี้โค้ดด้านล่างนี้ไปรันในช่องแรก เพื่อเชื่อมต่อ Google Drive และลงเครื่องมือ AI")
        st.code("""# 1. เชื่อมต่อ Google Drive
from google.colab import drive
drive.mount('/content/drive')

# 2. ติดตั้งไลบรารี YOLOv8
!pip install ultralytics

# 3. แตกไฟล์ Dataset (เปลี่ยนชื่อไฟล์ ai_dataset.zip ให้ตรงกับของคุณ)
!unzip "/content/drive/MyDrive/ai_dataset.zip" -d "/content/dataset"
        """, language="python")

        st.markdown('<div class="section-label" style="margin-top:32px;">Step 3: เริ่มเทรนโมเดล (Train AI)</div>', unsafe_allow_html=True)
        st.markdown("เพิ่มช่องโค้ดใหม่ (New Code Cell) แล้วรันคำสั่งด้านล่างเพื่อเริ่มสอน AI ของคุณ")
        st.code("""from ultralytics import YOLO

# โหลดโมเดลตั้งต้น (n = nano, รันได้เร็วและเบาที่สุด)
model = YOLO('yolov8n.pt') 

# เริ่มเทรน! (สามารถปรับ epochs หรือ batch ได้ตามความเหมาะสม)
results = model.train(
    data='/content/dataset/data.yaml',  # ไฟล์ชี้เป้า Dataset
    epochs=50,                          # จำนวนรอบที่ให้ AI เรียนรู้ซ้ำๆ (แนะนำ 50-100)
    imgsz=640,                          # ขนาดรูปภาพที่ใช้เทรน
    batch=16,                           # จำนวนรูปที่ประมวลผลต่อ 1 รอบ
    name='my_custom_ai'                 # ชื่อโฟลเดอร์เก็บผลลัพธ์
)
        """, language="python")

        st.markdown('<div class="section-label" style="margin-top:32px;">Step 4: นำโมเดลกลับมาใช้งาน</div>', unsafe_allow_html=True)
        st.success("✅ เมื่อการเทรนเสร็จสมบูรณ์ โมเดลที่เก่งที่สุดของคุณจะถูกบันทึกไว้ในโฟลเดอร์ฝั่งซ้ายมือของ Colab ที่เส้นทาง:\n\n👉 `runs/detect/my_custom_ai/weights/best.pt`")
        st.markdown("คุณสามารถดาวน์โหลดไฟล์ **`best.pt`** ไปใส่ช่อง **🧠 Neural Network Override** เพื่อใช้งานได้เลยครับ! 🎉")

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
            res_users = supabase.table("userstable").select("username", count="exact").execute()
            total_users = res_users.count if res_users.count else len(res_users.data)
            
            hist_res = supabase.table("historytable").select("*").order("timestamp", desc=True).execute()
            df_history = pd.DataFrame(hist_res.data) if hist_res.data else pd.DataFrame(columns=['username', 'total_img', 'blur_skip', 'timestamp'])
        else:
            total_users = 1
            hist_res = supabase.table("historytable").select("*").eq("username", st.session_state['username']).order("timestamp", desc=True).execute()
            df_history = pd.DataFrame(hist_res.data) if hist_res.data else pd.DataFrame(columns=['username', 'total_img', 'blur_skip', 'timestamp'])

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
                <div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:40px;text-align:center;">
                    <div style="font-family:var(--font-display);font-size:13px;font-weight:700;color:var(--text-3);letter-spacing:1px;">NO DATA YET</div>
                    <div style="font-size:14px;color:var(--text-2);margin-top:8px;">Run the AI Engine to see your trends here</div>
                </div>
                """, unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="section-label">Recent Activity</div>', unsafe_allow_html=True)
            if not df_history.empty:
                display_df = df_history[['username', 'total_img', 'timestamp']].head(8).copy()
                display_df.columns = ['User', 'Images', 'Time']
                html_table = display_df.to_html(index=False, classes="custom-table", border=0)
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-family:var(--font-ui);font-size:13px;color:var(--text-3);font-weight:500;">No recent activity</div>', unsafe_allow_html=True)

# ── ROUTER ──
if st.session_state['current_page'] == 'landing': show_landing_page()
elif st.session_state['current_page'] == 'auth':  show_auth_page()
elif st.session_state['current_page'] == 'main':  show_main_app()