import streamlit as st
import pytesseract
from PIL import Image
import re
import pandas as pd

st.set_page_config(page_title="Auto-Planner Packer", layout="wide")
st.title("🏭 Auto-Planner Packer L1 & L2")

# --- FUNGSI EKSTRAKSI TEKS (STOK 6 VARIAN) ---
def parse_stock(text):
    stock = {'40K': 0, '40K_CPM': 0, '40P': 0, '40P_CPM': 0, '50K': 0, '50K_CPM': 0}
    if not text: return stock
    
    lines = text.lower().split('\n')
    for line in lines:
        match = re.search(r':\s*(\d+)', line)
        if not match: continue
        val = int(match.group(1))
        
        if '40' in line and ('kertas' in line or 'k ' in line or 'k' in line):
            if 'cpm' in line: stock['40K_CPM'] += val
            else: stock['40K'] += val
        elif '40' in line and ('plastik' in line or 'p ' in line or 'p' in line):
            if 'cpm' in line: stock['40P_CPM'] += val
            else: stock['40P'] += val
        elif '50' in line and ('kertas' in line or 'k ' in line or 'k' in line):
            if 'cpm' in line: stock['50K_CPM'] += val
            else: stock['50K'] += val
            
    return stock

# --- FUNGSI EKSTRAKSI GAMBAR (SO KUNCI KOLOM READY) ---
def parse_so_image(image):
    text = pytesseract.image_to_string(image)
    so_data = {'40K': 0, '40K_CPM': 0, '50K': 0, '50K_CPM': 0}
    
    lines = text.upper().split('\n')
    for line in lines:
        if ('40KG' in line or '50KG' in line) and 'PLASTIC' not in line:
            # 1. Hapus "40KG"/"50KG" agar tidak terhitung sebagai kolom angka
            cleaned = re.sub(r'\b[45]0\s*KG\b', '', line, flags=re.IGNORECASE)
            
            # 2. Ubah tanda strip/kosong (-) yang berdiri sendiri menjadi angka 0
            cleaned = re.sub(r'(?<!\S)-(?!\S)', '0', cleaned)
            
            # 3. Cari deretan angka di baris tersebut
            numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', cleaned)
            
            # 4. Kunci absolut ke kolom "SO Ready Hari Ini" (Index ke-2 setelah Late & Hari Ini)
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
    stok_text = st.text_area("Paste Teks Stok Gudang:", height=170, 
                             placeholder="Contoh:\n40 kertas Dynamix : 64 Pallet\n40 k Dynamix CPM : 43 Pallet")
    so_image = st.file_uploader("Upload Gambar Tabel SO (JPG/PNG)", type=['png', 'jpg', 'jpeg'])
    
    st.markdown("---")
    st.subheader("2. Input Manual SO READY 40 Plastik")
    col1a, col1b = st.columns(2)
    with col1a:
        so_40p_manual = st.number_input("Dynamix (Reguler) Ton:", min_value=0.0, value=0.0, step=10.0)
    with col1b:
        so_40p_cpm_manual = st.number_input("Dynamix CPM Ton:", min_value=0.0, value=0.0, step=10.0)
    
    st.markdown("---")
    mode = st.selectbox("Mode Operasional", ["Normal", "Polysling", "PM Line 1", "PM Line 2"])

with col2:
    st.subheader("3. Hasil Kalkulasi & Jadwal")
    if st.button("Generate Planning", type="primary"):
        if stok_text and so_image:
            with st.spinner("Memindai gambar dan memproses logika...") :
                stok = parse_stock(stok_text)
                img = Image.open(so_image)
                so, raw_text = parse_so_image(img)
                
                # Masukkan nilai input manual
                so['40P'] = so_40p_manual
                so['40P_CPM'] = so_40p_cpm_manual
                
                # Kalkulasi Net: (Palet x 2) - Tonase SO
                nets = {}
                for key in stok.keys():
                    nets[key] = (stok[key] * 2) - so.get(key, 0)
                
                st.write("**Data 6 Varian (Fokus Kolom SO Ready Hari Ini):**")
                df_baca = pd.DataFrame({
                    'Varian Produk': [
                        '40 Kertas Dynamix', '40 Kertas CPM', 
                        '40 Plastik Dynamix', '40 Plastik CPM', 
                        '50 Kertas Dynamix', '50 Kertas CPM'
                    ],
                    'Stok (Plt)': [stok['40K'], stok['40K_CPM'], stok['40P'], stok['40P_CPM'], stok['50K'], stok['50K_CPM']],
                    'SO Ready (Ton)': [so['40K'], so['40K_CPM'], so['40P'], so['40P_CPM'], so['50K'], so['50K_CPM']],
                    'Net (Ton)': [nets['40K'], nets['40K_CPM'], nets['40P'], nets['40P_CPM'], nets['50K'], nets['50K_CPM']]
                })
                st.dataframe(df_baca, hide_index=True)
                
                # LOGIKA REKOMENDASI MESIN
                st.write("**Rekomendasi Running Mesin:**")
                l1_tasks = []
                l2_tasks = []
                
                net_40k_total = nets['40K'] + nets['40K_CPM']
                net_40p_total = nets['40P'] + nets['40P_CPM']
                net_50k_total = nets['50K'] + nets['50K_CPM']
                so_50k_total = so['50K'] + so['50K_CPM']
                
                # Evaluasi Mesin L2 (Target 40 Kertas)
                if net_40k_total < 3200: 
                    l2_tasks.append(f"40 Kertas [Reguler Net: {nets['40K']}T | CPM Net: {nets['40K_CPM']}T]")
                
                # Evaluasi Mesin L1 (Target 40 Plastik & 50 Kertas)
                if net_40p_total < 3200:
                    l1_tasks.append(f"40 Plastik [Reguler Net: {nets['40P']}T | CPM Net: {nets['40P_CPM']}T]")
                
                if net_50k_total < (so_50k_total * 2):
                    l1_tasks.append(f"50 Kertas [Reguler Net: {nets['50K']}T | CPM Net: {nets['50K_CPM']}T]")
                
                st.success(f"**L1 RUNNING:**\n{', '.join(l1_tasks) if l1_tasks else 'Stop / Standby'}")
                st.info(f"**L2 RUNNING:**\n{', '.join(l2_tasks) if l2_tasks else 'Stop / Standby'}")
                
        else:
            st.warning("Mohon isi teks stok dan upload gambar SO terlebih dahulu.")
