import streamlit as st
import pytesseract
from PIL import Image
import re
import pandas as pd
import math

st.set_page_config(page_title="Auto-Planner Packer", layout="wide")
st.title("🏭 Auto-Planner Packer L1 & L2")

# --- FUNGSI EKSTRAKSI TEKS (STOK) ---
def parse_stock(text):
    stock = {'40K': 0, '40K_CPM': 0, '40P': 0, '40P_CPM': 0, '50K': 0, '50K_CPM': 0}
    if not text: return stock
    
    lines = text.lower().split('\n')
    for line in lines:
        match = re.search(r':\s*(\d+)', line)
        if not match: continue
        val = int(match.group(1))
        
        if '40' in line:
            if re.search(r'\b(plastik|p)\b', line):
                if 'cpm' in line: stock['40P_CPM'] += val
                else: stock['40P'] += val
            elif re.search(r'\b(kertas|k)\b', line):
                if 'cpm' in line: stock['40K_CPM'] += val
                else: stock['40K'] += val
        elif '50' in line:
            if re.search(r'\b(kertas|k)\b', line):
                if 'cpm' in line: stock['50K_CPM'] += val
                else: stock['50K'] += val
                
    return stock

# --- FUNGSI EKSTRAKSI GAMBAR ---
def parse_so_image(image):
    text = pytesseract.image_to_string(image)
    so_data = {'40K': 0, '40K_CPM': 0, '50K': 0, '50K_CPM': 0}
    
    lines = text.upper().split('\n')
    for line in lines:
        if ('40KG' in line or '50KG' in line) and 'PLASTIC' not in line:
            cleaned = re.sub(r'\b[45]0\s*KG\b', '', line, flags=re.IGNORECASE)
            cleaned = re.sub(r'(?<!\S)-(?!\S)', '0', cleaned)
            numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', cleaned)
            
            if len(numbers) >= 3:
                val = float(numbers[2].replace(',', ''))
                if '40' in line:
                    if 'CPM' in line: so_data['40K_CPM'] += val
                    else: so_data['40K'] += val
                elif '50' in line:
                    if 'CPM' in line: so_data['50K_CPM'] += val
                    else: so_data['50K'] += val
                    
    return so_data, text

# --- UI APLIKASI ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Input Data & Scan")
    stok_text = st.text_area("Paste Teks Stok Gudang:", height=170)
    so_image = st.file_uploader("Upload Gambar Tabel SO (JPG/PNG)", type=['png', 'jpg', 'jpeg'])
    
    st.markdown("---")
    st.subheader("2. Input Manual SO READY 40 Plastik")
    col1a, col1b = st.columns(2)
    with col1a:
        so_40p_manual = st.number_input("Dynamix (Reguler) Ton:", min_value=0.0, value=0.0, step=10.0)
    with col1b:
        so_40p_cpm_manual = st.number_input("Dynamix CPM Ton:", min_value=0.0, value=0.0, step=10.0)
    
    st.markdown("---")
    mode = st.selectbox("3. Mode Operasional", ["Normal", "Polysling", "PM Line 1", "PM Line 2"])

