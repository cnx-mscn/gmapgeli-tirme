import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from datetime import datetime
import pandas as pd
import io
from fpdf import FPDF
from io import BytesIO
import base64
from haversine import haversine
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook

# Google Maps API Anahtarı
API_KEY = "AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws"
gmaps = googlemaps.Client(key=API_KEY)

# Sayfa konfigürasyonu
st.set_page_config("Montaj Rota Planlayıcı", layout="wide")
st.title("🛠️ Montaj Rota Planlayıcı")

# Sidebar ayarları
SAATLIK_ISCILIK = st.sidebar.number_input("Saatlik İşçilik Ücreti (TL)", min_value=100, value=500, step=50)
benzin_fiyati = st.sidebar.number_input("Benzin Fiyatı (TL/L)", min_value=0.1, value=10.0, step=0.1)
km_basi_tuketim = st.sidebar.number_input("Km Başına Tüketim (L/km)", min_value=0.01, value=0.1, step=0.01)
siralama_tipi = st.sidebar.radio("Rota Sıralama Tipi", ["Önem Derecesi", "En Kısa Rota"])

# Session State başlat
if "ekipler" not in st.session_state:
    st.session_state.ekipler = {}
if "aktif_ekip" not in st.session_state:
    st.session_state.aktif_ekip = None
if "baslangic_konum" not in st.session_state:
    st.session_state.baslangic_konum = None

# Ekip yönetimi
st.sidebar.subheader("👷 Ekip Yönetimi")
ekip_adi = st.sidebar.text_input("Yeni Ekip Adı")
if st.sidebar.button("➕ Ekip Oluştur") and ekip_adi:
    if ekip_adi not in st.session_state.ekipler:
        st.session_state.ekipler[ekip_adi] = {"members": [], "visited_cities": []}
        st.session_state.aktif_ekip = ekip_adi
aktif_secim = st.sidebar.selectbox("Aktif Ekip Seç", list(st.session_state.ekipler.keys()))
st.session_state.aktif_ekip = aktif_secim

# Ekip üyeleri
st.sidebar.subheader("Ekip Üyeleri")
aktif_ekip = st.session_state.aktif_ekip
if aktif_ekip:
    members = st.session_state.ekipler[aktif_ekip]["members"]
    for idx, member in enumerate(members):
        cols = st.sidebar.columns([5,1])
        cols[0].write(member)
        if cols[1].button("❌", key=f"remove_{aktif_ekip}_{idx}"):
            st.session_state.ekipler[aktif_ekip]["members"].pop(idx)
            st.experimental_rerun()

    new_member = st.sidebar.text_input(f"{aktif_ekip} için yeni üye", key=f"new_member_{aktif_ekip}")
    if st.sidebar.button(f"➕ {aktif_ekip} Üyesi Ekle"):
        if new_member:
            st.session_state.ekipler[aktif_ekip]["members"].append(new_member)
            st.experimental_rerun()

# Başlangıç konumu
st.sidebar.subheader("📍 Başlangıç Noktası")
if not st.session_state.baslangic_konum:
    adres_input = st.sidebar.text_input("Adres Girin")
    if st.sidebar.button("✅ Adres Onayla"):
        sonuc = gmaps.geocode(adres_input)
        if sonuc:
            st.session_state.baslangic_konum = sonuc[0]["geometry"]["location"]
            st.sidebar.success("Başlangıç noktası kaydedildi.")
        else:
            st.sidebar.error("Adres bulunamadı.")

# Şehir ekleme formu
st.subheader("📌 Şehir / Bayi Ekle")
with st.form("sehir_form"):
    sehir_adi = st.text_input("Şehir veya Bayi Adı")
    onem = st.slider("Önem Derecesi", 1, 5, 3)
    is_suresi = st.number_input("Montaj Süresi (saat)", 1, 24, 2)
    tarih = st.date_input("Planlanan Tarih")
    ekle_btn = st.form_submit_button("➕ Şehir Ekle")

    if ekle_btn and st.session_state.baslangic_konum and aktif_ekip:
        sonuc = gmaps.geocode(sehir_adi)
        if sonuc:
            konum = sonuc[0]["geometry"]["location"]
            st.session_state.ekipler[aktif_ekip]["visited_cities"].append({
                "sehir": sehir_adi,
                "konum": konum,
                "onem": onem,
                "is_suresi": is_suresi,
                "tarih": tarih
            })
            st.success(f"{sehir_adi} eklendi.")
        else:
            st.error("Konum bulunamadı.")

# Harita çizimi
st.subheader("🗺️ Harita")
if st.session_state.baslangic
::contentReference[oaicite:0]{index=0}
 
