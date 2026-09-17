from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import re

import pandas as pd
import streamlit as st


st.set_page_config(page_title="SIRENA MI3", page_icon="📰", layout="wide")

SECTORS = {
    "Mining & Energy": {
        "query": '(pertambangan OR batubara OR nikel OR mineral OR energi OR RKAB OR royalti) Indonesia',
        "businesses": "Pemilik tambang, kontraktor tambang, hauling, smelter, dan penyedia alat berat",
    },
    "Oil & Gas": {
        "query": '(migas OR minyak bumi OR gas bumi OR lifting OR offshore OR onshore OR SKK Migas) Indonesia',
        "businesses": "Produsen migas, kontraktor migas, operator offshore/onshore, dan jasa penunjang",
    },
    "Construction": {
        "query": '(konstruksi OR kontraktor sipil OR proyek infrastruktur OR APBN OR APBD OR jalan tol) Indonesia',
        "businesses": "Kontraktor sipil, EPC, kontraktor pemerintah, dan pemasok material",
    },
    "Property": {
        "query": '(properti OR developer OR presales OR perumahan OR apartemen OR pusat perbelanjaan) Indonesia',
        "businesses": "Developer residensial, kawasan industri, apartemen, dan pusat perbelanjaan",
    },
    "Hotel": {
        "query": '(hotel OR perhotelan OR okupansi OR ADR OR RevPAR OR pariwisata) Indonesia',
        "businesses": "Pemilik hotel, operator hotel, dan usaha terkait pariwisata",
    },
}

RISK_RULES = [
    {
        "theme": "Legal dan kepailitan",
        "keywords": ["pailit", "kepailitan", "pkpu", "gugatan", "korupsi", "sanksi"],
        "materiality": 25,
        "impact": "Tinjau kelangsungan usaha, reputasi, legalitas, dan kemampuan memenuhi kewajiban.",
    },
    {
        "theme": "Operasional",
        "keywords": ["penghentian operasi", "kecelakaan", "ledakan", "longsor", "banjir", "kebakaran", "gangguan produksi"],
        "materiality": 25,
        "impact": "Tinjau volume produksi, utilisasi, biaya operasional, asuransi, dan arus kas.",
    },
    {
        "theme": "Kinerja keuangan",
        "keywords": ["gagal bayar", "default", "rugi bersih", "penurunan laba", "utang meningkat", "restrukturisasi utang", "penurunan rating"],
        "materiality": 25,
        "impact": "Tinjau profitabilitas, leverage, likuiditas, dan kemampuan membayar kewajiban.",
    },
    {
        "theme": "Regulasi",
        "keywords": ["rkab", "royalti", "larangan ekspor", "dmo", "izin dicabut", "regulasi baru", "kuota produksi"],
        "materiality": 20,
        "impact": "Tinjau izin usaha, volume, biaya, dan proyeksi pendapatan.",
    },
    {
        "theme": "Kontrak dan proyek",
        "keywords": ["pemutusan kontrak", "kontrak baru", "proyek baru", "tender", "order book", "perpanjangan kontrak"],
        "materiality": 20,
        "impact": "Tinjau order book, kepastian pendapatan, modal kerja, dan konsentrasi pelanggan.",
    },
    {
        "theme": "Harga dan pasar",
        "keywords": ["harga batubara", "harga batu bara", "harga minyak", "harga gas", "harga nikel", "permintaan melemah", "harga turun"],
        "materiality": 15,
        "impact": "Tinjau harga jual, margin, volume, dan sensitivitas proyeksi keuangan.",
    },
]

def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", value.lower()).strip()


def parse_date(raw):
    try:
        value = parsedate_to_datetime(raw)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    except Exception:
        return None


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_rss(query, limit=30):
    url = (
        "https://news.google.com/rss/search?q=" + quote_plus(query)
        + "&hl=id&gl=ID&ceid=ID:id"
    )
    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 SIRENA-MI3/1.0"},
    )
    with urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())

    rows = []
    for entry in root.findall(".//item")[:limit]:
        def value(tag):
            element = entry.find(tag)
            return element.text.strip() if element is not None and element.text else ""

        rows.append({
            "Judul": value("title"),
            "Ringkasan": value("description"),
            "URL": value("link"),
            "Tanggal": parse_date(value("pubDate")),
            "Sumber": value("source"),
        })
    return rows


