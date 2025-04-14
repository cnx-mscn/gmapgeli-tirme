import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from haversine import haversine
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

# Harita oluşturma ve rota hesaplama
def calculate_route(city_data, baslangic_konum, rotasi_tipi):
    """ Rota hesaplaması (en kısa veya önemliye göre sıralama) """
    # Rota oluşturulacak şehirlerin listesi
    city_coords = [(sehir["sehir"], sehir["konum"]) for sehir in city_data]
    
    # En kısa yol için koordinatlar
    route = [baslangic_konum] + [sehir["konum"] for sehir in city_data]
    
    # Rota sıralama (önem sırasına göre veya en kısa rota)
    if rotasi_tipi == "En Kısa Rota":
        # Google Maps API ile rotayı hesapla
        result = gmaps.directions(baslangic_konum, route[-1], waypoints=[sehir["konum"] for sehir in city_data], mode="driving")
        if result:
            route = result[0]['legs'][0]['steps']
    
    elif rotasi_tipi == "Önem Derecesi":
        # Önem derecesine göre sıralama
        city_data.sort(key=lambda x: x['onem'], reverse=True)
        route = [baslangic_konum] + [sehir["konum"] for sehir in city_data]

    return route, city_data

# Rota hesapla ve harita oluştur
if st.session_state.baslangic_konum:
    baslangic_konum = st.session_state.baslangic_konum
    # Aktif ekip için şehirleri al
    aktif_ekip = st.session_state.aktif_ekip
    visited_cities = st.session_state.ekipler[aktif_ekip]["visited_cities"]

    # Rota hesapla (en kısa veya önemliye göre)
    route, ordered_cities = calculate_route(visited_cities, baslangic_konum, siralama_tipi)
    
    # Harita oluştur
    harita = folium.Map(location=[baslangic_konum["lat"], baslangic_konum["lng"]], zoom_start=6)

    # Başlangıç noktası ekle
    folium.Marker(
        [baslangic_konum["lat"], baslangic_konum["lng"]],
        popup="Başlangıç Konumu",
        icon=folium.Icon(color="blue", icon="info-sign"),
    ).add_to(harita)

    # Aktif ekip için şehirleri haritada numaralandırarak göster
    for idx, sehir in enumerate(ordered_cities):
        sehir_konum = sehir["konum"]
        folium.Marker(
            [sehir_konum["lat"], sehir_konum["lng"]],
            popup=f"{idx+1}. {sehir['sehir']} (Önem: {sehir['onem']})",
            icon=folium.Icon(color="green", icon="cloud"),
        ).add_to(harita)
    
    # Haritayı Streamlit üzerinden göster
    st_folium(harita, width=700)
else:
    st.warning("Başlangıç noktasını girin ve onaylayın.")
