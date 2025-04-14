import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from datetime import timedelta
from haversine import haversine
from fpdf import FPDF
import base64
from io import BytesIO
import pandas as pd
import io

# Google Maps API Anahtarınızı girin
gmaps = googlemaps.Client(key="AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws")

# PAGE CONFIG, Bu satır en başta olmalı
st.set_page_config("Montaj Rota Planlayıcı", layout="wide")

st.title("🛠️ Montaj Rota Planlayıcı")

# GLOBAL Sabitler
SAATLIK_ISCILIK = st.sidebar.number_input("Saatlik İşçilik Ücreti (TL)", min_value=100, value=500, step=50)
benzin_fiyati = st.sidebar.number_input("Benzin Fiyatı (TL/L)", min_value=0.1, value=10.0, step=0.1)
km_basi_tuketim = st.sidebar.number_input("Km Başına Tüketim (L/km)", min_value=0.01, value=0.1, step=0.01)
siralama_tipi = st.sidebar.radio("Rota Sıralama Tipi", ["Önem Derecesi", "En Kısa Rota"])

# PDF oluşturma fonksiyonu
def create_pdf(toplam_km, toplam_sure_td, toplam_yakit, toplam_iscilik, toplam_maliyet):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)

    # PDF içeriği
    pdf.cell(200, 10, txt=f"Toplam Mesafe: {round(toplam_km, 1)} km", ln=True)
    pdf.cell(200, 10, txt=f"Toplam Süre: {toplam_sure_td}", ln=True)
    pdf.cell(200, 10, txt=f"Yakıt Maliyeti: {round(toplam_yakit)} TL", ln=True)
    pdf.cell(200, 10, txt=f"İşçilik Maliyeti: {round(toplam_iscilik)} TL", ln=True)
    pdf.cell(200, 10, txt=f"Toplam Maliyet: {round(toplam_maliyet)} TL", ln=True)

    # PDF'yi belleğe yaz
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)

    # PDF'yi base64 formatında encode et
    pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
    pdf_url = f"data:application/pdf;base64,{pdf_base64}"

    return pdf_url

# Kullanıcıya PDF indir linki sunma
def display_pdf_link(pdf_url):
    st.markdown(f'<a href="{pdf_url}" download="montaj_raporu.pdf">PDF olarak indir</a>', unsafe_allow_html=True)

# Session Init
if "ekipler" not in st.session_state:
    st.session_state.ekipler = {}
if "aktif_ekip" not in st.session_state:
    st.session_state.aktif_ekip = None
if "sehirler" not in st.session_state:
    st.session_state.sehirler = []
if "baslangic_konum" not in st.session_state:
    st.session_state.baslangic_konum = None

# Ekip Yönetimi
st.sidebar.subheader("👷 Ekip Yönetimi")
ekip_adi = st.sidebar.text_input("Yeni Ekip Adı")
if st.sidebar.button("➕ Ekip Oluştur") and ekip_adi:
    if ekip_adi not in st.session_state.ekipler:
        st.session_state.ekipler[ekip_adi] = {"members": [], "visited_cities": []}
        st.session_state.aktif_ekip = ekip_adi
aktif_secim = st.sidebar.selectbox("Aktif Ekip Seç", list(st.session_state.ekipler.keys()))
st.session_state.aktif_ekip = aktif_secim

# Başlangıç Adresi Girişi
st.sidebar.subheader("📍 Başlangıç Noktası")
if not st.session_state.baslangic_konum:
    adres_input = st.sidebar.text_input("Manuel Adres Girin (1 kez girilir)")
    if st.sidebar.button("✅ Adres Onayla") and adres_input:
        try:
            sonuc = gmaps.geocode(adres_input)
            if sonuc:
                st.session_state.baslangic_konum = sonuc[0]["geometry"]["location"]
                st.sidebar.success("Başlangıç noktası belirlendi.")
            else:
                st.sidebar.error("Adres bulunamadı.")
        except:
            st.sidebar.error("API Hatası.")

# Şehir/Bayi Ekleme
st.subheader("📌 Şehir Ekle")
with st.form("sehir_form"):
    sehir_adi = st.text_input("Şehir / Bayi Adı")
    onem = st.slider("Önem Derecesi", 1, 5, 3)
    is_suresi = st.number_input("Montaj Süresi (saat)", 1, 24, 2)
    ekle_btn = st.form_submit_button("➕ Şehir Ekle")
    if ekle_btn:
        sonuc = gmaps.geocode(sehir_adi)
        if sonuc:
            konum = sonuc[0]["geometry"]["location"]
            # Ekip için şehir ekle
            aktif_ekip = st.session_state.aktif_ekip
            st.session_state.ekipler[aktif_ekip]["visited_cities"].append({
                "sehir": sehir_adi,
                "konum": konum,
                "onem": onem,
                "is_suresi": is_suresi
            })
            st.success(f"{sehir_adi} eklendi.")
        else:
            st.error("Konum bulunamadı.")

# Excel raporu oluşturma
def generate_excel():
    data = []
    for ekip, details in st.session_state.ekipler.items():
        for sehir in details["visited_cities"]:
            row = {
                "Ekip Adı": ekip,
                "Şehir": sehir["sehir"],
                "Montaj Süresi (saat)": sehir["is_suresi"],
                "Önem Derecesi": sehir["onem"],
            }
            data.append(row)

    df = pd.DataFrame(data)

    # Excel dosyasını belleğe kaydetme
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Montaj Planı")
    excel_buffer.seek(0)
    return excel_buffer

# Excel dosyasını dışa aktar
st.download_button(
    label="Excel Olarak İndir",
    data=generate_excel(),
    file_name="montaj_plani.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
