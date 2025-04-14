# app.py

import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from haversine import haversine
from fpdf import FPDF
import base64
from io import BytesIO
import pandas as pd
import io
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook

# GOOGLE MAPS API ANAHTARINIZI GİRİN
gmaps = googlemaps.Client(key="AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws")  # 🔑 <-- API anahtarınızı buraya yazın

# PAGE CONFIG
st.set_page_config("Montaj Rota Planlayıcı", layout="wide")
st.title("🛠️ Montaj Rota Planlayıcı")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Genel Ayarlar")
SAATLIK_ISCILIK = st.sidebar.number_input("Saatlik İşçilik Ücreti (TL)", min_value=100, value=500, step=50)
benzin_fiyati = st.sidebar.number_input("Benzin Fiyatı (TL/L)", min_value=0.1, value=10.0, step=0.1)
km_basi_tuketim = st.sidebar.number_input("Km Başına Tüketim (L/km)", min_value=0.01, value=0.1, step=0.01)
siralama_tipi = st.sidebar.radio("Rota Sıralama Tipi", ["Önem Derecesi", "En Kısa Rota"])

# --- SESSION ---
if "ekipler" not in st.session_state:
    st.session_state.ekipler = {}
if "aktif_ekip" not in st.session_state:
    st.session_state.aktif_ekip = None
if "baslangic_konum" not in st.session_state:
    st.session_state.baslangic_konum = None

# --- EKİP YÖNETİMİ ---
st.sidebar.subheader("👷 Ekip Yönetimi")
ekip_adi = st.sidebar.text_input("Yeni Ekip Adı")
if st.sidebar.button("➕ Ekip Oluştur") and ekip_adi:
    if ekip_adi not in st.session_state.ekipler:
        st.session_state.ekipler[ekip_adi] = {"members": [], "visited_cities": []}
        st.session_state.aktif_ekip = ekip_adi

aktif_secim = st.sidebar.selectbox("Aktif Ekip Seç", list(st.session_state.ekipler.keys()))
st.session_state.aktif_ekip = aktif_secim

st.sidebar.markdown("### 👥 Ekip Üyeleri")
aktif_ekip = st.session_state.aktif_ekip
if aktif_ekip:
    members = st.session_state.ekipler[aktif_ekip]["members"]
    for idx, member in enumerate(members):
        col1, col2 = st.sidebar.columns([4, 1])
        col1.write(member)
        if col2.button("❌", key=f"remove_{idx}"):
            members.pop(idx)
            st.experimental_rerun()

    new_member = st.sidebar.text_input("Yeni Üye Ekle", key="new_member_input")
    if st.sidebar.button("➕ Üye Ekle"):
        if new_member:
            st.session_state.ekipler[aktif_ekip]["members"].append(new_member)
            st.success(f"{new_member} eklendi.")

# --- BAŞLANGIÇ KONUMU ---
st.sidebar.subheader("📍 Başlangıç Noktası")
if not st.session_state.baslangic_konum:
    adres_input = st.sidebar.text_input("Adres (Sadece 1 kez girilir)")
    if st.sidebar.button("✅ Adres Onayla") and adres_input:
        sonuc = gmaps.geocode(adres_input)
        if sonuc:
            st.session_state.baslangic_konum = sonuc[0]["geometry"]["location"]
            st.sidebar.success("Başlangıç noktası belirlendi.")
        else:
            st.sidebar.error("Adres bulunamadı.")

# --- ŞEHİR EKLE ---
st.subheader("📌 Şehir / Bayi Ekle")
with st.form("sehir_form"):
    sehir_adi = st.text_input("Şehir veya Bayi Adı")
    onem = st.slider("Önem Derecesi", 1, 5, 3)
    is_suresi = st.number_input("Montaj Süresi (saat)", 1, 24, 2)
    ekle_btn = st.form_submit_button("➕ Şehir Ekle")
    if ekle_btn and st.session_state.aktif_ekip:
        sonuc = gmaps.geocode(sehir_adi)
        if sonuc:
            konum = sonuc[0]["geometry"]["location"]
            st.session_state.ekipler[st.session_state.aktif_ekip]["visited_cities"].append({
                "sehir": sehir_adi,
                "konum": konum,
                "onem": onem,
                "is_suresi": is_suresi
            })
            st.success(f"{sehir_adi} başarıyla eklendi.")
        else:
            st.error("Konum bulunamadı.")

# --- HARİTA VE ROTA ---
st.subheader("🗺️ Harita ve Rota Gösterimi")
if st.session_state.baslangic_konum:
    for ekip, detay in st.session_state.ekipler.items():
        st.markdown(f"### 🚚 {ekip} Ekibi Haritası")
        harita = folium.Map(location=[st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]], zoom_start=6)

        rota = sorted(detay["visited_cities"], key=lambda x: x["onem"], reverse=True) if siralama_tipi == "Önem Derecesi" else detay["visited_cities"].copy()
        if siralama_tipi == "En Kısa Rota":
            rota.sort(key=lambda c: haversine((st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]),
                                              (c["konum"]["lat"], c["konum"]["lng"])))

        # Başlangıç noktası
        folium.Marker(
            [st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]],
            popup="Başlangıç",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(harita)

        prev_latlng = (st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"])
        for idx, sehir in enumerate(rota, start=1):
            latlng = (sehir["konum"]["lat"], sehir["konum"]["lng"])
            folium.Marker(
                latlng,
                popup=f"{idx}. {sehir['sehir']} (Önem: {sehir['onem']})",
                icon=folium.DivIcon(html=f"<div style='font-size: 12pt; color: red'>{idx}</div>")
            ).add_to(harita)
            folium.PolyLine([prev_latlng, latlng], color="red", weight=2.5).add_to(harita)
            prev_latlng = latlng

        st_folium(harita, width=800, height=500)

# --- EXCEL ---
st.subheader("📊 Excel Raporu")
def generate_excel():
    data = []
    for ekip, detay in st.session_state.ekipler.items():
        for sehir in detay["visited_cities"]:
            km = haversine(
                (st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]),
                (sehir["konum"]["lat"], sehir["konum"]["lng"])
            )
            yol_masraf = km * km_basi_tuketim * benzin_fiyati
            iscik_maliyet = sehir["is_suresi"] * SAATLIK_ISCILIK
            toplam = yol_masraf + iscik_maliyet
            data.append({
                "Ekip Adı": ekip,
                "Şehir": sehir["sehir"],
                "Montaj Süresi": sehir["is_suresi"],
                "Önem Derecesi": sehir["onem"],
                "İşçilik Maliyeti (TL)": round(iscik_maliyet),
                "Yol Masrafı (TL)": round(yol_masraf),
                "Toplam Maliyet (TL)": round(toplam),
                "Ekip Üyeleri": ", ".join(detay["members"])
            })

    df = pd.DataFrame(data)
    excel_io = BytesIO()
    with pd.ExcelWriter(excel_io, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Montaj Planı")
        ws = writer.book["Montaj Planı"]
        for col in ws.columns:
            max_length = max(len(str(cell.value)) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max_length + 2
    excel_io.seek(0)
    return excel_io

st.download_button(
    label="📥 Excel Olarak İndir",
    data=generate_excel(),
    file_name="montaj_plani.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