def analyze_article(article, sector):
    text = clean_text(article["Judul"] + " " + article["Ringkasan"])
    selected = {
        "theme": "Informasi umum",
        "materiality": 5,
        "impact": "Baca dan validasi sumber sebelum menggunakan informasi dalam analisis kredit.",
        "matches": [],
    }

    for rule in RISK_RULES:
        matches = [keyword for keyword in rule["keywords"] if keyword in text]
        if matches and rule["materiality"] > selected["materiality"]:
            selected = {**rule, "matches": matches}

    return {
        **article,
        "Sektor": sector,
        "Jenis usaha yang perlu ditinjau": SECTORS[sector]["businesses"],
        "Tema risiko": selected["theme"],
        "Indikasi dampak": selected["impact"],
        "Kata kunci": ", ".join(selected["matches"]),
    }


def collect_news(sector, limit):
    selected_sectors = list(SECTORS) if sector == "Semua sektor" else [sector]
    articles = []
    for item in selected_sectors:
        for article in fetch_rss(SECTORS[item]["query"], limit):
            articles.append(analyze_article(article, item))

    unique = {}
    for article in articles:
        unique[article["URL"] or article["Judul"]] = article
    return list(unique.values())


st.markdown(
    """
    <style>
    .hero {background:linear-gradient(90deg,#073b74,#1260a5);padding:28px 32px;
    border-radius:0 0 22px 22px;color:white;margin-bottom:22px}
    .hero h1{margin:0;font-size:38px}.hero p{margin:8px 0 0;color:#e7f0fa}
    </style>
    <div class="hero"><h1>SIRENA MI3</h1>
    <p>Monitoring berita sektoral dan indikasi dampak kredit</p></div>
    """,
    unsafe_allow_html=True,
)

tab_news, tab_method = st.tabs(["Monitoring Berita", "Metodologi"])

with tab_news:
    col1, col2 = st.columns([2, 1])
    with col1:
        sector = st.selectbox("Sektor", ["Semua sektor", *SECTORS.keys()])
    with col2:
        period = st.selectbox("Jumlah berita per sektor", [10, 20, 30, 50], index=1)
    if st.button("Perbarui berita", type="primary", use_container_width=True):
        with st.spinner("Mengambil berita publik terbaru..."):
            data = pd.DataFrame(collect_news(sector, period))

        if data.empty:
            st.warning("Berita belum ditemukan atau sumber tidak dapat diakses.")
        else:
            data = data.sort_values("Tanggal", ascending=False, na_position="last")

            m1, m2, m3 = st.columns(3)
            m1.metric("Berita ditemukan", len(data))
            m2.metric("Sektor dipantau", int(data["Sektor"].nunique()))
            m3.metric("Tema teridentifikasi", int(data["Tema risiko"].nunique()))

            for _, row in data.iterrows():
                with st.container(border=True):
                    st.markdown(f"### [{row['Judul']}]({row['URL']})")
                    c1, c2 = st.columns(2)
                    c1.write(f"**Sektor:** {row['Sektor']}")
                    c2.write(f"**Tema:** {row['Tema risiko']}")
                    st.write(f"**Jenis usaha yang perlu ditinjau:** {row['Jenis usaha yang perlu ditinjau']}")
                    st.write(f"**Indikasi dampak:** {row['Indikasi dampak']}")
                    date_text = row["Tanggal"].strftime("%d-%m-%Y") if pd.notna(row["Tanggal"]) else "Tanggal tidak tersedia"
                    st.caption(f"{row['Sumber'] or 'Sumber tidak tersedia'} | {date_text}")

            export_cols = [
                "Judul", "Tanggal", "Sumber", "URL", "Sektor",
                "Jenis usaha yang perlu ditinjau", "Tema risiko",
                "Indikasi dampak",
            ]
            csv = data[export_cols].to_csv(index=False).encode("utf-8-sig")
            st.download_button("Unduh hasil ke CSV", csv, "monitoring_berita_MI3.csv", "text/csv")
    else:
        st.info("Pilih sektor lalu tekan Perbarui berita.")

with tab_method:
    st.subheader("Cara kerja klasifikasi")
    st.dataframe(
        pd.DataFrame({
            "Tahap": ["Pengambilan berita", "Klasifikasi sektor", "Identifikasi tema", "Review CRM"],
            "Proses": [
                "Mengambil berita publik melalui RSS",
                "Mencocokkan berita dengan kata kunci sektor MI3",
                "Mengelompokkan isu regulasi, operasional, pasar, kontrak, keuangan, atau legal",
                "CRM membuka tautan dan memvalidasi dampaknya terhadap debitur",
            ],
        }),
        hide_index=True,
        use_container_width=True,
    )
    st.info(
        "Semua berita ditampilkan berdasarkan tanggal terbaru. Indikasi dampak berasal dari aturan kata kunci. "
        "CRM tetap membuka sumber dan memvalidasi informasi sebelum menggunakannya dalam analisis kredit."
    )
