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
    pdf.cell(200, 10, txt=f"Toplam Mesafe: {round(toplam_km, 1)} km", ln=True)
    pdf.cell(200, 10, txt=f"Toplam Süre: {toplam_sure_td}", ln=True)
    pdf.cell(200, 10, txt=f"Yakıt Maliyeti: {round(toplam_yakit)} TL", ln=True)
    pdf.cell(200, 10, txt=f"İşçilik Maliyeti: {round(toplam_iscilik)} TL", ln=True)
    pdf.cell(200, 10, txt=f"Toplam Maliyet: {round(toplam_maliyet)} TL", ln=True)
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
    pdf_url = f"data:application/pdf;base64,{pdf_base64}"
    return pdf_url

def display_pdf_link(pdf_url):
    st.markdown(f'<a href="{pdf_url}" download="montaj_raporu.pdf">PDF olarak indir</a>', unsafe_allow_html=True)

# Session Init
if "ekipler" not in st.session_state:
    st.session_state.ekipler = {}  # Her ekip: {"members": [...], "visited_cities": [...]}
if "aktif_ekip" not in st.session_state:
    st.session_state.aktif_ekip = None
if "baslangic_konum" not in st.session_state:
    st.session_state.baslangic_konum = None

# ---------------------
# Ekip Yönetimi
# ---------------------
st.sidebar.subheader("👷 Ekip Yönetimi")
ekip_adi = st.sidebar.text_input("Yeni Ekip Adı")
if st.sidebar.button("➕ Ekip Oluştur") and ekip_adi:
    if ekip_adi not in st.session_state.ekipler:
        st.session_state.ekipler[ekip_adi] = {"members": [], "visited_cities": []}
        st.session_state.aktif_ekip = ekip_adi
    else:
        st.sidebar.warning("Bu ekip zaten var.")

if st.session_state.ekipler:
    aktif_secim = st.sidebar.selectbox("Aktif Ekip Seç", list(st.session_state.ekipler.keys()))
    st.session_state.aktif_ekip = aktif_secim

# Ekip Üyeleri Yönetimi (aktif ekip için)
st.sidebar.subheader("Ekip Üyeleri")
if st.session_state.aktif_ekip:
    aktif_ekip = st.session_state.aktif_ekip
    members = st.session_state.ekipler[aktif_ekip]["members"]
    # Üye ekleme
    new_member = st.sidebar.text_input(f"{aktif_ekip} için yeni üye ekleyin", key=f"new_member_{aktif_ekip}")
    if st.sidebar.button(f"➕ {aktif_ekip} Üyesi Ekle"):
        if new_member:
            if new_member not in members:
                members.append(new_member)
                st.sidebar.success(f"{new_member} eklendi.")
            else:
                st.sidebar.warning("Bu üye zaten var.")
    # Üyeleri listele ve her üyenin yanında silme butonu ekle
    if members:
        st.sidebar.markdown("**Üyeler:**")
        for m in members:
            col1, col2 = st.sidebar.columns([0.8, 0.2])
            col1.write(m)
            if col2.button("❌", key=f"remove_{aktif_ekip}_{m}"):
                members.remove(m)
                st.experimental_rerun()
else:
    st.sidebar.info("Lütfen bir ekip oluşturun ve aktif seçin.")

# ---------------------
# Başlangıç Konumu
# ---------------------
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
        except Exception as e:
            st.sidebar.error("API Hatası.")

# ---------------------
# Şehir/Bayi Ekleme
# ---------------------
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

# ---------------------
# Harita ve Rota Oluşturma
# ---------------------
st.subheader("🗺️ Aktif Ekibin Haritası ve Rota")

if st.session_state.baslangic_konum and st.session_state.aktif_ekip:
    baslangic_konum = st.session_state.baslangic_konum
    # Aktif ekibin şehirleri
    visited_cities = st.session_state.ekipler[st.session_state.aktif_ekip]["visited_cities"].copy()
    
    # Rota sıralaması: "Önem Derecesi" veya "En Kısa Rota"
    if siralama_tipi == "Önem Derecesi":
        visited_cities.sort(key=lambda x: x["onem"], reverse=True)
    else:  # En Kısa Rota için basit nearest neighbor algoritması
        rota = []
        current = baslangic_konum
        while visited_cities:
            en_yakin = min(visited_cities, key=lambda x: haversine(
                (current["lat"], current["lng"]), 
                (x["konum"]["lat"], x["konum"]["lng"])
            ))
            rota.append(en_yakin)
            current = en_yakin["konum"]
            visited_cities.remove(en_yakin)
        visited_cities = rota

    # Harita oluşturma
    harita = folium.Map(location=[baslangic_konum["lat"], baslangic_konum["lng"]], zoom_start=6)
    # Başlangıç noktasını ekle
    folium.Marker(
        [baslangic_konum["lat"], baslangic_konum["lng"]],
        popup="Başlangıç Konumu",
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(harita)
    
    # Rota numaralı işaretlemeler ve yol çizgileri
    route_coords = [[baslangic_konum["lat"], baslangic_konum["lng"]]]
    for idx, sehir in enumerate(visited_cities):
        konum = sehir["konum"]
        route_coords.append([konum["lat"], konum["lng"]])
        folium.Marker(
            [konum["lat"], konum["lng"]],
            popup=f"{idx+1}. {sehir['sehir']} (Önem: {sehir['onem']})",
            icon=folium.DivIcon(html=f"""<div style="font-size: 12pt; color : red">{idx+1}</div>""")
        ).add_to(harita)
    
    # Yol çizgisi (polyline) oluştur
    folium.PolyLine(route_coords, color="blue", weight=2.5, opacity=1).add_to(harita)
    
    st_folium(harita, width=700)
else:
    st.warning("Başlangıç noktasını girin ve aktif ekibi seçin.")

# ---------------------
# Excel Raporu Oluşturma (Detaylı)
# ---------------------
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
            row = {
                "Ekip Adı": ekip,
                "Şehir": sehir["sehir"],
                "Montaj Süresi (saat)": sehir["is_suresi"],
                "Önem Derecesi": sehir["onem"],
                "İşçilik Maliyeti (TL)": round(iscik_maliyet, 2),
                "Yol Masrafı (TL)": round(yol_masrafi, 2),
                "Toplam Maliyet (TL)": round(toplam_maliyet, 2),
                "Ekip Üyeleri": ", ".join(details["members"]),
            }
            data.append(row)
    df = pd.DataFrame(data)
   with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name="Montaj Planı")
    worksheet = writer.sheets["Montaj Planı"]

    # Sütun genişliklerini içeriğe göre ayarla
    for column_cells in worksheet.columns:
        max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        adjusted_width = max_length + 2  # Biraz boşluk bırak
        worksheet.column_dimensions[column_cells[0].column_letter].width = adjusted_width


st.download_button(
    label="Excel Olarak İndir",
    data=generate_excel(),
    file_name="montaj_plani.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
