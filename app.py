import streamlit as st
import folium
from streamlit_folium import st_folium
import googlemaps
from math import radians, cos, sin, asin, sqrt
import pandas as pd
from io import BytesIO
import datetime

# Google Maps API anahtarını girin
gmaps = googlemaps.Client(key="AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws")

# Sayfa ayarları
st.set_page_config(page_title="Montaj Rota Planlayıcı", layout="wide")
st.title("🔧 Montaj Rota Planlayıcı Uygulaması")

# Sabitler
SAATLIK_ISCILIK = 500  # TL
yakit_tuketimi_lt_100km = 8  # litre
benzin_fiyati = 43.5  # TL
km_basi_tuketim = yakit_tuketimi_lt_100km / 100

# Haversine fonksiyonu
def haversine(coord1, coord2):
    lon1, lat1 = coord1[1], coord1[0]
    lon2, lat2 = coord2[1], coord2[0]
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

# Oturum durumu başlatma
if "ekipler" not in st.session_state:
    st.session_state.ekipler = {}
if "aktif_ekip" not in st.session_state:
    st.session_state.aktif_ekip = None
if "baslangic_konum" not in st.session_state:
    st.session_state.baslangic_konum = None

# Sidebar - Ekip Tanımlama
st.sidebar.header("👥 Ekip Tanımlama")
aktif = st.sidebar.text_input("Yeni Ekip Adı")
if st.sidebar.button("➕ Ekip Oluştur"):
    if aktif and aktif not in st.session_state.ekipler:
        st.session_state.ekipler[aktif] = {"members": [], "visited_cities": []}
        st.session_state.aktif_ekip = aktif

# Aktif ekip seçimi
if st.session_state.ekipler:
    ekip_sec = st.sidebar.selectbox("Aktif Ekip Seç", list(st.session_state.ekipler.keys()), index=0)
    st.session_state.aktif_ekip = ekip_sec

# Ekip üyeleri
st.sidebar.subheader("Ekip Üyeleri")
yeni_uye = st.sidebar.text_input("Üye Adı")
if st.sidebar.button("👤 Üye Ekle") and yeni_uye:
    st.session_state.ekipler[st.session_state.aktif_ekip]["members"].append(yeni_uye)

# Başlangıç noktası seçimi
st.sidebar.subheader("📍 Başlangıç Noktası")
baslangic = st.sidebar.text_input("Başlangıç Konumu", value="Gebze")
if st.sidebar.button("📌 Konumu Ayarla"):
    sonuc = gmaps.geocode(baslangic)
    if sonuc:
        st.session_state.baslangic_konum = sonuc[0]["geometry"]["location"]
        st.sidebar.success("Konum ayarlandı")
    else:
        st.sidebar.error("Konum bulunamadı")

# Şehir Ekleme
st.subheader("📌 Şehir Ekle")
with st.form("sehir_form"):
    sehir_adi = st.text_input("Şehir / Bayi Adı")
    onem = st.slider("Önem Derecesi", 1, 5, 3)
    is_suresi = st.number_input("Montaj Süre (saat)", 1, 24, 2)
    tarih = st.date_input("Planlanan Tarih", value=datetime.date.today())
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
                "tarih": tarih.strftime("%Y-%m-%d")
            })
            st.success(f"{sehir_adi} eklendi.")
        else:
            st.error("Konum bulunamadı.")

# Harita ve Rota
st.subheader("🗺️ Rota Haritası")
if st.session_state.baslangic_konum and st.session_state.ekipler[st.session_state.aktif_ekip]["visited_cities"]:
    harita = folium.Map(location=[st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]], zoom_start=6)
    folium.Marker([st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]], tooltip="Başlangıç", icon=folium.Icon(color='green')).add_to(harita)
    sirali_sehirler = sorted(st.session_state.ekipler[st.session_state.aktif_ekip]["visited_cities"], key=lambda x: x["onem"], reverse=True)
    toplam_km = 0
    onceki_konum = st.session_state.baslangic_konum
    for i, sehir in enumerate(sirali_sehirler, start=1):
        konum = sehir["konum"]
        folium.Marker([konum["lat"], konum["lng"]], tooltip=f"{i}. {sehir['sehir']}\n({sehir['tarih']})").add_to(harita)
        mesafe = haversine((onceki_konum["lat"], onceki_konum["lng"]), (konum["lat"], konum["lng"]))
        toplam_km += mesafe
        onceki_konum = konum
    st.markdown(f"**Toplam Mesafe:** {round(toplam_km, 2)} km")
    st_folium(harita, width=700, height=500)

# Excel çıktısı oluşturma
st.subheader("📄 Raporlama")
def generate_excel():
    data = []
    for ekip, details in st.session_state.ekipler.items():
        for sehir in details["visited_cities"]:
            yol_masrafi = haversine(
                (st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]),
                (sehir["konum"]["lat"], sehir["konum"]["lng"])
            ) * km_basi_tuketim * benzin_fiyati
            iscik_maliyet = sehir["is_suresi"] * SAATLIK_ISCILIK
            toplam_maliyet = yol_masrafi + iscik_maliyet

            data.append({
                "Ekip Adı": ekip,
                "Şehir": sehir["sehir"],
                "Tarih": sehir.get("tarih", ""),
                "Montaj Süre (saat)": sehir["is_suresi"],
                "Önem Derecesi": sehir["onem"],
                "İŞçilik Maliyeti (TL)": round(iscik_maliyet, 2),
                "Yol Masrafı (TL)": round(yol_masrafi, 2),
                "Toplam Maliyet (TL)": round(toplam_maliyet, 2),
                "Ekip Üyeleri": ", ".join(details["members"]),
            })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Rapor")
    return output.getvalue()

if st.button("📥 Excel Olarak İndir"):
    excel_bytes = generate_excel()
    st.download_button(label="Raporu İndir", data=excel_bytes, file_name="montaj_raporu.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
