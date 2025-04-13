import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from datetime import timedelta
from haversine import haversine

# Google Maps API Anahtarı
gmaps = googlemaps.Client(key="AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws")

st.set_page_config("Montaj Rota Planlayıcı", layout="wide")
st.title("🛠️ Montaj Rota Planlayıcı")

# Sidebar ayarları
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
    st.session_state.sehirler = {}
if "baslangic_konum" not in st.session_state:
    st.session_state.baslangic_konum = None

# Ekip Yönetimi
st.sidebar.subheader("👷 Ekip Yönetimi")
ekip_adi = st.sidebar.text_input("Yeni Ekip Adı")
if st.sidebar.button("➕ Ekip Oluştur") and ekip_adi:
    if ekip_adi not in st.session_state.ekipler:
        st.session_state.ekipler[ekip_adi] = {"members": []}
        st.session_state.sehirler[ekip_adi] = []
        st.session_state.aktif_ekip = ekip_adi

if st.session_state.ekipler:
    aktif_secim = st.sidebar.selectbox("Aktif Ekip Seç", list(st.session_state.ekipler.keys()))
    st.session_state.aktif_ekip = aktif_secim

# Başlangıç Konumu
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

# Ekip Üyeleri
with st.sidebar.expander("👤 Ekip Üyeleri"):
    uye_adi = st.text_input("Yeni Üye Adı")
    if st.button("✅ Üye Ekle") and uye_adi and st.session_state.aktif_ekip:
        st.session_state.ekipler[st.session_state.aktif_ekip]["members"].append(uye_adi)

    for i, uye in enumerate(st.session_state.ekipler[st.session_state.aktif_ekip]["members"]):
        st.markdown(f"- {uye}")

# Şehir Ekleme
if st.session_state.aktif_ekip:
    st.subheader(f"📌 Şehir Ekle ({st.session_state.aktif_ekip})")
    with st.form("sehir_form"):
        sehir_adi = st.text_input("Şehir / Bayi Adı")
        onem = st.slider("Önem Derecesi", 1, 5, 3)
        is_suresi = st.number_input("Montaj Süresi (saat)", 1, 24, 2)
        ekle_btn = st.form_submit_button("➕ Şehir Ekle")
        if ekle_btn:
            sonuc = gmaps.geocode(sehir_adi)
            if sonuc:
                konum = sonuc[0]["geometry"]["location"]
                st.session_state.sehirler[st.session_state.aktif_ekip].append({
                    "sehir": sehir_adi,
                    "konum": konum,
                    "onem": onem,
                    "is_suresi": is_suresi
                })
                st.success(f"{sehir_adi} eklendi.")
            else:
                st.error("Konum bulunamadı.")

# Rota ve Hesaplama
if st.session_state.baslangic_konum and st.session_state.aktif_ekip:
    baslangic = st.session_state.baslangic_konum
    sehirler = st.session_state.sehirler.get(st.session_state.aktif_ekip, []).copy()

    if sehirler:
        if siralama_tipi == "Önem Derecesi":
            sehirler.sort(key=lambda x: x["onem"], reverse=True)
        else:
            rota = []
            current = baslangic
            while sehirler:
                en_yakin = min(sehirler, key=lambda x: haversine((current["lat"], current["lng"]), (x["konum"]["lat"], x["konum"]["lng"])) )
                rota.append(en_yakin)
                current = en_yakin["konum"]
                sehirler.remove(en_yakin)
            sehirler = rota

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
                km = yol[0]["legs"][0]["distance"]["value"] / 1000
                sure_dk = yol[0]["legs"][0]["duration"]["value"] / 60
                toplam_km += km
                toplam_sure += sure_dk
                yakit_maliyeti = km * km_basi_tuketim * benzin_fiyati
                toplam_yakit += yakit_maliyeti
                montaj_suresi = sehirler[i]["is_suresi"]
                toplam_iscilik += montaj_suresi * SAATLIK_ISCILIK
                toplam_maliyet += yakit_maliyeti + (montaj_suresi * SAATLIK_ISCILIK)

                folium.Marker(
                    location=[konumlar[i + 1]["lat"], konumlar[i + 1]["lng"]],
                    popup=f"{i+1}. {sehirler[i]['sehir']}<br>İşçilik: {round(montaj_suresi * SAATLIK_ISCILIK, 2)} TL<br>Yakıt: {round(yakit_maliyeti, 2)} TL",
                    tooltip=f"{round(km)} km, {round(sure_dk)} dk"
                ).add_to(harita)

        toplam_sure_td = timedelta(minutes=toplam_sure)

        # Harita ve Özet
        st.subheader(f"🗺️ {st.session_state.aktif_ekip} Rota Haritası")
        st_folium(harita, width=1000, height=600)

        st.markdown("---")
        st.subheader("📊 Rota Özeti")
        st.markdown(f"**Toplam Mesafe:** {round(toplam_km, 1)} km")
        st.markdown(f"**Toplam Süre:** {toplam_sure_td}")
        st.markdown(f"**Yakıt Maliyeti:** {round(toplam_yakit)} TL")
        st.markdown(f"**İşçilik Maliyeti:** {round(toplam_iscilik)} TL")
        st.markdown(f"**Toplam Maliyet:** {round(toplam_maliyet)} TL")

    else:
        st.info("Bu ekip için henüz şehir girilmedi.")

