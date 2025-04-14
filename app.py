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
gmaps = googlemaps.Client(key=AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws)

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
if st.session_state.baslangic_konum and aktif_ekip:
    cities = st.session_state.ekipler[aktif_ekip]["visited_cities"]
    if cities:
        if siralama_tipi == "Önem Derecesi":
            cities = sorted(cities, key=lambda x: -x["onem"])
        else:
            cities = sorted(cities, key=lambda x: haversine(
                (st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]),
                (x["konum"]["lat"], x["konum"]["lng"])))

        rota = [
            (st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"])
        ] + [(s["konum"]["lat"], s["konum"]["lng"]) for s in cities]

        harita = folium.Map(location=rota[0], zoom_start=6)

        for i, (lat, lng) in enumerate(rota):
            label = "Başlangıç" if i == 0 else f"{i}. {cities[i-1]['sehir']}"
            folium.Marker([lat, lng], tooltip=label, icon=folium.Icon(color="green" if i else "blue"))\
                .add_to(harita)

        folium.PolyLine(rota, color="red").add_to(harita)
        st_folium(harita, width=700)

# Excel raporu
st.subheader("📄 Excel Raporu")
def generate_excel():
    rows = []
    for ekip, details in st.session_state.ekipler.items():
        for sehir in details["visited_cities"]:
            mesafe_km = haversine(
                (st.session_state.baslangic_konum["lat"], st.session_state.baslangic_konum["lng"]),
                (sehir["konum"]["lat"], sehir["konum"]["lng"])
            )
            yakit = mesafe_km * km_basi_tuketim * benzin_fiyati
            iscilik = sehir["is_suresi"] * SAATLIK_ISCILIK
            toplam = yakit + iscilik

            rows.append({
                "Ekip Adı": ekip,
                "Şehir": sehir["sehir"],
                "Tarih": sehir["tarih"].strftime("%Y-%m-%d"),
                "Montaj Süresi (saat)": sehir["is_suresi"],
                "Önem Derecesi": sehir["onem"],
                "İşçilik Maliyeti (TL)": round(iscilik),
                "Yol Masrafı (TL)": round(yakit),
                "Toplam Maliyet (TL)": round(toplam),
                "Ekip Üyeleri": ", ".join(details["members"])
            })

    df = pd.DataFrame(rows)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Montaj Planı")
        worksheet = writer.sheets["Montaj Planı"]
        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value)) for cell in column_cells)
            col_letter = get_column_letter(column_cells[0].column)
            worksheet.column_dimensions[col_letter].width = max_length + 2

    excel_buffer.seek(0)
    return excel_buffer

st.download_button(
    label="📥 Excel Olarak İndir",
    data=generate_excel(),
    file_name="montaj_plani.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Takvimli Görev Tablosu
st.subheader("📅 Takvimli Görev Listesi")
if aktif_ekip:
    df_plan = pd.DataFrame(st.session_state.ekipler[aktif_ekip]["visited_cities"])
    if not df_plan.empty:
        df_plan = df_plan.sort_values("tarih")
        df_plan = df_plan[["sehir", "tarih", "onem", "is_suresi"]]
        st.dataframe(df_plan.rename(columns={
            "sehir": "Şehir",
            "tarih": "Tarih",
            "onem": "Önem",
            "is_suresi": "Montaj Süresi (saat)"
        }))