with col2:
    st.subheader("4. Hasil Kalkulasi & Jadwal")
    if st.button("Generate Planning", type="primary"):
        if stok_text and so_image:
            with st.spinner("Menghitung Logika Rule Engine Excel..."):
                stok = parse_stock(stok_text)
                img = Image.open(so_image)
                so, raw_text = parse_so_image(img)
                
                so['40P'] = so_40p_manual
                so['40P_CPM'] = so_40p_cpm_manual
                
                nets = {}
                for key in stok.keys():
                    nets[key] = (stok[key] * 2) - so.get(key, 0)
                
                net_40k_total = nets['40K'] + nets['40K_CPM']
                net_40p_total = nets['40P'] + nets['40P_CPM']
                net_50k_total = nets['50K'] + nets['50K_CPM']
                
                # --- LOGIKA THRESHOLD BERDASARKAN MODE ---
                if mode == "Normal":
                    stopMin_40k = 3200
                    stopMin_40p = 3200
                elif mode == "Polysling":
                    stopMin_40k = 2400
                    stopMin_40p = 7200
                elif mode == "PM Line 1":
                    stopMin_40k = 2400
                    stopMin_40p = 2400
                elif mode == "PM Line 2":
                    stopMin_40k = 2400
                    stopMin_40p = 3200
                
                st.write(f"*Sistem membaca target (stopMin) berdasarkan Mode **{mode}**: 40K = {stopMin_40k}T | 40P = {stopMin_40p}T*")

                def hitung_palet(net, stopMin, ton_per_palet):
                    if net >= stopMin: return 0
                    return math.ceil((stopMin - net) / ton_per_palet)

                butuh_40k = hitung_palet(net_40k_total, stopMin_40k, 160)
                butuh_40p = hitung_palet(net_40p_total, stopMin_40p, 280)
                butuh_50k = hitung_palet(net_50k_total, ((so['50K'] + so['50K_CPM']) * 2), 200)

                l1_tasks = []
                l2_tasks = []
                l1_kapasitas = 360 
                l2_kapasitas = 360

                # ALOKASI L2
                l2_terpakai = 0
                if butuh_40k > 0:
                    buka_40k_l2 = min(butuh_40k, 4) 
                    l2_tasks.append(f"🔴 BUKA {buka_40k_l2} PALET KANTONG - 40 Kertas")
                    l2_terpakai += buka_40k_l2 * 80
                    butuh_40k -= buka_40k_l2 
                
                if l2_terpakai == 0:
                    l2_tasks.append("⚪ STOP / Kebutuhan L2 (40K) Terpenuhi")

                # ALOKASI L1
                l1_terpakai = 0
                if butuh_40p > 0:
                    buka_40p = min(butuh_40p, 2) 
                    l1_tasks.append(f"🔵 BUKA {buka_40p} PALET KANTONG - 40 Plastik")
                    l1_terpakai += buka_40p * 140
                    butuh_40p -= buka_40p
                
                if butuh_50k > 0 and l1_terpakai < l1_kapasitas:
                    sisa_slot = l1_kapasitas - l1_terpakai
                    max_50k = sisa_slot // 100
                    buka_50k = min(butuh_50k, max_50k)
                    if buka_50k > 0:
                        l1_tasks.append(f"🟢 BUKA {buka_50k} PALET KANTONG - 50 Kertas")
                        l1_terpakai += buka_50k * 100
                        butuh_50k -= buka_50k

                if butuh_40k > 0 and l1_terpakai < l1_kapasitas:
                    sisa_slot = l1_kapasitas - l1_terpakai
                    max_40k = sisa_slot // 80
                    buka_40k_l1 = min(butuh_40k, max_40k)
                    if buka_40k_l1 > 0:
                        l1_tasks.append(f"🟠 (Backup) BUKA {buka_40k_l1} PALET KANTONG - 40 Kertas")
                        l1_terpakai += buka_40k_l1 * 80

                if l1_terpakai == 0:
                    l1_tasks.append("⚪ STOP / Kebutuhan L1 Terpenuhi")

                st.success("**JADWAL L1 SHIFT INI (URUTAN):**\n\n" + "\n\n".join(f"- {task}" for task in l1_tasks))
                st.info("**JADWAL L2 SHIFT INI (URUTAN):**\n\n" + "\n\n".join(f"- {task}" for task in l2_tasks))
                
                with st.expander("Klik untuk lihat detail stok & net tonase"):
                    df_baca = pd.DataFrame({
                        'Varian Produk': ['40 Kertas', '40K CPM', '40 Plastik', '40P CPM', '50 Kertas', '50K CPM'],
                        'Stok (Plt)': [stok['40K'], stok['40K_CPM'], stok['40P'], stok['40P_CPM'], stok['50K'], stok['50K_CPM']],
                        'SO Ready': [so['40K'], so['40K_CPM'], so['40P'], so['40P_CPM'], so['50K'], so['50K_CPM']],
                        'Net (Ton)': [nets['40K'], nets['40K_CPM'], nets['40P'], nets['40P_CPM'], nets['50K'], nets['50K_CPM']]
                    })
                    st.dataframe(df_baca, hide_index=True)

        else:
            st.warning("Mohon isi teks stok dan upload gambar SO terlebih dahulu.")
