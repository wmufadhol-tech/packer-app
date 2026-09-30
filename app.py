import streamlit as st
import pytesseract
from PIL import Image
import re
import pandas as pd
import math
import io

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

# --- FUNGSI MEMBERSIHKAN ANGKA RIBUAN OCR ---
def parse_weird_number(num_str):
    # Mengatasi error baca OCR seperti: 2.136.00 atau 2,136,00
    if len(num_str) > 3 and num_str[-3] in ['.', ',']:
        main_part = num_str[:-3]
        main_part = re.sub(r'[.,]', '', main_part) # Hapus semua pemisah ribuan
        return float(main_part)
    return 0.0

# --- FUNGSI EKSTRAKSI TEKS EXCEL (AKURASI 100%) ---
def parse_so_excel_text(text):
    so_data = {'40K': 0.0, '40K_CPM': 0.0, '50K': 0.0, '50K_CPM': 0.0}
    lines = text.upper().split('\n')
    for line in lines:
        if ('40KG' in line or '50KG' in line) and 'PLASTIC' not in line:
            cols = line.split('\t')
            if len(cols) >= 4:
                val_str = cols[3].strip() # Kolom ke-4 adalah SO READY
                if val_str == '-' or val_str == '':
                    val = 0.0
                else:
                    val = float(val_str.replace(',', ''))
                
                if '40' in line:
                    if 'CPM' in line: so_data['40K_CPM'] += val
                    else: so_data['40K'] += val
                elif '50' in line:
                    if 'CPM' in line: so_data['50K_CPM'] += val
                    else: so_data['50K'] += val
    return so_data

