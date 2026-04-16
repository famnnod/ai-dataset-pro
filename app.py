import streamlit as st
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

# ── State Management ──
if 'current_page'    not in st.session_state: st.session_state['current_page']    = 'landing'
if 'logged_in'       not in st.session_state: st.session_state['logged_in']       = False
if 'username'        not in st.session_state: st.session_state['username']         = ""
if 'reg_attempts'    not in st.session_state: st.session_state['reg_attempts']     = 0
if 'reg_last_time'   not in st.session_state: st.session_state['reg_last_time']    = datetime.datetime.now()
if 'just_registered' not in st.session_state: st.session_state['just_registered']  = False

if 'process_done'       not in st.session_state: st.session_state['process_done']       = False
if 'last_uploaded_file' not in st.session_state: st.session_state['last_uploaded_file'] = ""
if 'dataset_records'    not in st.session_state: st.session_state['dataset_records']    = []
if 'class_counts'       not in st.session_state: st.session_state['class_counts']       = {}
if 'skipped_blur_count' not in st.session_state: st.session_state['skipped_blur_count'] = 0

if st.session_state['logged_in']:
    st.session_state['current_page'] = 'main'

# ==========================================
# 3. Global CSS (Modern Tech Fonts)
# ==========================================
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Outfit:wght@400;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

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
    --blue:        #3b82f6;
    --text-1:      #0f172a;
    --text-2:      #1e293b;
    --text-3:      #475569;
    --font-display:'Outfit', sans-serif;
    --font-ui:     'Plus Jakarta Sans', sans-serif;
    --font-mono:   'DM Mono', monospace;
    --r:           10px;
    --r-lg:        16px;
}

html, body, .stApp { background-color: var(--bg-deep) !important; color: var(--text-1) !important; font-family: var(--font-ui); }

[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
header[data-testid="stHeader"] { background-color: transparent !important; border-bottom: none !important; box-shadow: none !important; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
.appview-container { background-color: var(--bg-deep) !important; }
.main > div { padding-top: 0 !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 3px; }

/* ── TOP HEADER (App) ── */
.top-brand { display: flex; align-items: center; gap: 12px; }
.top-brand .hex { width: 36px; height: 36px; background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.3); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; color: var(--accent); font-weight: 800; }
.top-brand h2 { font-size: 20px !important; font-weight: 800 !important; color: var(--text-1) !important; margin: 0 !important; letter-spacing: -0.5px; font-family: var(--font-display) !important; }
.top-user { display: flex; align-items: center; gap: 12px; justify-content: flex-end; padding: 4px 0; }
.top-user .avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--accent); color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; box-shadow: 0 2px 4px rgba(255,107,0,0.3); }
.top-user .uname { font-size: 14px; font-weight: 800; color: var(--text-1) !important; line-height: 1.2; text-transform: uppercase; font-family: var(--font-display) !important; }
.top-user .ustatus { font-size: 11px; font-weight: 700; color: var(--green); letter-spacing: 0.5px; }

/* ── PAGE HEADER (App) ── */
.page-header { padding: 12px 0 24px; border-bottom: 2px solid var(--border); margin-bottom: 32px; }
.page-header .eyebrow { font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; }
.page-header h1 { font-size: 32px !important; font-weight: 800 !important; color: var(--text-1) !important; margin: 0 !important; letter-spacing: -1px; line-height: 1.2 !important; font-family: var(--font-display) !important; }
.page-header .sub { font-size: 15px; font-weight: 500; color: var(--text-2); margin-top: 8px; }

/* ── LABELS & TEXTS ── */
.section-label { font-family: var(--font-display); font-size: 14px; font-weight: 800; color: var(--text-1) !important; letter-spacing: 1px; text-transform: uppercase; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.section-label::before { content: ''; width: 16px; height: 4px; background: var(--accent); display: inline-block; border-radius: 2px; }
.col-header { font-family: var(--font-display); font-size: 11px; font-weight: 800; color: var(--text-1) !important; letter-spacing: 1px; text-transform: uppercase; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.dot-status { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-blue  { background: var(--text-1); }
.dot-green { background: var(--accent); }
.dot-red   { background: var(--red); }

/* ── STAT PILLS ── */
.stat-row  { display: flex; gap: 16px; margin-top: 16px; flex-wrap: wrap; }
.stat-pill { flex: 1; min-width: 130px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 20px 16px; text-align: left; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); transition: transform 0.2s; }
.stat-pill:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); }
.stat-pill .sp-label { font-family: var(--font-display); font-size: 11px; font-weight: 700; color: var(--text-2); letter-spacing: 0.5px; text-transform: uppercase; display: block; margin-bottom: 8px; }
.stat-pill .sp-val { font-size: 28px; font-weight: 800; color: var(--text-1); letter-spacing: -0.5px; font-family: var(--font-display); }

