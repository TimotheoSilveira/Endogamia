import streamlit as st
import pandas as pd
from io import StringIO
import requests
from pathlib import Path
import base64

st.set_page_config(page_title="Consulta de Endogamia", page_icon="🐄", layout="wide")

# ─── Logo ─────────────────────────────────────────────────────────────────────
logo_path = Path(__file__).parent / "Logo_Alta_Triangulo.jpg"

def logo_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

if logo_path.exists():
    logo_b64 = logo_base64(logo_path)

    # Cabeçalho com logo + título
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:18px; margin-bottom:8px;">
            <img src="data:image/jpeg;base64,{logo_b64}" style="height:64px;">
            <div>
                <span style="font-size:2rem; font-weight:700; color:#1a3a6b;">Consulta de Endogamia Bovina</span><br>
                <span style="font-size:0.95rem; color:#555;">Alta Genetics — Ferramenta de apoio técnico</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.title("🐄 Consulta de Endogamia Bovina")

st.markdown("---")

# ─── Links publicados do Google Sheets ───────────────────────────────────────
ARQUIVOS = {
    "Holandês": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFznVxvHhq5iX_gfW_KeHqa8GW2u41-0_7CtSrRtY5lFB-V8n7evH3EXcGQK428orZDCRsm4KfcfOI/pub?gid=1768377571&single=true&output=csv",
    "Jersey":   "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEGo8e3USR_jKgQUN3A-Cej-oZTqAI9ji2B693e_nx_76Dd8fL4-RgYCZmRuuaHdVFxGt8Fvf6SgtB/pub?output=csv",
}

@st.cache_data(show_spinner=False, ttl=3600)
def carregar_planilha(url, nome):
    try:
        resp = requests.get(url, timeout=180)
        resp.raise_for_status()
        try:
            texto = resp.content.decode("utf-8")
        except UnicodeDecodeError:
            texto = resp.content.decode("latin-1")

        amostra = texto[:4096]
        sep = ";" if amostra.count(";") > amostra.count(",") else ","
        df = pd.read_csv(StringIO(texto), sep=sep, dtype=str)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar **{nome}**: {e}")
        return None

# ─── Carregamento com barra de progresso ──────────────────────────────────────
dfs = {}
progress = st.progress(0, text="Iniciando carregamento…")
total = len(ARQUIVOS)

for i, (nome, url) in enumerate(ARQUIVOS.items()):
    progress.progress(i / total, text=f"Carregando **{nome}**…")
    df_temp = carregar_planilha(url, nome)
    if df_temp is not None:
        dfs[nome] = df_temp
        progress.progress((i + 1) / total, text=f"✅ {nome} carregado — {len(df_temp):,} linhas")

progress.empty()

if not dfs:
    st.error("Não foi possível carregar nenhuma planilha. Verifique os links do Google Sheets.")
    st.stop()

# ─── Seleção de raça ──────────────────────────────────────────────────────────
raca = st.radio("Selecione a raça:", list(dfs.keys()), horizontal=True)
df = dfs[raca]

# ─── Mapeamento flexível de colunas ──────────────────────────────────────────
import unicodedata

def normalizar(texto):
    """Remove acentos e coloca em minúsculas para comparação."""
    return unicodedata.normalize("NFD", str(texto)).encode("ascii", "ignore").decode().lower().strip()

colunas_esperadas = {
    "pai":      ["touro pai da femea", "touro pai da fzmea"],
    "naab":     ["naab touro alta"],
    "curto":    ["nome curto"],
    "completo": ["nome completo"],
    "inb":      ["inb %", "inb%"],
    "haplo":    ["haplotipos", "haplo tipos"],
}
COL_MAP = {}
for chave, opcoes in colunas_esperadas.items():
    for col_real in df.columns:
        if normalizar(col_real) in opcoes:
            COL_MAP[chave] = col_real
            break

st.markdown("---")
st.subheader(f"Consulta — {raca}")


col1, col2 = st.columns(2)

# ─── Funções de busca ─────────────────────────────────────────────────────────
def sugestoes(col_key, texto):
    coluna = COL_MAP.get(col_key)
    if not coluna or coluna not in df.columns:
        return []
    mask = df[coluna].fillna("").str.lower().str.contains(texto.lower(), na=False)
    return sorted(df.loc[mask, coluna].dropna().unique().tolist())