# --- FUNGSI EKSTRAKSI GAMBAR OCR ---
@st.cache_data
def get_ocr_data(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(img)
    so_data = {'40K': 0.0, '40K_CPM': 0.0, '50K': 0.0, '50K_CPM': 0.0}
    
    lines = text.upper().split('\n')
    for line in lines:
        if ('40KG' in line or '50KG' in line) and 'PLASTIC' not in line:
            cleaned = re.sub(r'\b[45]0\s*KG\b', '', line, flags=re.IGNORECASE)
            cleaned = re.sub(r'(?<!\S)[-—_~](?!\S)', '0.00', cleaned)
            
            # Pola baru yang tahan banting (menangkap 2,136.00 atau 2.136.00)
            decimal_numbers = re.findall(r'\b\d+(?:[.,]\d{3})*[.,]\d{2}\b', cleaned)
            
            if decimal_numbers:
                val = parse_weird_number(decimal_numbers[0])
                if '40' in line:
                    if 'CPM' in line: so_data['40K_CPM'] += val
                    else: so_data['40K'] += val
                elif '50' in line:
                    if 'CPM' in line: so_data['50K_CPM'] += val
                    else: so_data['50K'] += val
    return so_data

# --- UI APLIKASI ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Input Data")
    stok_text = st.text_area("📦 Paste Teks Stok Gudang:", height=110)
    
    st.markdown("---")
    st.write("📝 **Data Sales Order (Pilih salah satu metode):**")
    
    # METODE 1: PASTE EXCEL (DISARANKAN)
    so_text_excel = st.text_area("🌟 METODE TERBAIK: Copy-Paste Tabel Excel langsung ke sini:", height=90, placeholder="Blok tabel di Excel Anda, lalu copy dan paste di sini.")
    
    st.write("Atau")
    
    # METODE 2: UPLOAD GAMBAR
    so_image = st.file_uploader("📷 METODE ALTERNATIF: Upload Gambar Tabel", type=['png', 'jpg', 'jpeg'])
    
    st.markdown("---")
    mode = st.selectbox("⚙️ Mode Operasional", ["Normal", "Polysling", "PM Line 1", "PM Line 2"])

with col2:
    st.subheader("2. Verifikasi Data (BISA DIEDIT!)")
    
    # Deteksi input (Prioritaskan Paste Excel jika keduanya diisi)
    has_so_data = bool(so_text_excel or so_image)
    
    if stok_text and has_so_data:
        
        stok = parse_stock(stok_text)
        
        if so_text_excel:
            so_final = parse_so_excel_text(so_text_excel)
            st.success("✅ Membaca dari Teks Excel (Akurasi 100%)")
        else:
            so_final = get_ocr_data(so_image.getvalue())
            st.info("📷 Membaca dari Gambar Kamera")
        
        df_edit = pd.DataFrame({
            'Varian Produk': ['40 Kertas', '40K CPM', '40 Plastik', '40P CPM', '50 Kertas', '50K CPM'],
            'Stok (Plt)': [stok['40K'], stok['40K_CPM'], stok['40P'], stok['40P_CPM'], stok['50K'], stok['50K_CPM']],
            'SO Ready (Ton)': [so_final['40K'], so_final['40K_CPM'], 0.0, 0.0, so_final['50K'], so_final['50K_CPM']]
        })
        
        st.caption("Klik dua kali angka di tabel bawah untuk mengoreksi sebelum klik Generate.")
        edited_df = st.data_editor(df_edit, hide_index=True, use_container_width=True)
        
        st.markdown("---")
        
        if st.button("🚀 Generate Planning", type="primary"):
            with st.spinner("Menghitung Jadwal..."):
                
                s_40k = edited_df.loc[0, 'Stok (Plt)']; o_40k = edited_df.loc[0, 'SO Ready (Ton)']
                s_40kc = edited_df.loc[1, 'Stok (Plt)']; o_40kc = edited_df.loc[1, 'SO Ready (Ton)']
                s_40p = edited_df.loc[2, 'Stok (Plt)']; o_40p = edited_df.loc[2, 'SO Ready (Ton)']
                s_40pc = edited_df.loc[3, 'Stok (Plt)']; o_40pc = edited_df.loc[3, 'SO Ready (Ton)']
                s_50k = edited_df.loc[4, 'Stok (Plt)']; o_50k = edited_df.loc[4, 'SO Ready (Ton)']
                s_50kc = edited_df.loc[5, 'Stok (Plt)']; o_50kc = edited_df.loc[5, 'SO Ready (Ton)']

                net_40k = (s_40k * 2) - o_40k
                net_40kc = (s_40kc * 2) - o_40kc
                net_40p = (s_40p * 2) - o_40p
                net_40pc = (s_40pc * 2) - o_40pc
                net_50k = (s_50k * 2) - o_50k
                net_50kc = (s_50kc * 2) - o_50kc
                
                net_40k_total = net_40k + net_40kc
                net_40p_total = net_40p + net_40pc
                net_50k_total = net_50k + net_50kc
                
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

                # L2
                if mode == "PM Line 2":
                    l2_tasks.append("🔧 PREVENTIVE MAINTENANCE (PM) - Mesin Stop")
                else:
                    l2_terpakai = 0
                    if butuh_40k > 0:
                        buka_40k_l2 = min(butuh_40k, 4) 
                        l2_tasks.append(f"🔴 BUKA {buka_40k_l2} PALET KANTONG - 40 Kertas")
                        l2_terpakai += buka_40k_l2 * 80
                        butuh_40k -= buka_40k_l2 
                    if l2_terpakai == 0: 
                        l2_tasks.append("⚪ STOP / Kebutuhan L2 (40K) Terpenuhi")

                # L1
                if mode == "PM Line 1":
                    l1_tasks.append("🔧 PREVENTIVE MAINTENANCE (PM) - Mesin Stop")
                else:
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

                st.write(f"*Target (runMax) Mode **{mode}**: 40K = {target_40k}T | 40P = {target_40p}T*")
                
                if mode == "PM Line 1":
                    st.warning("**JADWAL L1 SHIFT INI (URUTAN):**\n\n" + "\n\n".join(f"- {task}" for task in l1_tasks))
                else:
                    st.success("**JADWAL L1 SHIFT INI (URUTAN):**\n\n" + "\n\n".join(f"- {task}" for task in l1_tasks))
                
                if mode == "PM Line 2":
                    st.warning("**JADWAL L2 SHIFT INI (URUTAN):**\n\n" + "\n\n".join(f"- {task}" for task in l2_tasks))
                else:
                    st.info("**JADWAL L2 SHIFT INI (URUTAN):**\n\n" + "\n\n".join(f"- {task}" for task in l2_tasks))
                
                with st.expander("Klik untuk lihat detail Net Tonase Akhir"):
                    df_akhir = pd.DataFrame({
                        'Varian Produk': ['40 Kertas', '40K CPM', '40 Plastik', '40P CPM', '50 Kertas', '50K CPM'],
                        'Net (Ton)': [net_40k, net_40kc, net_40p, net_40pc, net_50k, net_50kc]
                    })
                    st.dataframe(df_akhir, hide_index=True)

    else:
        st.warning("Mohon masukkan teks Stok Gudang dan Data SO terlebih dahulu.")