/* ── FORMS & BUTTONS ── */
[data-testid="stForm"] { border: none !important; padding: 0 !important; }
.stButton > button { font-family: var(--font-display) !important; font-size: 14px !important; font-weight: 700 !important; border-radius: 8px !important; border: 1px solid var(--border-hi) !important; background: var(--bg-surface) !important; color: var(--text-1) !important; transition: all 0.2s ease !important; padding: 10px 24px !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; }
.stButton > button:hover { border-color: var(--accent) !important; background: var(--bg-raised) !important; color: var(--accent) !important; }
.stDownloadButton > button { font-family: var(--font-display) !important; font-weight: 800 !important; font-size: 14px !important; border-radius: 8px !important; background: var(--accent) !important; color: white !important; border: none !important; padding: 12px 24px !important; box-shadow: 0 4px 6px rgba(255,107,0,0.2) !important; }
.stDownloadButton > button:hover { opacity: 0.9 !important; transform: translateY(-1px) !important; }

/* ── INPUTS ── */
.stTextInput > label, .stMultiselect > label, .stSlider > label, .stFileUploader > label, .stRadio > label { font-family: var(--font-ui) !important; font-size: 12px !important; font-weight: 700 !important; color: var(--text-1) !important; margin-bottom: 8px !important; }
.stCheckbox > label span { font-weight: 600 !important; color: var(--text-1) !important; }
.stTextInput > div > div > input { background: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; border-radius: 8px !important; color: var(--text-1) !important; font-size: 14px !important; padding: 12px 16px !important; transition: all 0.2s !important; }
.stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-dim) !important; }
.stTextInput > div > div > input::placeholder { color: var(--text-3) !important; }
[data-baseweb="select"] > div { background: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; border-radius: 8px !important; transition: all 0.2s !important; }
[data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-dim) !important; }
[data-baseweb="tag"] { background: var(--accent-dim) !important; border: none !important; border-radius: 6px !important; padding: 4px 8px !important; }
[data-baseweb="tag"] span { color: var(--accent) !important; font-size: 12px !important; font-weight: 700 !important; }

/* ── EXPANDER & TABS ── */
[data-testid="stExpander"] { background: var(--bg-surface) !important; border: 1px solid var(--border) !important; border-radius: var(--r-lg) !important; margin-bottom: 24px !important; overflow: hidden !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02) !important; }
[data-testid="stExpander"] summary { font-family: var(--font-display) !important; font-size: 13px !important; font-weight: 700 !important; color: var(--text-1) !important; padding: 16px 24px !important; background: var(--bg-raised) !important; border-bottom: 1px solid var(--border) !important; }
[data-testid="stExpander"] summary:hover { background: var(--bg-hover) !important; }
[data-testid="stExpander"] > div > div { padding: 24px !important; }
.stTabs [data-baseweb="tab-list"] { background: transparent !important; border-bottom: 1px solid var(--border) !important; gap: 16px !important; }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: var(--text-3) !important; border: none !important; font-family: var(--font-display) !important; font-size: 13px !important; font-weight: 700 !important; letter-spacing: 0.5px !important; text-transform: uppercase !important; padding: 12px 4px !important; border-radius: 0 !important; transition: color 0.2s; }
.stTabs [data-baseweb="tab"]:hover { color: var(--text-1) !important; }
.stTabs [aria-selected="true"] { color: var(--accent) !important; border-bottom: 3px solid var(--accent) !important; font-weight: 800 !important; }
.stTabs [data-baseweb="tab-panel"] { padding: 32px 0 0 !important; }
.stProgress > div > div { background: var(--border) !important; border-radius: 4px !important; height: 6px !important; }
.stProgress > div > div > div { background: var(--accent) !important; height: 6px !important; border-radius: 4px !important; }

