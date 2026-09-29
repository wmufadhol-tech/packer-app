import streamlit as st
import pytesseract
from PIL import Image
import re
import pandas as pd
import math

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

# --- FUNGSI EKSTRAKSI GAMBAR (KUNCI TITIK DESIMAL + STRIP) ---
def parse_so_image(image):
    text = pytesseract.image_to_string(image)
    so_data = {'40K': 0, '40K_CPM': 0, '50K': 0, '50K_CPM': 0}
    
    lines = text.upper().split('\n')
    for line in lines:
        if ('40KG' in line or '50KG' in line) and 'PLASTIC' not in line:
            # Hapus teks '40KG' atau '50KG' agar tidak mengganggu
            cleaned = re.sub(r'\b[45]0\s*KG\b', '', line, flags=re.IGNORECASE)
            
            # UBAH STRIP (-) MENJADI 0.00 AGAR DIKENALI SEBAGAI DESIMAL
            cleaned = re.sub(r'(?<!\S)-(?!\S)', '0.00', cleaned)
            
            # Khusus mencari angka yang ADA TITIK DESIMALNYA (Ciri khas SO READY)
            decimal_numbers = re.findall(r'\b\d+(?:,\d{3})*\.\d+\b', cleaned)
            
            if decimal_numbers:
                val = float(decimal_numbers[0].replace(',', ''))
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
    stok_text = st.text_area("Paste Teks Stok Gudang:", height=130)
    so_image = st.file_uploader("Upload Gambar Tabel SO (JPG/PNG)", type=['png', 'jpg', 'jpeg'])
    
    st.markdown("---")
    st.subheader("2. Backup Manual SO READY (Opsional)")
    st.caption("Jika hasil scan foto meleset/0, cukup ketik manual di sini:")
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        m_40k = st.number_input("40 Kertas:", min_value=0.0, value=0.0)
        m_40k_cpm = st.number_input("40K CPM:", min_value=0.0, value=0.0)
    with col_b:
        m_40p = st.number_input("40 Plastik:", min_value=0.0, value=0.0)
        m_40p_cpm = st.number_input("40P CPM:", min_value=0.0, value=0.0)
    with col_c:
        m_50k = st.number_input("50 Kertas:", min_value=0.0, value=0.0)
        m_50k_cpm = st.number_input("50K CPM:", min_value=0.0, value=0.0)
    
    st.markdown("---")
    mode = st.selectbox("3. Mode Operasional", ["Normal", "Polysling", "PM Line 1", "PM Line 2"])

with col2:
    st.subheader("4. Hasil Kalkulasi & Jadwal")
    if st.button("Generate Planning", type="primary"):
        # Bisa diproses asal ada teks stok dan (ada foto ATAU ada input manual)
        if stok_text and (so_image or m_40p > 0 or m_40k > 0 or m_50k > 0): 
            with st.spinner("Memproses data..."):
                stok = parse_stock(stok_text)
                
                if so_image:
                    img = Image.open(so_image)
                    so, raw_text = parse_so_image(img)
                else:
                    so = {'40K': 0, '40K_CPM': 0, '50K': 0, '50K_CPM': 0}
                    raw_text = "Tidak ada gambar yang di-upload."
                
                # Timpa (override) hasil scan dengan input manual jika nilainya lebih dari 0
                if m_40k > 0: so['40K'] = m_40k
                if m_40k_cpm > 0: so['40K_CPM'] = m_40k_cpm
                if m_40p > 0: so['40P'] = m_40p 
                else: so['40P'] = 0 # Plastik selalu manual, jadi fallback ke 0
                if m_40p_cpm > 0: so['40P_CPM'] = m_40p_cpm
                else: so['40P_CPM'] = 0
                if m_50k > 0: so['50K'] = m_50k
                if m_50k_cpm > 0: so['50K_CPM'] = m_50k_cpm
                
                nets = {}
                for key in stok.keys():
                    nets[key] = (stok[key] * 2) - so.get(key, 0)
                
                net_40k_total = nets['40K'] + nets['40K_CPM']
                net_40p_total = nets['40P'] + nets['40P_CPM']
                net_50k_total = nets['50K'] + nets['50K_CPM']
                
                # Target runMax berdasarkan Mode Operasional
                if mode == "Normal":
                    target_40k = 1200; target_40p = 1200
                elif mode == "Polysling":
                    target_40k = 1000; target_40p = 3600
                elif mode == "PM Line 1":
                    target_40k = 1600; target_40p = 1000
                elif mode == "PM Line 2":
                    target_40k = 1000; target_40p = 1600
                
                def hitung_palet(net, target, ton_per_palet):
                    if net >= target: return 0
                    return round((target - net) / ton_per_palet)

                butuh_40k = hitung_palet(net_40k_total, target_40k, 160)
                butuh_40p = hitung_palet(net_40p_total, target_40p, 280)
                
                if net_50k_total >= 0: butuh_50k = 0
                else: butuh_50k = math.ceil(abs(net_50k_total) / 200)

                l1_tasks = []; l2_tasks = []
                l1_kapasitas = 360; l2_kapasitas = 360

                # L2 - KHUSUS 40 Kertas
                l2_terpakai = 0
                if butuh_40k > 0:
                    buka_40k_l2 = min(butuh_40k, 4) 
                    l2_tasks.append(f"🔴 BUKA {buka_40k_l2} PALET KANTONG - 40 Kertas")
                    l2_terpakai += buka_40k_l2 * 80
                    butuh_40k -= buka_40k_l2 
                if l2_terpakai == 0: l2_tasks.append("⚪ STOP / Kebutuhan L2 (40K) Terpenuhi")

                # L1 - PRIORITAS: Plastik -> 50 Kertas -> Backup 40 Kertas
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
                if l1_terpakai == 0: l1_tasks.append("⚪ STOP / Kebutuhan L1 Terpenuhi")

                # OUTPUT
                st.write(f"*Target produksi (runMax) Mode **{mode}**: 40K = {target_40k}T | 40P = {target_40p}T*")
                st.success("**JADWAL L1 SHIFT INI (URUTAN):**\n\n" + "\n\n".join(f"- {task}" for task in l1_tasks))
                st.info("**JADWAL L2 SHIFT INI (URUTAN):**\n\n" + "\n\n".join(f"- {task}" for task in l2_tasks))
                
                with st.expander("Klik untuk lihat detail stok & net tonase"):
                    df_baca = pd.DataFrame({
                        'Varian Produk': ['40 Kertas', '40K CPM', '40 Plastik', '40P CPM', '50 Kertas', '50K CPM'],
                        'Stok (Plt)': [stok['40K'], stok['40K_CPM'], stok['40P'], stok['40P_CPM'], stok['50K'], stok['50K_CPM']],
                        'SO Ready (Ton)': [so['40K'], so['40K_CPM'], so['40P'], so['40P_CPM'], so['50K'], so['50K_CPM']],
                        'Net (Ton)': [nets['40K'], nets['40K_CPM'], nets['40P'], nets['40P_CPM'], nets['50K'], nets['50K_CPM']]
                    })
                    st.dataframe(df_baca, hide_index=True)
                    st.text("Teks Mentah dari Gambar:")
                    st.text(raw_text)
        else:
            st.warning("Mohon isi teks stok dan upload gambar SO (atau isi manual) terlebih dahulu.")
