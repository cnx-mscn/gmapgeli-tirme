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

# Google Maps API Anahtarınızı girin
gmaps = googlemaps.Client(key="AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws")

st.set_page_config("Montaj Rota Planlayıcı", layout="wide")
st.title("🛠️ Montaj Rota Planlayıcı")

# GLOBAL Sabitler
SAATLIK_ISCILIK = st.sidebar.number_input("Saatlik İşçilik Ücreti (TL)", min_value=100, value=500, step=50)
benzin_fiyati = st.sidebar.number_input("Benzin Fiyatı (TL/L)", min_value=0.1, value=10.0, step=0.1)
km_basi_tuketim = st.sidebar.number_input("Km Başına Tüketim (L/km)", min_value=0.01, value=0.1, step=0.01)
siralama_tipi = st.sidebar.radio("Rota Sıralama Tipi", ["Önem Derecesi", "En Kısa Rota"])

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
        st.session_state.ekipler[ekip_adi] = {"members": []}
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

# Üye Ekle
with st.sidebar.expander("👤 Ekip Üyeleri"):
    uye_adi = st.text_input("Yeni Üye Adı")
    if st.button("✅ Üye Ekle") and uye_adi:
        st.session_state.ekipler[st.session_state.aktif_ekip]["members"].append(uye_adi)

    for i, uye in enumerate(st.session_state.ekipler[st.session_state.aktif_ekip]["members"]):
        st.markdown(f"- {uye}")

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
            st.session_state.sehirler.append({
                "sehir": sehir_adi,
                "konum": konum,
                "onem": onem,
                "is_suresi": is_suresi
            })
            st.success(f"{sehir_adi} eklendi.")
        else:
            st.error("Konum bulunamadı.")

# Rota ve Hesaplama
if st.session_state.baslangic_konum and st.session_state.sehirler:
    baslangic = st.session_state.baslangic_konum
    sehirler = st.session_state.sehirler.copy()

    # Rota sıralama
    if siralama_tipi == "Önem Derecesi":
        sehirler.sort(key=lambda x: x["onem"], reverse=True)
    else:  # En kısa rota (basit nearest neighbor)
        rota = []
        current = baslangic
        while sehirler:
            en_yakin = min(sehirler, key=lambda x: haversine((current["lat"], current["lng"]), (x["konum"]["lat"], x["konum"]["lng"])) )
            rota.append(en_yakin)
            current = en_yakin["konum"]
            sehirler.remove(en_yakin)
        sehirler = rota

    # Harita
    harita = folium.Map(location=[baslangic["lat"], baslangic["lng"]], zoom_start=6)
    toplam_km = 0
    toplam_sure = 0
    toplam_iscilik = 0
    toplam_yakit = 0
    toplam_maliyet = 0

    konumlar = [baslangic] + [s["konum"] for s in sehirler]
    for i in range(len(konumlar) - 1):
        yol = gmaps.directions(
            (konumlar[i]["lat"], konumlar[i]["lng"]),
            (konumlar[i + 1]["lat"], konumlar[i + 1]["lng"]),
            mode="driving"
        )
        if yol:
            km = yol[0]["legs"][0]["distance"]["value"] / 1000  # km olarak mesafe
            sure_dk = yol[0]["legs"][0]["duration"]["value"] / 60  # dakika cinsinden süre
            toplam_km += km
            toplam_sure += sure_dk
            yakit_maliyeti = km * km_basi_tuketim * benzin_fiyati
            toplam_yakit += yakit_maliyeti
            montaj_suresi = st.session_state.sehirler[i]["is_suresi"]
            toplam_iscilik += montaj_suresi * SAATLIK_ISCILIK
            toplam_maliyet += yakit_maliyeti + (montaj_suresi * SAATLIK_ISCILIK)

            folium.Marker(
                location=[konumlar[i + 1]["lat"], konumlar[i + 1]["lng"]],
                popup=f"{i+1}. {st.session_state.sehirler[i]['sehir']}<br>İşçilik: {round(montaj_suresi * SAATLIK_ISCILIK, 2)} TL<br>Yakıt: {round(yakit_maliyeti, 2)} TL",
                tooltip=f"{round(km)} km, {round(sure_dk)} dk"
            ).add_to(harita)

    toplam_sure_td = timedelta(minutes=toplam_sure)

    # Rota Haritası
    st.subheader("🗺️ Rota Haritası")
    st_folium(harita, width=1000, height=600)

    # PDF Raporu Oluşturma
    pdf = FPDF()
    pdf.add_page()

    # Türkçe karakter destekli font
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', '', 12)

    # PDF İçeriği
    pdf.cell(200, 10, txt=f"Toplam Mesafe: {round(toplam_km, 1)} km", ln=True)
    pdf.cell(200, 10, txt=f"Toplam Süre: {toplam_sure_td}", ln=True)
    pdf.cell(200, 10, txt=f"Yakıt Maliyeti: {round(toplam_yakit)} TL", ln=True)
    pdf.cell(200, 10, txt=f"İşçilik Maliyeti: {round(toplam_iscilik)} TL", ln=True)
    pdf.cell(200, 10, txt=f"Toplam Maliyet: {round(toplam_maliyet)} TL", ln=True)

    # PDF Çıktısı
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)

    # PDF'yi kullanıcıya sunma
    pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
    pdf_url = f"data:application/pdf;base64,{pdf_base64}"
    st.markdown(f'<a href="{pdf_url}" download="montaj_raporu.pdf">PDF olarak indir</a>', unsafe_allow_html=True)

else:
    st.info("Lütfen başlangıç adresi ve en az 1 şehir giriniz.")