def buscar_linha(filtros):
    resultado = df.copy()
    for col_key, val in filtros.items():
        coluna = COL_MAP.get(col_key)
        if val and coluna and coluna in resultado.columns:
            resultado = resultado[resultado[coluna].fillna("").str.lower() == val.lower()]
    return resultado

# ─── Touro pai da fêmea ───────────────────────────────────────────────────────
with col1:
    st.markdown("#### 🐮 Touro pai da fêmea")
    pai_texto = st.text_input("Digite o nome ou código:", key="pai_txt")
    pai_selecionado = ""
    if pai_texto:
        opts = sugestoes("pai", pai_texto)
        if opts:
            pai_selecionado = st.selectbox("Selecione:", opts, key="pai_sel")
        else:
            st.caption("Nenhuma sugestão encontrada.")

# ─── Touro para cruzamento ────────────────────────────────────────────────────
with col2:
    st.markdown("#### 🐂 Touro para cruzamento")
    campo_opcoes = {
        "NAAB touro Alta": "naab",
        "Nome curto":      "curto",
        "Nome completo":   "completo",
    }
    campo_label = st.selectbox("Buscar touro por:", list(campo_opcoes.keys()), key="campo_busca")
    campo_key   = campo_opcoes[campo_label]

    touro_texto = st.text_input(f"Digite o {campo_label}:", key="touro_txt")
    touro_selecionado = ""
    if touro_texto:
        opts2 = sugestoes(campo_key, touro_texto)
        if opts2:
            touro_selecionado = st.selectbox("Selecione:", opts2, key="touro_sel")
        else:
            st.caption("Nenhuma sugestão encontrada.")

# ─── Resultado ────────────────────────────────────────────────────────────────
st.markdown("---")

filtros = {}
if pai_selecionado:
    filtros["pai"] = pai_selecionado
if touro_selecionado:
    filtros[campo_key] = touro_selecionado

if filtros:
    resultado = buscar_linha(filtros)

    if resultado.empty:
        st.warning("⚠️ Nenhum resultado encontrado para os filtros selecionados.")
    else:
        st.success(f"✅ {len(resultado)} resultado(s) encontrado(s).")

        for _, row in resultado.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 1, 2])
                with c1:
                    st.markdown(f"**Touro pai da fêmea:**  \n{row.get(COL_MAP.get('pai', ''), '—')}")
                    st.markdown(f"**NAAB touro Alta:**  \n{row.get(COL_MAP.get('naab', ''), '—')}")
                with c2:
                    st.markdown(f"**Nome curto:**  \n{row.get(COL_MAP.get('curto', ''), '—')}")
                    st.markdown(f"**Nome completo:**  \n{row.get(COL_MAP.get('completo', ''), '—')}")
                with c3:
                    inb_col = COL_MAP.get("inb", "")
                    inb_raw = row.get(inb_col, "")
                    inb_str = str(inb_raw).strip().replace(",", ".") if pd.notna(inb_raw) else ""
                    st.metric("INB %", inb_str if inb_str else "—")
                    try:
                        inb_val = float(inb_str)
                        if inb_val > 18:
                            st.error("🔴 Endogamia muito alta!")
                        elif inb_val >= 12:
                            st.warning("🟠 Nível crítico de endogamia!")
                        elif inb_val > 6.25:
                            st.warning("🟡 Avaliar com um técnico")
                        else:
                            st.success("🟢 OK — sem efeitos de endogamia")
                    except (ValueError, TypeError):
                        pass
                with c4:
                    hap_col = COL_MAP.get("haplo", "")
                    hap = row.get(hap_col, "")
                    st.markdown("**Haplótipos:**")
                    if pd.notna(hap) and str(hap).strip():
                        st.error(f"⚠️ {hap}")
                    else:
                        st.success("✅ Nenhum haplótipo identificado")
else:
    st.info("ℹ️ Preencha pelo menos um campo acima para realizar a consulta.")

# ─── Rodapé ───────────────────────────────────────────────────────────────────
st.markdown("---")
if logo_path.exists():
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; opacity:0.7;">
            <img src="data:image/jpeg;base64,{logo_b64}" style="height:36px;">
            <span style="font-size:0.85rem; color:#555;">© Alta Genetics — Todos os direitos reservados</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