else:
    st.info("Lütfen başlangıç adresi ve bir ekip oluşturup şehir girin.")
    # ================================
# 🔍 Tüm Ekip Karşılaştırma Tablosu
# ================================
st.markdown("---")
st.header("📋 Tüm Ekiplerin Karşılaştırması")

ekip_ozetleri = []

for ekip_adi, sehirler_liste in st.session_state.sehirler.items():
    if not sehirler_liste or not st.session_state.baslangic_konum:
        continue

    baslangic = st.session_state.baslangic_konum
    sehirler = sehirler_liste.copy()

    # Aynı sıralama algoritması
    if siralama_tipi == "Önem Derecesi":
        sehirler.sort(key=lambda x: x["onem"], reverse=True)
    else:
        rota = []
        current = baslangic
        while sehirler:
            en_yakin = min(sehirler, key=lambda x: haversine((current["lat"], current["lng"]), (x["konum"]["lat"], x["konum"]["lng"])) )
            rota.append(en_yakin)
            current = en_yakin["konum"]
            sehirler.remove(en_yakin)
        sehirler = rota

    toplam_km = 0
    toplam_sure = 0
    toplam_iscilik = 0
    toplam_yakit = 0

    konumlar = [baslangic] + [s["konum"] for s in sehirler]
    for i in range(len(konumlar) - 1):
        yol = gmaps.directions(
            (konumlar[i]["lat"], konumlar[i]["lng"]),
            (konumlar[i + 1]["lat"], konumlar[i + 1]["lng"]),
            mode="driving"
        )
        if yol:
            km = yol[0]["legs"][0]["distance"]["value"] / 1000
            sure_dk = yol[0]["legs"][0]["duration"]["value"] / 60
            toplam_km += km
            toplam_sure += sure_dk
            yakit_maliyeti = km * km_basi_tuketim * benzin_fiyati
            toplam_yakit += yakit_maliyeti
            montaj_suresi = sehirler[i]["is_suresi"]
            toplam_iscilik += montaj_suresi * SAATLIK_ISCILIK

    toplam_maliyet = toplam_yakit + toplam_iscilik
    ekip_ozetleri.append({
        "Ekip": ekip_adi,
        "Toplam KM": round(toplam_km, 1),
        "Toplam Süre (saat)": round(toplam_sure / 60, 1),
        "Yakıt Maliyeti (TL)": round(toplam_yakit),
        "İşçilik Maliyeti (TL)": round(toplam_iscilik),
        "Toplam Maliyet (TL)": round(toplam_maliyet)
    })

# Tablo Göster
if ekip_ozetleri:
    st.dataframe(ekip_ozetleri, use_container_width=True)
else:
    st.info("Henüz karşılaştırılabilir ekip verisi yok.")

import pandas as pd
from fpdf import FPDF
import base64
from io import BytesIO

st.markdown("## 📤 Çıktı Al")

# Excel İndir
if ekip_ozetleri:
    df = pd.DataFrame(ekip_ozetleri)

    # Excel
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Ekip Özeti")
    excel_data = excel_buffer.getvalue()

    b64_excel = base64.b64encode(excel_data).decode()
    href_excel = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_excel}" download="ekip_ozeti.xlsx">📥 Excel Olarak İndir</a>'
    st.markdown(href_excel, unsafe_allow_html=True)

    # PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Ekip Özeti", ln=True, align="C")
    pdf.ln(10)

    for row in ekip_ozetleri:
        for key, val in row.items():
            pdf.cell(200, 10, txt=f"{key}: {val}", ln=True)
        pdf.ln(5)

    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_data = pdf_buffer.getvalue()

    b64_pdf = base64.b64encode(pdf_data).decode()
    href_pdf = f'<a href="data:application/pdf;base64,{b64_pdf}" download="ekip_ozeti.pdf">📥 PDF Olarak İndir</a>'
    st.markdown(href_pdf, unsafe_allow_html=True)