/* ── ALERTS & OTHERS ── */
[data-testid="stAlert"] { background: var(--bg-surface) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; font-family: var(--font-ui) !important; font-size: 14px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important; }
[data-testid="stAlert"][data-type="success"] { border-left: 4px solid var(--green) !important; }
[data-testid="stAlert"][data-type="error"]   { border-left: 4px solid var(--red) !important; }
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 32px 0 !important; }
[data-testid="stFileUploaderDropzone"] { background: var(--bg-surface) !important; border: 2px dashed var(--border-hi) !important; border-radius: var(--r-lg) !important; padding: 40px 24px !important; transition: all 0.2s ease !important; }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent) !important; background: var(--accent-dim) !important; }
[data-testid="stFileUploaderDropzone"] button { background: var(--bg-surface) !important; border: 1px solid var(--border-hi) !important; color: var(--text-1) !important; border-radius: 8px !important; font-family: var(--font-display) !important; font-size: 13px !important; font-weight: 700 !important; padding: 8px 16px !important; }
video { border-radius: 12px !important; border: 1px solid var(--border) !important; width: 100% !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important; }
[data-testid="stImage"] img { border-radius: 12px !important; border: 1px solid var(--border) !important; width: 100% !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important; }
.stMarkdown p { color: var(--text-1) !important; font-size: 15px !important; font-family: var(--font-ui) !important; font-weight: 500 !important; line-height: 1.6 !important; }
.main .block-container { padding: 0 2rem 2rem !important; max-width: 1200px; }

/* ── Landing Page Specific ── */
.land-logo-badge { font-family: var(--font-mono); font-size: 9px; font-weight: 700; color: var(--accent); background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.2); border-radius: 4px; padding: 2px 6px; letter-spacing: 1.5px; text-transform: uppercase; margin-left: 4px; vertical-align: middle; }
.hero-eyebrow { display: inline-flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.25); border-radius: 100px; padding: 6px 14px; margin-bottom: 28px; }
.hero-eyebrow .pulse { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); animation: pulse-dot 1.8s ease-in-out infinite; }
@keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.7); } }
.hero-title { font-family: var(--font-display) !important; font-size: 60px !important; font-weight: 900 !important; color: var(--text-1) !important; margin: 0 0 16px !important; letter-spacing: -2px; line-height: 1.05 !important; }
.hero-title .accent-word { color: var(--accent); position: relative; display: inline-block; }
.hero-sub { font-size: 17px !important; font-weight: 400 !important; color: var(--text-3) !important; margin: 0 0 40px !important; line-height: 1.75 !important; max-width: 500px; }
.hero-stats { display: flex; align-items: center; gap: 28px; padding: 18px 24px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); max-width: 480px; margin-top: 32px; }
.hero-stat-num { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--text-1); letter-spacing: -1px; line-height: 1; }
.hero-stat-label { font-size: 10px; font-weight: 600; color: var(--text-3); letter-spacing: 0.5px; margin-top: 3px; text-transform: uppercase; }
.hero-stat-div { width: 1px; height: 32px; background: var(--border); }
.hero-visual { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 20px; overflow: hidden; box-shadow: 0 20px 48px -12px rgba(0,0,0,0.10); }
.hero-visual-bar { background: var(--bg-raised); border-bottom: 1px solid var(--border); padding: 13px 18px; display: flex; align-items: center; gap: 6px; }
.win-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.hero-visual-body { padding: 18px; }
.mock-label { font-family: var(--font-mono); font-size: 10px; font-weight: 600; color: var(--text-3); letter-spacing: 1px; text-transform: uppercase; display: flex; justify-content: space-between; margin-bottom: 5px; }
.mock-bar-bg { width: 100%; height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; margin-bottom: 14px; }
.mock-bar-fill { height: 100%; border-radius: 3px; background: var(--accent); animation: fill-anim 2.6s ease-in-out infinite alternate; }
@keyframes fill-anim { from { width: 38%; } to { width: 79%; } }
.mock-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; }
.mock-thumb { aspect-ratio: 4/3; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); position: relative; display: flex; align-items: center; justify-content: center; }
.mock-thumb-label { position: absolute; bottom: 5px; left: 5px; font-family: var(--font-mono); font-size: 9px; font-weight: 700; color: white; background: rgba(0,0,0,0.5); padding: 2px 5px; border-radius: 3px; letter-spacing: 0.5px; }
.mock-detect-box { position: absolute; border: 2px solid var(--accent); border-radius: 3px; animation: box-pulse 2s ease-in-out infinite; }
@keyframes box-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }
.mock-stat-row { display: flex; gap: 7px; margin-top: 10px; }
.mock-stat { flex: 1; background: var(--bg-raised); border-radius: 8px; padding: 9px 10px; border: 1px solid var(--border); }
.mock-stat-n { font-family: var(--font-display); font-size: 17px; font-weight: 800; color: var(--text-1); }
.mock-stat-l { font-family: var(--font-mono); font-size: 9px; font-weight: 600; color: var(--text-3); letter-spacing: 0.8px; text-transform: uppercase; }

