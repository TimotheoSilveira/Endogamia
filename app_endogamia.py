import streamlit as st
import pandas as pd
import requests
import re
from io import StringIO

st.set_page_config(page_title="Consulta de Endogamia", page_icon="🐄", layout="wide")

st.title("🐄 Consulta de Endogamia Bovina")
st.markdown("---")

# ─── IDs dos arquivos no Google Drive ─────────────────────────────────────────
ARQUIVOS = {
    "Holandês": "1DavabVaootf8pZ1TRawI8b7U8Z1NTpwh",
    "Jersey":   "1dcdzqFsTbwyjR6RWrnFZabUJInw6PUA3",
}

# ─── Download robusto (lida com aviso de vírus do Drive para arquivos grandes) ─
@st.cache_data(show_spinner=False)
def carregar_csv(file_id, nome):
    session = requests.Session()

    # 1ª tentativa — link direto via usercontent (mais confiável para CSVs grandes)
    urls_tentativa = [
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
        f"https://drive.google.com/uc?export=download&id={file_id}",
    ]

    content = None
    for url in urls_tentativa:
        try:
            resp = session.get(url, timeout=180)
            resp.raise_for_status()

            # Se retornou HTML (página de confirmação), extrai o token e tenta de novo
            ctype = resp.headers.get("Content-Type", "")
            if "text/html" in ctype:
                token_match = re.search(r'confirm=([^&"]+)', resp.text)
                uuid_match  = re.search(r'uuid=([^&"]+)', resp.text)
                if token_match:
                    confirm_url = (
                        f"https://drive.usercontent.google.com/download"
                        f"?id={file_id}&export=download"
                        f"&confirm={token_match.group(1)}"
                        + (f"&uuid={uuid_match.group(1)}" if uuid_match else "")
                    )
                    resp = session.get(confirm_url, timeout=180)
                    resp.raise_for_status()

            # Verifica se agora temos dados reais
            if len(resp.content) > 1000 and b"<!DOCTYPE" not in resp.content[:100]:
                content = resp.content
                break

        except Exception:
            continue

    if content is None:
        st.error(f"❌ Não foi possível baixar a planilha **{nome}**. "
                 "Verifique se o arquivo está público no Google Drive.")
        return None

    # Decodifica e detecta separador
    try:
        texto = content.decode("utf-8")
    except UnicodeDecodeError:
        texto = content.decode("latin-1")

    amostra = texto[:4096]
    sep = ";" if amostra.count(";") > amostra.count(",") else ","

    try:
        df = pd.read_csv(StringIO(texto), sep=sep, dtype=str)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Erro ao interpretar o CSV de **{nome}**: {e}")
        return None

# ─── Carregamento com barra de progresso ──────────────────────────────────────
dfs = {}
progress = st.progress(0, text="Iniciando carregamento…")

for i, (nome, fid) in enumerate(ARQUIVOS.items()):
    progress.progress((i) / len(ARQUIVOS), text=f"Carregando planilha **{nome}**…")
    df_temp = carregar_csv(fid, nome)
    if df_temp is not None:
        dfs[nome] = df_temp
    progress.progress((i + 1) / len(ARQUIVOS), text=f"✅ {nome} carregado ({len(df_temp):,} linhas)" if df_temp is not None else f"❌ Falha em {nome}")

progress.empty()

if not dfs:
    st.error("Não foi possível carregar nenhuma planilha.")
    st.stop()

# ─── DEBUG: mostra colunas encontradas (remover após confirmar que funciona) ──
with st.expander("🔍 Diagnóstico — colunas encontradas nas planilhas"):
    for nome, df_d in dfs.items():
        st.write(f"**{nome}** ({len(df_d):,} linhas) — Colunas: {list(df_d.columns)}")

# ─── Seleção de raça ──────────────────────────────────────────────────────────
raca = st.radio("Selecione a raça:", list(dfs.keys()), horizontal=True)
df = dfs[raca]

# Mapeamento flexível de colunas (caso haja pequenas diferenças de nome)
COL_MAP = {}
colunas_esperadas = {
    "pai":       ["Touro pai da fêmea", "Touro pai da femea", "touro pai da fêmea"],
    "naab":      ["NAAB touro Alta", "NAAB Touro Alta", "naab touro alta"],
    "curto":     ["Nome curto", "nome curto"],
    "completo":  ["Nome completo", "nome completo"],
    "inb":       ["INB %", "INB%", "inb %"],
    "haplo":     ["Haplótipos", "Haplotipos", "haplótipos"],
}
for chave, opcoes in colunas_esperadas.items():
    for op in opcoes:
        if op in df.columns:
            COL_MAP[chave] = op
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
                    inb = row.get(inb_col, "—")
                    st.metric("INB %", inb if pd.notna(inb) and str(inb).strip() else "—")
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

# ─── Prévia da planilha ───────────────────────────────────────────────────────
with st.expander("📋 Visualizar amostra da planilha carregada"):
    st.dataframe(df.head(50), use_container_width=True)
