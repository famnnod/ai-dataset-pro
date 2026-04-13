import streamlit as st
import tempfile
import os
import cv2
import zipfile
import shutil
import pandas as pd
import random
import sqlite3 # 1. นำเข้าไลบรารีฐานข้อมูล (มีใน Python อยู่แล้ว)
import hashlib # 2. นำเข้าตัวเข้ารหัสผ่านเพื่อความปลอดภัย
from ultralytics import YOLO
from streamlit_option_menu import option_menu # 3. นำเข้าตัวทำเมนูสวยๆ

st.set_page_config(page_title="AI-Dataset Pro", page_icon="🔥", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# ส่วนของการจัดการฐานข้อมูล (Database Management)
# ==========================================
# เชื่อมต่อกับไฟล์ฐานข้อมูล (ถ้าไม่มีไฟล์นี้ ระบบจะสร้างให้ใหม่ชื่อ users.db)
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()

# ฟังก์ชันสร้างตารางเก็บข้อมูลผู้ใช้
def create_usertable():
    c.execute('CREATE TABLE IF NOT EXISTS userstable(username TEXT, password TEXT)')

# ฟังก์ชันเพิ่มผู้ใช้ใหม่ (พร้อมเข้ารหัส Password ป้องกันโดนแฮก)
def add_userdata(username, password):
    hashed_password = hashlib.sha256(str.encode(password)).hexdigest()
    c.execute('INSERT INTO userstable(username, password) VALUES (?,?)', (username, hashed_password))
    conn.commit()

# ฟังก์ชันตรวจสอบตอนล็อกอิน
def login_user(username, password):
    hashed_password = hashlib.sha256(str.encode(password)).hexdigest()
    c.execute('SELECT * FROM userstable WHERE username =? AND password = ?', (username, hashed_password))
    data = c.fetchall()
    return data

# สร้างตารางฐานข้อมูลรอไว้เลยตั้งแต่เปิดเว็บ
create_usertable()

# ==========================================
# ระบบจัดการ Session
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""

# ==========================================
# หน้าเข้าสู่ระบบ & สมัครสมาชิก (Auth Page)
# ==========================================
def show_auth_page():
    st.markdown("""
        <style>
        .auth-box { max-width: 450px; margin: 80px auto; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #f0f2f6; text-align: center; }
        .main-title { background: -webkit-linear-gradient(#FF4B4B, #FF904F); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.5rem; font-weight: 800; margin-bottom: 10px;}
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="auth-box">', unsafe_allow_html=True)
    st.markdown('<div class="main-title">🔥 AI-Dataset Pro</div>', unsafe_allow_html=True)
    st.markdown("<p style='color: gray; margin-bottom: 30px;'>แพลตฟอร์มจัดการข้อมูลสำหรับนักพัฒนา AI</p>", unsafe_allow_html=True)
    
    # ทำหน้าจอเป็น Tab ให้กดสลับระหว่าง ล็อกอิน / สมัครสมาชิก
    tab1, tab2 = st.tabs(["🔐 เข้าสู่ระบบ", "📝 สมัครสมาชิกใหม่"])
    
    with tab1:
        st.subheader("ยินดีต้อนรับกลับมา")
        login_user_input = st.text_input("ชื่อผู้ใช้งาน", key="login_user")
        login_pass_input = st.text_input("รหัสผ่าน", type="password", key="login_pass")
        
        if st.button("🚀 เข้าสู่ระบบ", type="primary", use_container_width=True):
            if login_user_input and login_pass_input:
                result = login_user(login_user_input, login_pass_input)
                if result:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = login_user_input
                    st.success(f"เข้าสู่ระบบสำเร็จ! ยินดีต้อนรับ {login_user_input}")
                    st.rerun()
                else:
                    st.error("❌ ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")
            else:
                st.warning("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน")

    with tab2:
        st.subheader("สร้างบัญชีใหม่")
        new_user = st.text_input("ตั้งชื่อผู้ใช้งาน", key="reg_user")
        new_pass = st.text_input("ตั้งรหัสผ่าน", type="password", key="reg_pass")
        
        if st.button("✨ สมัครสมาชิก", type="primary", use_container_width=True):
            if new_user and new_pass:
                # เช็คก่อนว่าชื่อนี้มีคนใช้หรือยัง
                c.execute('SELECT * FROM userstable WHERE username =?', (new_user,))
                if c.fetchone():
                    st.error("❌ ชื่อผู้ใช้งานนี้มีคนใช้แล้ว กรุณาตั้งชื่อใหม่")
                else:
                    add_userdata(new_user, new_pass)
                    st.success("✅ สมัครสมาชิกสำเร็จ! คุณสามารถเข้าสู่ระบบได้เลย")
            else:
                st.warning("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน")
                
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# หน้าแอปพลิเคชันหลัก (Main Application)
# ==========================================
def show_main_app():
    # CSS ตกแต่ง
    st.markdown("""
        <style>
        .stButton>button { border-radius: 10px; font-weight: bold; }
        .upload-box { border: 2px dashed #FF4B4B; border-radius: 15px; padding: 20px; background-color: rgba(255, 75, 75, 0.05); text-align: center;}
        </style>
    """, unsafe_allow_html=True)

    # --- เมนู Sidebar สไตล์แอป ---
    with st.sidebar:
        # ใช้ streamlit-option-menu สร้างเมนูสวยๆ
        selected_menu = option_menu(
            menu_title="Main Menu", 
            options=["Dashboard", "สร้าง Dataset", "ออกจากระบบ"], 
            icons=["house", "cloud-upload", "box-arrow-left"], 
            menu_icon="cast", 
            default_index=1,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "nav-link-selected": {"background-color": "#FF4B4B"},
            }
        )
        
        st.markdown(f"<div style='margin-top: 20px; padding: 10px; background-color: #f0f2f6; border-radius: 10px; text-align: center;'>👤 <b>ผู้ใช้งาน:</b> {st.session_state['username']}</div>", unsafe_allow_html=True)
        
        # จัดการเมนู ออกจากระบบ
        if selected_menu == "ออกจากระบบ":
            st.session_state['logged_in'] = False
            st.session_state['username'] = ""
            st.rerun()
            
    # --- หน้า "สร้าง Dataset" ---
    if selected_menu == "สร้าง Dataset":
        st.title("🔥 AI-Dataset Factory Pro")
        st.markdown("ระบบสร้าง Dataset อัตโนมัติด้วย AI")
        
        # โหลดโมเดล
        @st.cache_resource
        def load_model(): return YOLO('yolov8n.pt') 
        model = load_model()
        available_classes = model.names
        
        # ตั้งค่าย้ายมาอยู่ด้านบนในรูปแบบ Expander เพื่อให้จอดูคลีน
        with st.expander("⚙️ ตั้งค่าโมเดลและ Dataset (คลิกเพื่อปรับแต่ง)"):
            col_set1, col_set2 = st.columns(2)
            with col_set1:
                selected_class_names = st.multiselect("🎯 เลือกวัตถุที่ต้องการ Label", list(available_classes.values()), default=["person", "car"])
                selected_class_ids = [k for k, v in available_classes.items() if v in selected_class_names]
            with col_set2:
                split_ratio = st.slider("Train Dataset (%)", 50, 95, 80)
                frame_skip = st.slider("ดึงภาพทุกๆ X เฟรม", 1, 30, 10)

        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("📂 ลากไฟล์วิดีโอมาวางที่นี่", type=['mp4', 'avi', 'mov'])
        st.markdown('</div>', unsafe_allow_html=True)

        if uploaded_file is not None:
            tfile = tempfile.NamedTemporaryFile(delete=False) 
            tfile.write(uploaded_file.read())
            tfile.close()
            video_path = tfile.name
            
            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.markdown("### 🎥 ต้นฉบับ")
                st.video(uploaded_file)
            with col2:
                st.markdown("### 🤖 พรีวิว AI")
                image_preview = st.empty()
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("🚀 เริ่มสร้าง Dataset", type="primary", use_container_width=True):
                # ... (การทำงานของ OpenCV และ YOLO เหมือนเดิมทั้งหมด) ...
                output_folder = "dataset_workspace"
                if os.path.exists(output_folder): shutil.rmtree(output_folder)
                folders = ['images/train', 'images/val', 'labels/train', 'labels/val']
                for f in folders: os.makedirs(os.path.join(output_folder, f))

                cap = cv2.VideoCapture(video_path)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                progress_bar = st.progress(0)
                status_text = st.empty()

                frame_count = 0; dataset_records = [] 
                class_counts = {name: 0 for name in selected_class_names} if selected_class_names else {v: 0 for v in available_classes.values()}

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret: break
                    if frame_count % frame_skip == 0:
                        results = model(frame, classes=selected_class_ids if selected_class_ids else None, verbose=False)
                        boxes = results[0].boxes
                        if len(boxes) > 0:
                            subset = "train" if random.random() < (split_ratio / 100.0) else "val"
                            base_name = f"frame_{frame_count:06d}"
                            img_path = f"{output_folder}/images/{subset}/{base_name}.jpg"
                            txt_path = f"{output_folder}/labels/{subset}/{base_name}.txt"
                            cv2.imwrite(img_path, frame)
                            with open(txt_path, 'w') as f:
                                for box in boxes:
                                    c_id = int(box.cls)
                                    c_name = available_classes[c_id]
                                    class_counts[c_name] += 1 
                                    new_id = selected_class_names.index(c_name) if selected_class_names else c_id
                                    x, y, w, h = box.xywhn[0]
                                    f.write(f"{new_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")
                            dataset_records.append({"subset": subset, "file": base_name})
                            annotated_frame = results[0].plot()
                            image_preview.image(cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB), use_container_width=True)
                    frame_count += 1
                    progress_bar.progress(min(frame_count / total_frames, 1.0))
                    status_text.markdown(f"**⏳ ทำงาน:** {frame_count}/{total_frames} เฟรม")
                cap.release()
                
                yaml_path = os.path.join(output_folder, "data.yaml")
                classes_for_yaml = selected_class_names if selected_class_names else list(available_classes.values())
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    f.write("train: images/train\nval: images/val\n\n")
                    f.write(f"nc: {len(classes_for_yaml)}\n")
                    names_str = "[" + ", ".join([f"'{name}'" for name in classes_for_yaml]) + "]"
                    f.write(f"names: {names_str}\n")
                    
                st.divider()
                st.success("🎉 สร้าง Dataset เสร็จสมบูรณ์!")
                
                # ... (ส่วน Dashboard ซ่อนไว้ชั่วคราวเพื่อให้เห็นภาพรวม)...
                
                zip_filename = "pro_dataset.zip"
                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                    for root, dirs, files in os.walk(output_folder):
                        for file in files: zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), output_folder))
                
                with open(zip_filename, "rb") as fp:
                    st.download_button("✅ ดาวน์โหลด Pro Dataset", fp, "pro_dataset.zip", "application/zip", use_container_width=True)
                
                os.remove(video_path); shutil.rmtree(output_folder); os.remove(zip_filename)

    # --- หน้า "Dashboard" ---
    elif selected_menu == "Dashboard":
        st.title("📊 ภาพรวมระบบ")
        st.info("หน้านี้สำหรับโชว์กราฟ หรือประวัติการใช้งานของผู้ใช้แต่ละคนในอนาคตครับ")
        st.image("https://cdn.dribbble.com/users/189524/screenshots/2942485/media/1eb2df4ee5d14cdbbdcfe836a9e14a1e.gif") # ใส่ภาพเคลื่อนไหวให้ดูไม่โล่ง

# ==========================================
# Router (ตัวควบคุมหน้าเว็บ)
# ==========================================
if not st.session_state['logged_in']:
    show_auth_page()
else:
    show_main_app()