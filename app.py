import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from datetime import timedelta
from haversine import haversine

# API
gmaps = googlemaps.Client(key="AIzaSyDwQVuPcON3rGSibcBrwhxQvz4HLTpF9Ws")

st.set_page_config("Montaj Rota Planlayıcı", layout="wide")
st.title("🛠️ Montaj Rota Planlayıcı (v2.0)")

# Sabitler / Ayarlar
SAATLIK_ISCILIK = st.sidebar.number_input("💸 Saatlik İşçilik Ücreti (TL)", 100, 5000, 500, step=50)
benzin_fiyati = st.sidebar.number_input("⛽ Benzin Fiyatı (TL/L)", 0.1, 50.0, 10.0, step=0.1)
km_basi_tuketim = st.sidebar.number_input("🚗 Km Başına Tüketim (L/km)", 0.01, 1.0, 0.1, step=0.01)
siralama_tipi = st.sidebar.radio("📍 Rota Sıralama Tipi", ["Önem Derecesi", "En Kısa Rota"])

# Session init
if "ekipler" not in st.session_state:
    st.session_state.ekipler = {}
if "aktif_ekip" not in st.session_state:
    st.session_state.aktif_ekip = None

# Ekip oluştur
st.sidebar.subheader("👷 Ekip Yönetimi")
ekip_adi = st.sidebar.text_input("Yeni Ekip Adı")
if st.sidebar.button("➕ Ekip Oluştur") and ekip_adi:
    if ekip_adi not in st.session_state.ekipler:
        st.session_state.ekipler[ekip_adi] = {
            "members": [],
            "baslangic": None,
            "sehirler": []
        }
        st.session_state.aktif_ekip = ekip_adi

ekipler_list = list(st.session_state.ekipler.keys())
if ekipler_list:
    aktif = st.sidebar.selectbox("Aktif Ekip Seç", ekipler_list)
    st.session_state.aktif_ekip = aktif
else:
    st.info("Lütfen önce bir ekip oluşturun.")

aktif_ekip = st.session_state.aktif_ekip

# Ekip detayları
if aktif_ekip:
    ekip_data = st.session_state.ekipler[aktif_ekip]

    # Başlangıç noktası
    st.sidebar.subheader("📍 Başlangıç Noktası")
    if not ekip_data["baslangic"]:
        adres_input = st.sidebar.text_input("Adres Gir (Sadece 1 kez girilir)")
        if st.sidebar.button("✅ Adres Onayla") and adres_input:
            try:
                sonuc = gmaps.geocode(adres_input)
                if sonuc:
                    ekip_data["baslangic"] = sonuc[0]["geometry"]["location"]
                    st.sidebar.success("Başlangıç noktası belirlendi.")
                else:
                    st.sidebar.error("Adres bulunamadı.")
            except:
                st.sidebar.error("API hatası.")

    # Üye ekleme
    with st.sidebar.expander("👤 Ekip Üyeleri"):
        uye = st.text_input("Yeni Üye Adı")
        if st.button("✅ Üye Ekle") and uye:
            ekip_data["members"].append(uye)
        for u in ekip_data["members"]:
            st.markdown(f"- {u}")

    # Şehir Ekleme
    st.subheader(f"📌 {aktif_ekip} için Şehir / Bayi Girişi")
    with st.form("sehir_form"):
        sehir_adi = st.text_input("Şehir / Bayi Adı")
        onem = st.slider("Önem Derecesi", 1, 5, 3)
        is_suresi = st.number_input("Montaj Süresi (saat)", 1, 24, 2)
        ekle_btn = st.form_submit_button("➕ Şehri Ekle")

        if ekle_btn and sehir_adi:
            sonuc = gmaps.geocode(sehir_adi)
            if sonuc:
                konum = sonuc[0]["geometry"]["location"]
                ekip_data["sehirler"].append({
                    "sehir": sehir_adi,
                    "konum": konum,
                    "onem": onem,
                    "is_suresi": is_suresi
                })
                st.success(f"{sehir_adi} eklendi.")
            else:
                st.error("Şehir/Bayi bulunamadı.")

    # Şehir listesi ve silme
    st.subheader("📄 Eklenen Şehirler")
    for i, s in enumerate(ekip_data["sehirler"]):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"- **{s['sehir']}** | Önem: {s['onem']} | Süre: {s['is_suresi']} saat")
        with col2:
            if st.button("🗑️ Sil", key=f"sil_{i}"):
                ekip_data["sehirler"].pop(i)
                st.experimental_rerun()

    # Rota Hesaplama
    if ekip_data["baslangic"] and ekip_data["sehirler"]:
        st.subheader("🧭 Rota ve Maliyet Hesaplama")
        sehirler = ekip_data["sehirler"].copy()

        if siralama_tipi == "Önem Derecesi":
            sehirler.sort(key=lambda x: x["onem"], reverse=True)
        else:
            rota = []
            current = ekip_data["baslangic"]
            while sehirler:
                en_yakin = min(sehirler, key=lambda x: haversine(
                    (current["lat"], current["lng"]),
                    (x["konum"]["lat"], x["konum"]["lng"])
                ))
                rota.append(en_yakin)
                current = en_yakin["konum"]
                sehirler.remove(en_yakin)
            sehirler = rota

        harita = folium.Map(location=[ekip_data["baslangic"]["lat"], ekip_data["baslangic"]["lng"]], zoom_start=6)
        toplam_km = toplam_sure = toplam_iscilik = toplam_yakit = toplam_maliyet = 0
        konumlar = [ekip_data["baslangic"]] + [s["konum"] for s in sehirler]

        for i in range(len(konumlar) - 1):
            yol = gmaps.directions(
                (konumlar[i]["lat"], konumlar[i]["lng"]),
                (konumlar[i+1]["lat"], konumlar[i+1]["lng"]),
                mode="driving"
            )
            if yol:
                km = yol[0]["legs"][0]["distance"]["value"] / 1000
                sure_dk = yol[0]["legs"][0]["duration"]["value"] / 60
                montaj_saat = sehirler[i]["is_suresi"]

                toplam_km += km
                toplam_sure += sure_dk + montaj_saat * 60
                iscilik = montaj_saat * SAATLIK_ISCILIK
                yakit = km * km_basi_tuketim * benzin_fiyati
                toplam_iscilik += iscilik
                toplam_yakit += yakit
                toplam_maliyet += iscilik + yakit

                folium.Marker(
                    location=[konumlar[i+1]["lat"], konumlar[i+1]["lng"]],
                    popup=f"{i+1}. {sehirler[i]['sehir']}<br>İşçilik: {round(iscilik)} TL<br>Yakıt: {round(yakit)} TL",
                    tooltip=f"{round(km)} km, {round(sure_dk)} dk"
                ).add_to(harita)

        st_folium(harita, width=1000, height=600)

        st.markdown("---")
        st.subheader("📊 Özet")
        st.markdown(f"- **Toplam Mesafe:** {round(toplam_km)} km")
        st.markdown(f"- **Toplam Süre:** {timedelta(minutes=toplam_sure)}")
        st.markdown(f"- **Yakıt Maliyeti:** {round(toplam_yakit)} TL")
        st.markdown(f"- **İşçilik Maliyeti:** {round(toplam_iscilik)} TL")
        st.markdown(f"- **Toplam Maliyet:** {round(toplam_maliyet)} TL")

    elif not ekip_data["sehirler"]:
        st.info("Lütfen en az 1 şehir girin.")
    elif not ekip_data["baslangic"]:
        st.info("Lütfen başlangıç noktası belirleyin.")
