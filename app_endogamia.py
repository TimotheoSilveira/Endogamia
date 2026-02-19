import streamlit as st
import pandas as pd
import requests
from io import StringIO

st.set_page_config(page_title="Consulta de Endogamia", page_icon="🐄", layout="wide")

st.title("🐄 Consulta de Endogamia Bovina")
st.markdown("---")

# ─── IDs dos arquivos no Google Drive ─────────────────────────────────────────
ARQUIVOS = {
    "Holandês": "1DavabVaootf8pZ1TRawI8b7U8Z1NTpwh",
    "Jersey":   "1dcdzqFsTbwyjR6RWrnFZabUJInw6PUA3",
}

def url_download(file_id):
    return f"https://drive.google.com/uc?export=download&id={file_id}"

@st.cache_data(show_spinner="Carregando planilha…")
def carregar_csv(file_id, nome):
    try:
        url = url_download(file_id)
        response = requests.get(url, timeout=120)
        response.raise_for_status()

        # Tenta detectar separador automaticamente (vírgula ou ponto e vírgula)
        amostra = response.content[:4096].decode("utf-8", errors="ignore")
        sep = ";" if amostra.count(";") > amostra.count(",") else ","

        df = pd.read_csv(
            StringIO(response.content.decode("utf-8", errors="ignore")),
            sep=sep,
            dtype=str,
        )
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao carregar {nome}: {e}")
        return None

# ─── Carregamento automático ──────────────────────────────────────────────────
with st.spinner("Carregando planilhas do Google Drive…"):
    dfs = {}
    for nome, fid in ARQUIVOS.items():
        df_temp = carregar_csv(fid, nome)
        if df_temp is not None:
            dfs[nome] = df_temp

if not dfs:
    st.error("Não foi possível carregar nenhuma planilha. Verifique se os arquivos no Google Drive estão públicos.")
    st.stop()

# ─── Seleção de raça ──────────────────────────────────────────────────────────
racas_disponiveis = list(dfs.keys())
raca = st.radio("Selecione a raça:", racas_disponiveis, horizontal=True)
df = dfs[raca]

st.markdown("---")
st.subheader(f"Consulta — {raca}")

col1, col2 = st.columns(2)

# ─── Funções de busca ─────────────────────────────────────────────────────────
def sugestoes(coluna, texto):
    if coluna not in df.columns:
        return []
    mask = df[coluna].fillna("").str.lower().str.contains(texto.lower(), na=False)
    return sorted(df.loc[mask, coluna].dropna().unique().tolist())

def buscar_linha(filtros):
    resultado = df.copy()
    for col, val in filtros.items():
        if val and col in resultado.columns:
            resultado = resultado[resultado[col].fillna("").str.lower() == val.lower()]
    return resultado

# ─── Touro pai da fêmea ───────────────────────────────────────────────────────
with col1:
    st.markdown("#### 🐮 Touro pai da fêmea")
    pai_texto = st.text_input("Digite o nome ou código:", key="pai_txt")
    pai_selecionado = ""
    if pai_texto:
        opts = sugestoes("Touro pai da fêmea", pai_texto)
        if opts:
            pai_selecionado = st.selectbox("Selecione:", opts, key="pai_sel")
        else:
            st.caption("Nenhuma sugestão encontrada.")

# ─── Touro para cruzamento ────────────────────────────────────────────────────
with col2:
    st.markdown("#### 🐂 Touro para cruzamento")
    campo_busca = st.selectbox(
        "Buscar touro por:",
        ["NAAB touro Alta", "Nome curto", "Nome completo"],
        key="campo_busca"
    )
    touro_texto = st.text_input(f"Digite o {campo_busca}:", key="touro_txt")
    touro_selecionado = ""
    if touro_texto:
        opts2 = sugestoes(campo_busca, touro_texto)
        if opts2:
            touro_selecionado = st.selectbox("Selecione:", opts2, key="touro_sel")
        else:
            st.caption("Nenhuma sugestão encontrada.")

# ─── Resultado ────────────────────────────────────────────────────────────────
st.markdown("---")

filtros = {}
if pai_selecionado:
    filtros["Touro pai da fêmea"] = pai_selecionado
if touro_selecionado:
    filtros[campo_busca] = touro_selecionado

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
                    st.markdown(f"**Touro pai da fêmea:**  \n{row.get('Touro pai da fêmea', '—')}")
                    st.markdown(f"**NAAB touro Alta:**  \n{row.get('NAAB touro Alta', '—')}")
                with c2:
                    st.markdown(f"**Nome curto:**  \n{row.get('Nome curto', '—')}")
                    st.markdown(f"**Nome completo:**  \n{row.get('Nome completo', '—')}")
                with c3:
                    inb = row.get("INB %", "—")
                    st.metric("INB %", inb if pd.notna(inb) and str(inb).strip() else "—")
                with c4:
                    hap = row.get("Haplótipos", "")
                    st.markdown("**Haplótipos:**")
                    if pd.notna(hap) and str(hap).strip():
                        st.error(f"⚠️ {hap}")
                    else:
                        st.success("✅ Nenhum haplótipo identificado")
else:
    st.info("ℹ️ Preencha pelo menos um campo acima para realizar a consulta.")

# ─── Prévia da planilha ───────────────────────────────────────────────────────
with st.expander("📋 Visualizar amostra da planilha carregada"):
    st.dataframe(df.head(50), use_container_width=True)
