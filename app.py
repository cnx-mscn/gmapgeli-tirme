import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from datetime import timedelta
from haversine import haversine
from PIL import Image
import io

# Google Maps API Anahtarınızı girin
gmaps = googlemaps.Client(key="AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws")

# PAGE CONFIG
title = "Montaj Rota Planlayıcı"
st.set_page_config(page_title=title, layout="wide")
st.title(f"🛠️ {title}")

# GLOBAL Sabitler
SAATLIK_ISCILIK = st.sidebar.number_input("Saatlik İŞçilik Ücreti (TL)", min_value=100, value=500, step=50)
benzin_fiyati = st.sidebar.number_input("Benzin Fiyatı (TL/L)", min_value=0.1, value=10.0, step=0.1)
km_basi_tuketim = st.sidebar.number_input("Km Başına Tüketim (L/km)", min_value=0.01, value=0.1, step=0.01)
siralama_tipi = st.sidebar.radio("Rota Sıralama Tipi", ["Önem Derecesi", "En Kısa Rota"])

# Session Init
if "ekipler" not in st.session_state:
    st.session_state.ekipler = {}
if "aktif_ekip" not in st.session_state:
    st.session_state.aktif_ekip = None
if "baslangic_konum" not in st.session_state:
    st.session_state.baslangic_konum = None
if "kullanici_tipi" not in st.session_state:
    st.session_state.kullanici_tipi = "Yönetici"  # Varsayılan olarak yönetici

# Kullanıcı Tipi Seçimi (Yönetici / İşçi)
kullanici_tipi = st.sidebar.selectbox("Kullanıcı Tipini Seç", ["Yönetici", "İşçi"])
st.session_state.kullanici_tipi = kullanici_tipi

# Ekip Yönetimi
if st.session_state.kullanici_tipi == "Yönetici":
    st.sidebar.subheader("👷 Ekip Yönetimi")
    ekip_adi = st.sidebar.text_input("Yeni Ekip Adı")
    if st.sidebar.button("➕ Ekip Oluştur") and ekip_adi:
        if ekip_adi not in st.session_state.ekipler:
            st.session_state.ekipler[ekip_adi] = {"members": [], "visited_cities": []}
            st.session_state.aktif_ekip = ekip_adi

    aktif_secim = st.sidebar.selectbox("Aktif Ekip Seç", list(st.session_state.ekipler.keys()))
    st.session_state.aktif_ekip = aktif_secim

    # Başlangıç Noktası
    st.sidebar.subheader("📍 Başlangıç Noktası")
    if not st.session_state.baslangic_konum:
        adres_input = st.sidebar.text_input("Manuel Adres Girin (1 kez girilir)")
        if st.sidebar.button("✅ Adres Onayla") and adres_input:
            sonuc = gmaps.geocode(adres_input)
            if sonuc:
                st.session_state.baslangic_konum = sonuc[0]["geometry"]["location"]
                st.sidebar.success("Başlangıç noktası belirlendi.")
            else:
                st.sidebar.error("Adres bulunamadı.")

    # Şehir Ekleme
    st.subheader("📌 Şehir Ekle")
    with st.form("sehir_form"):
        sehir_adi = st.text_input("Şehir / Bayi Adı")
        onem = st.slider("Önem Derecesi", 1, 5, 3)
        is_suresi = st.number_input("Montaj Süre (saat)", 1, 24, 2)
        tarih = st.date_input("Montaj Tarihi")
        ekle_btn = st.form_submit_button("➕ Şehir Ekle")
        if ekle_btn:
            sonuc = gmaps.geocode(sehir_adi)
            if sonuc:
                konum = sonuc[0]["geometry"]["location"]
                st.session_state.ekipler[st.session_state.aktif_ekip]["visited_cities"].append({
                    "sehir": sehir_adi,
                    "konum": konum,
                    "onem": onem,
                    "is_suresi": is_suresi,
                    "tarih": str(tarih)
                })
                st.success(f"{sehir_adi} eklendi.")
            else:
                st.error("Konum bulunamadı.")

    # Harita Oluşturma
    st.subheader("🗺️ Aktif Ekiplerin Haritası")
    if st.session_state.baslangic_konum:
        baslangic = st.session_state.baslangic_konum
        harita = folium.Map(location=[baslangic["lat"], baslangic["lng"]], zoom_start=6)
        folium.Marker([baslangic["lat"], baslangic["lng"]], popup="Başlangıç", icon=folium.Icon(color="blue")).add_to(harita)

        ekip = st.session_state.ekipler[st.session_state.aktif_ekip]
        sehirler = ekip["visited_cities"]
        if siralama_tipi == "Önem Derecesi":
            sehirler = sorted(sehirler, key=lambda x: x["onem"], reverse=True)
        else:
            sehirler = sorted(sehirler, key=lambda x: haversine(
                (baslangic["lat"], baslangic["lng"]),
                (x["konum"]["lat"], x["konum"]["lng"])
            ))

        for i, sehir in enumerate(sehirler, 1):
            lat, lng = sehir["konum"]["lat"], sehir["konum"]["lng"]
            folium.Marker(
                [lat, lng],
                popup=f"{i}. {sehir['sehir']} (Onem: {sehir['onem']})\nTarih: {sehir['tarih']}",
                icon=folium.DivIcon(html=f"<div style='font-size: 12pt; color: red'>{i}</div>")
            ).add_to(harita)
            folium.PolyLine([(baslangic["lat"], baslangic["lng"]), (lat, lng)], color="green").add_to(harita)
            baslangic = sehir["konum"]

        st_folium(harita, width=700)

elif st.session_state.kullanici_tipi == "İşçi":
    # İşçi Arayüzü: Şehir Görevleri, Fotoğraf Yükleme
    st.subheader("📸 İşçi Görev ve Fotoğraf Yükleme")
    aktif_ekip = st.session_state.ekipler.get(st.session_state.aktif_ekip)
    if aktif_ekip:
        for sehir in aktif_ekip["visited_cities"]:
            sehir_adi = sehir["sehir"]
            # İşçi görevi için şehir detayları göster
            st.write(f"Şehir: {sehir_adi}")
            st.write(f"Montaj Süresi: {sehir['is_suresi']} saat")
            st.write(f"Tarih: {sehir['tarih']}")
            
            # İşçi fotoğraf yükleme seçeneği
            uploaded_file = st.file_uploader(f"{sehir_adi} Fotoğraf Yükleyin", type=["jpg", "jpeg", "png"])
            if uploaded_file is not None:
                img = Image.open(uploaded_file)
                st.image(img, caption=f"{sehir_adi} fotoğrafı", use_column_width=True)
                if st.button(f"Yönetici Onayı İçin Gönder: {sehir_adi}"):
                    # Fotoğraf, işçinin görevi tamamladığını ve yöneticinin onayını beklediğini belirtmek için güncellenecek
                    sehir["fotoğraf"] = uploaded_file.name
                    sehir["onay"] = False  # Fotoğrafın onayı bekleniyor
                    st.success(f"{sehir_adi} için fotoğraf gönderildi. Yöneticinin onayını bekliyor...")