.section-sep { display: flex; align-items: center; gap: 16px; padding: 56px 0 44px; }
.section-sep-line { flex: 1; height: 1px; background: var(--border); }
.section-sep-label { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-3); letter-spacing: 2px; text-transform: uppercase; white-space: nowrap; }
.features-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; margin-bottom: 60px; }
.feat-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 18px; padding: 26px 22px; transition: all 0.3s ease; position: relative; overflow: hidden; }
.feat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, var(--accent), transparent); opacity: 0; transition: opacity 0.3s; }
.feat-card:hover { transform: translateY(-4px); border-color: rgba(255,107,0,0.3); box-shadow: 0 16px 32px -8px rgba(255,107,0,0.1); }
.feat-card:hover::before { opacity: 1; }
.feat-icon-wrap { width: 42px; height: 42px; border-radius: 11px; background: var(--accent-dim); border: 1px solid rgba(255,107,0,0.2); display: flex; align-items: center; justify-content: center; font-size: 20px; margin-bottom: 16px; }
.feat-title { font-family: var(--font-display); font-size: 16px; font-weight: 700; color: var(--text-1); margin-bottom: 9px; letter-spacing: -0.3px; }
.feat-desc { font-size: 13px; color: var(--text-3); line-height: 1.65; }
.feat-tag { display: inline-block; margin-top: 13px; font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--accent); background: var(--accent-dim); border-radius: 4px; padding: 3px 8px; letter-spacing: 1px; text-transform: uppercase; }

.steps-row { display: flex; gap: 0; margin-bottom: 60px; position: relative; }
.steps-row::before { content: ''; position: absolute; top: 23px; left: 48px; right: 48px; height: 1px; background: repeating-linear-gradient(90deg, var(--border) 0, var(--border) 6px, transparent 6px, transparent 12px); z-index: 0; }
.step-item { flex: 1; text-align: center; position: relative; z-index: 1; padding: 0 10px; }
.step-num { width: 46px; height: 46px; border-radius: 50%; background: var(--bg-surface); border: 2px solid var(--border); display: flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 15px; font-weight: 800; color: var(--text-3); margin: 0 auto 14px; transition: all 0.3s; }
.step-item:hover .step-num { background: var(--accent); border-color: var(--accent); color: white; box-shadow: 0 6px 14px rgba(255,107,0,0.3); }
.step-title { font-family: var(--font-display); font-size: 13px; font-weight: 700; color: var(--text-1); margin-bottom: 5px; }
.step-desc { font-size: 12px; color: var(--text-3); line-height: 1.5; }

.cta-banner { background: var(--text-1); border-radius: 24px; padding: 52px 44px; margin-bottom: 60px; display: flex; align-items: center; justify-content: space-between; gap: 32px; position: relative; overflow: hidden; }
.cta-banner::before { content: ''; position: absolute; top: -60px; right: -60px; width: 260px; height: 260px; border-radius: 50%; background: radial-gradient(circle, rgba(255,107,0,0.22) 0%, transparent 70%); pointer-events: none; }
.cta-banner::after { content: ''; position: absolute; bottom: -80px; left: 30%; width: 180px; height: 180px; border-radius: 50%; background: radial-gradient(circle, rgba(255,107,0,0.1) 0%, transparent 70%); pointer-events: none; }
.cta-banner-eyebrow { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 12px; }
.cta-banner-title { font-family: var(--font-display); font-size: 32px; font-weight: 800; color: white; letter-spacing: -1px; line-height: 1.2; margin-bottom: 10px; }
.cta-banner-sub { font-size: 14px; color: rgba(255,255,255,0.55); line-height: 1.5; max-width: 380px; }

