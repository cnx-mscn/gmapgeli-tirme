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
from openpyxl.utils import get_column_letter
from PIL import Image

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

# Ekip Yönetimi
st.sidebar.subheader("👷 Ekip Yönetimi")
ekip_adi = st.sidebar.text_input("Yeni Ekip Adı")
if st.sidebar.button("➕ Ekip Oluştur") and ekip_adi:
    if ekip_adi not in st.session_state.ekipler:
        st.session_state.ekipler[ekip_adi] = {"members": [], "visited_cities": []}
        st.session_state.aktif_ekip = ekip_adi

aktif_secim = st.sidebar.selectbox("Aktif Ekip Seç", list(st.session_state.ekipler.keys()))
st.session_state.aktif_ekip = aktif_secim

# Ekip Üyeleri
st.sidebar.subheader("Ekip Üyeleri")
for ekip, details in st.session_state.ekipler.items():
    if ekip == st.session_state.aktif_ekip:
        new_member = st.sidebar.text_input(f"{ekip} için yeni üye ekleyin", key=f"new_member_{ekip}")
        if st.sidebar.button(f"➕ {ekip} Üyesi Ekle"):
            if new_member:
                details["members"].append(new_member)
                st.sidebar.success(f"{new_member} {ekip} ekibine eklendi.")
        for i, uye in enumerate(details["members"]):
            col1, col2 = st.sidebar.columns([4, 1])
            col1.write(uye)
            if col2.button("❌", key=f"remove_{uye}_{i}") :
                details["members"].remove(uye)
                st.experimental_rerun()

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

# İşçi Arayüzü: Şehir Görevleri, Fotoğraf Yükleme
st.subheader("📸 İşçi Görev ve Fotoğraf Yükleme")
aktif_ekip = st.session_state.ekipler.get(st.session_state.aktif_ekip)
if aktif_ekip:
    for sehir in aktif_ekip["visited_cities"]:
        sehir_adi = sehir["sehir"]
        # İşçi görevi için şehir detayları göster
        if st.button(f"✅ {sehir_adi} Görevini Tamamladım"):
            # Fotoğraf yükleme alanı
            uploaded_file = st.file_uploader(f"{sehir_adi} Fotoğraf Yükleyin", type=["jpg", "jpeg", "png"])
            if uploaded_file is not None:
                img = Image.open(uploaded_file)
                st.image(img, caption=f"{sehir_adi} fotoğrafı", use_column_width=True)
                # Yönetici onayı
                if st.button(f"Yönetici Onayı İçin Gönder: {sehir_adi}"):
                    st.session_state.ekipler[st.session_state.aktif_ekip]["visited_cities"] = [
                        {**sehir, "fotoğraf": uploaded_file.name, "onay": False}
                    ]
                    st.success(f"{sehir_adi} için fotoğraf gönderildi. Yöneticinin onayını bekliyor...")

# Yönetici Onayı: Fotoğrafı onayla
st.subheader("🧑‍💼 Yönetici Onayı")
onaylanan_gorevler = []
for ekip, details in st.session_state.ekipler.items():
    for sehir in details["visited_cities"]:
        if "fotoğraf" in sehir and not sehir.get("onay", False):
            onay_btn = st.button(f"Fotoğrafı Onayla: {sehir['sehir']}", key=f"onay_{sehir['sehir']}")
            if onay_btn:
                sehir["onay"] = True
                onaylanan_gorevler.append(sehir['sehir'])
                st.success(f"{sehir['sehir']} görevi onaylandı!")

if onaylanan_gorevler:
    st.write("Onaylanan Şehirler:", ", ".join(onaylanan_gorevler))
    # Sonraki şehire yönlendirme
    for sehir in onaylanan_gorevler:
        st.write(f"Yönlendirme: {sehir} sonrası bir sonraki şehire gidiniz.")

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

# Excel ve PDF Çıktısı
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
                "Montaj Süre (saat)": sehir["is_suresi"],
                "Önem Derecesi": sehir["onem"],
                "İşçilik Maliyeti (TL)": round(iscik_maliyet, 2),
                "Yol Masrafı (TL)": round(yol_masrafi, 2),
                "Toplam Maliyet (TL)": round(toplam_maliyet, 2),
                "Ekip Üyeleri": ", ".join(details["members"]),
            })

    df = pd.DataFrame(data)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Montaj Planı")
        worksheet = writer.sheets["Montaj Planı"]
        for i, col in enumerate(df.columns, 1):
            max_len = max(df[col].astype(str).map(len).max(), len(col))
            worksheet.column_dimensions[get_column_letter(i)].width = max_len + 5
    excel_buffer.seek(0)
    return excel_buffer

# Excel Raporu
st.download_button(
    label="Excel Olarak İndir",
    data=generate_excel(),
    file_name="montaj_plani.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
