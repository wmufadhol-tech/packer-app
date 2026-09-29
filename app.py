import streamlit as st
import pytesseract
from PIL import Image
import re
import pandas as pd

st.set_page_config(page_title="Auto-Planner Packer", layout="wide")
st.title("🏭 Auto-Planner Packer L1 & L2")

# --- FUNGSI EKSTRAKSI TEKS (STOK) DIPERBAIKI ---
def parse_stock(text):
    stock = {'40K': 0, '40P': 0, '50K': 0}
    if not text: return stock
    
    lines = text.lower().split('\n')
    for line in lines:
        # Mengabaikan baris CPM agar tidak dobel, sesuai logika utama
        if 'cpm' in line: continue 
        
        if '40 kertas' in line or '40 k ' in line:
            match = re.search(r':\s*(\d+)', line)
            if match: stock['40K'] += int(match.group(1))
        elif '40 plastik' in line or '40 p ' in line or '40 p' in line:
            match = re.search(r':\s*(\d+)', line)
            if match: stock['40P'] += int(match.group(1))
        elif '50 kertas' in line or '50 k ' in line:
            match = re.search(r':\s*(\d+)', line)
            if match: stock['50K'] += int(match.group(1))
    return stock

# --- FUNGSI EKSTRAKSI GAMBAR (SO) ---
def parse_so_image(image):
    text = pytesseract.image_to_string(image)
    so_data = {'40K': 0, '50K': 0} # 40P dihapus dari OCR karena akan diinput manual
    
    lines = text.upper().split('\n')
    for line in lines:
        if '40KG' in line and 'PLASTIC' not in line:
            numbers = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b', line)
            if numbers:
                val = float(numbers[-1].replace(',', ''))
                so_data['40K'] += val
        elif '50KG' in line:
            numbers = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b', line)
            if numbers:
                val = float(numbers[-1].replace(',', ''))
                so_data['50K'] += val
    return so_data, text

# --- UI APLIKASI ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Input Data & Scan")
    stok_text = st.text_area("Paste Teks Stok Gudang:", height=130, 
                             placeholder="Contoh:\n40 kertas Dynamix : 64 Pallet")
    so_image = st.file_uploader("Upload Gambar Tabel SO (JPG/PNG)", type=['png', 'jpg', 'jpeg'])
    
    st.markdown("---")
    st.subheader("2. Input Manual (Bila Tidak Ada di Tabel)")
    so_40p_manual = st.number_input("Ketikan SO 40 Plastik (Ton):", min_value=0.0, value=0.0, step=10.0)
    
    st.markdown("---")
    mode = st.selectbox("Mode Operasional", ["Normal", "Polysling", "PM Line 1", "PM Line 2"])

with col2:
    st.subheader("3. Hasil Kalkulasi & Jadwal")
    if st.button("Generate Planning", type="primary"):
        if stok_text and so_image:
            with st.spinner("Memindai gambar dan menghitung logika..."):
                # Ekstrak Stok
                stok = parse_stock(stok_text)
                
                # Ekstrak SO dari Gambar
                img = Image.open(so_image)
                so, raw_text = parse_so_image(img)
                
                # Masukkan nilai input manual ke dalam data SO
                so['40P'] = so_40p_manual
                
                # Kalkulasi Net (Stok Ton - SO Ton) -> 1 Palet = 2 Ton
                net_40k = (stok['40K'] * 2) - so['40K']
                net_40p = (stok['40P'] * 2) - so['40P']
                net_50k = (stok['50K'] * 2) - so['50K']
                
                # Tampilkan Data Ekstraksi
                st.write("**Data yang Terbaca & Diinput:**")
                df_baca = pd.DataFrame({
                    'Kategori': ['40 Kertas', '40 Plastik (Manual)', '50 Kertas'],
                    'Stok (Palet)': [stok['40K'], stok['40P'], stok['50K']],
                    'SO (Ton)': [so['40K'], so['40P'], so['50K']],
                    'Net (Ton)': [net_40k, net_40p, net_50k]
                })
                st.dataframe(df_baca, hide_index=True)
                
                # Logika Sederhana Threshold
                st.write("**Rekomendasi Running Mesin:**")
                l1_tasks = []
                l2_tasks = []
                
                # Aturan Threshold Mode Normal
                if net_40k < 3200: 
                    l2_tasks.append(f"40 Kertas (Defisit: {abs(net_40k)} Ton)")
                
                if net_40p < 3200:
                    l1_tasks.append(f"40 Plastik (Defisit: {abs(net_40p)} Ton)")
                
                if net_50k < (so['50K'] * 2):
                    l1_tasks.append(f"50 Kertas (Defisit: {abs(net_50k)} Ton)")
                
                st.success(f"**L1 RUNNING:** {', '.join(l1_tasks) if l1_tasks else 'Stop / Standby'}")
                st.info(f"**L2 RUNNING:** {', '.join(l2_tasks) if l2_tasks else 'Stop / Standby'}")
                
        else:
            st.warning("Mohon isi teks stok dan upload gambar SO terlebih dahulu.")