.land-footer { border-top: 1px solid var(--border); padding: 28px 0; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.land-footer-left { font-family: var(--font-mono); font-size: 11px; color: var(--text-3); font-weight: 600; letter-spacing: 0.5px; }
.land-footer-tags { display: flex; gap: 8px; }
.land-footer-tag { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-3); background: var(--bg-raised); border: 1px solid var(--border); border-radius: 4px; padding: 3px 8px; letter-spacing: 1px; text-transform: uppercase; }
</style>
"""

# ==========================================
# 4. Landing Page
# ==========================================
def show_landing_page():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
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
        st.markdown('<div style="display:flex;justify-content:flex-end;align-items:center;padding:18px 0;border-bottom:1px solid var(--border);">', unsafe_allow_html=True)
        if st.button("Sign In / Register →", key="nav_signin"):
            st.session_state['current_page'] = 'auth'
            st.rerun()
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
                    <div class="mock-thumb" style="background:linear-gradient(135deg,#e2e8f0,#cbd5e1);"><div class="mock-detect-box" style="top:20%;left:15%;width:55%;height:50%;"></div><div class="mock-thumb-label">person ✓</div></div>
                    <div class="mock-thumb" style="background:linear-gradient(135deg,#dbeafe,#bfdbfe);"><div class="mock-detect-box" style="top:25%;left:20%;width:60%;height:45%;animation-delay:0.5s;"></div><div class="mock-thumb-label">car ✓</div></div>
                    <div class="mock-thumb" style="background:linear-gradient(135deg,#dcfce7,#bbf7d0);"><div class="mock-detect-box" style="top:18%;left:10%;width:70%;height:55%;animation-delay:1s;"></div><div class="mock-thumb-label">person ✓</div></div>
                    <div class="mock-thumb" style="background:linear-gradient(135deg,#fef3c7,#fde68a);"><div class="mock-thumb-label">flip ↔</div></div>
                    <div class="mock-thumb" style="background:linear-gradient(135deg,#ede9fe,#ddd6fe);"><div class="mock-thumb-label">bright ☀</div></div>
                    <div class="mock-thumb" style="background:linear-gradient(135deg,#fce7f3,#fbcfe8);"><div class="mock-thumb-label">noise ~</div></div>
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
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    if st.button("← Back to Home", key="back_home"):
        st.session_state['current_page'] = 'landing'
        st.rerun()

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:32px 0 28px;border-bottom:2px solid var(--border);margin-bottom:28px;">
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
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    
    # 📌 User Workspace Initialization (พื้นที่ทำงานส่วนตัว)
    user_workspace = f"dataset_workspace_{st.session_state.get('username', 'default')}"

    init = st.session_state['username'][0].upper() if st.session_state['username'] else "?"
    col1, col2 = st.columns([1, 1])
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
    st.write("")

    is_admin = (st.session_state['username'].lower() == 'admin')

    selected_menu = option_menu(
        menu_title=None,
        options=["Dashboard", "AI Engine", "Logout"],
        icons=["grid-1x2", "cpu", "box-arrow-right"],
        default_index=1,
        orientation="horizontal",
        styles={
            "container": { "background-color": "var(--bg-surface)", "border": "1px solid var(--border)", "border-radius": "12px", "padding": "5px", "box-shadow": "0 4px 6px -1px rgba(0,0,0,0.02)", "margin-bottom": "30px" },
            "icon": {"color": "var(--text-3)", "font-size": "16px"},
            "nav-link": { "font-size": "14px", "font-weight": "700", "color": "var(--text-2)", "font-family": "var(--font-display)", "border-radius": "8px", "padding": "10px", "margin": "0 4px" },
            "nav-link-selected": { "background-color": "var(--accent-dim)", "color": "var(--accent)", "border": "1px solid rgba(255,107,0,0.2)" },
        }
    )

    if selected_menu == "Logout":
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
        
        uploaded_file = None
        uploaded_images = []
        
        if input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)":
            uploaded_file = st.file_uploader("Drop video file here", type=['mp4', 'avi', 'mov'], label_visibility="collapsed")
        else:
            uploaded_images = st.file_uploader("Drop image files or a folder here (ลากโฟลเดอร์มาวางได้เลย)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, label_visibility="collapsed")
            st.info("💡 **เคล็ดลับ:** คุณสามารถ **คลุมดำรูปภาพหลายๆ ไฟล์** หรือคลิกที่ **โฟลเดอร์รูปภาพ** แล้วลากมาวาง (Drag & Drop) ในกล่องด้านบนได้เลยครับ!")

        has_media = (input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)" and uploaded_file is not None) or \
                    (input_mode == "🖼️ อัปโหลดรูปภาพ (Image Batch Processing)" and len(uploaded_images) > 0)

        if has_media:
            current_upload_name = uploaded_file.name if input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)" else f"batch_{len(uploaded_images)}_images"
            if st.session_state.get('last_uploaded_file') != current_upload_name:
                st.session_state['process_done'] = False
                st.session_state['last_uploaded_file'] = current_upload_name
                if os.path.exists(user_workspace):
                    shutil.rmtree(user_workspace)

            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.markdown('<div class="col-header"><span class="dot-status dot-blue"></span>SOURCE</div>', unsafe_allow_html=True)
                if input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)":
                    st.video(uploaded_file)
                    video_bytes = uploaded_file.getvalue()
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tfile:
                        tfile.write(video_bytes)
                        video_path = tfile.name
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

                def save_data(img, boxes, modifier, is_flipped=False):
                    subset = "train" if random.random() < (split_ratio / 100.0) else "val"
                    
                    # 📌 1. ดึงชื่อ Class ทั้งหมดที่ตรวจเจอในรูปนี้ (แบบไม่ซ้ำกัน)
                    detected_classes = set()
                    for box in boxes:
                        cid = int(box.cls)
                        detected_classes.add(available_classes[cid])
                    
                    # 📌 2. นำชื่อคลาสมาเชื่อมต่อกัน (ถ้ามีหลายคลาส จะคั่นด้วย _)
                    class_str = "_".join(sorted(list(detected_classes)))
                    if not class_str: class_str = "unlabeled"
                    
                    # 📌 3. นำชื่อคลาส แทรกเข้าไปในชื่อไฟล์
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
                    dataset_records.append({"subset": subset, "file": base_name})

                if input_mode == "🎥 อัปโหลดวิดีโอ (Video Processing)":
                    cap          = cv2.VideoCapture(video_path)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    last_pos = {} 
                    
                    while cap.isOpened():
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
                                image_preview.image(cv2.cvtColor(plot_annotated, cv2.COLOR_BGR2RGB), use_container_width=True)

                        frame_count += 1
                        progress_bar.progress(min(frame_count / total_frames, 1.0))
                        status_text.markdown(f'<div class="status-text">PROCESSING  {frame_count} / {total_frames}  FRAMES | EXTRACTED: {len(dataset_records)}</div>', unsafe_allow_html=True)
                    
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
                    
                    # 📌 3. เพิ่ม Spinner บอกให้ผู้ใช้รู้ตัวระหว่างเรนเดอร์รูปภาพทั้งหมด
                    with st.spinner(f"⏳ กำลังโหลดและจัดเรียงรูปภาพทั้งหมด {len(dataset_records)} รูป... อาจใช้เวลาสักครู่หากข้อมูลมีขนาดใหญ่"):
                        with st.form("gallery_form"):
                            with st.container(height=450):
                                cols = st.columns(4)
                                delete_flags = {}
                                
                                # ปลดการจำกัด แสดงรูปภาพทั้งหมด
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
                    st.success("🎉 Dataset พร้อมนำไปเทรนแล้ว!")

                    zip_filename = f"ai_dataset_{st.session_state['username']}.zip"
                    if os.path.exists(zip_filename):
                        with open(zip_filename, "rb") as fp:
                            st.download_button("⬇  DOWNLOAD DATASET (ZIP)", fp, zip_filename, "application/zip", use_container_width=True)

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
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.markdown('<div style="font-family:var(--font-ui);font-size:13px;color:var(--text-3);font-weight:500;">No recent activity</div>', unsafe_allow_html=True)

# ── ROUTER ──
if st.session_state['current_page'] == 'landing': show_landing_page()
elif st.session_state['current_page'] == 'auth':  show_auth_page()
elif st.session_state['current_page'] == 'main':  show_main_app()