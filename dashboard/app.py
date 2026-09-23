"""Painel analitico do Nascente Brasil, consumindo exclusivamente a API."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


API = os.environ.get("NASCENTE_API_URL", "http://127.0.0.1:8000")
GEOJSON_PATH = Path(__file__).parent / "assets" / "brazil_states.geojson"
UF_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}
UF_GEOCODES = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
    "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
    "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53",
}

st.set_page_config(page_title="Nascente Brasil", layout="wide")
st.markdown("""
<style>
:root { --ink:#182326; --muted:#5c6b6d; --line:#dce3e2; --green:#006b5e; }
.stApp { background:#f7f9f8; color:var(--ink); }
[data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:6px; padding:14px; }
h1,h2,h3 { color:var(--ink); letter-spacing:0; } h1 { font-size:2rem; }
div[data-baseweb="select"] > div { border-radius:5px; }
.status { color:var(--green); font-weight:700; }
.note { color:var(--muted); font-size:.88rem; border-left:3px solid #d9a441; padding-left:10px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def api_page(endpoint: str, params: tuple[tuple[str, str | int], ...] = ()) -> dict:
    response = requests.get(f"{API}{endpoint}", params=dict(params), timeout=20)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=300, show_spinner=False)
def api_all(endpoint: str, params: tuple[tuple[str, str | int], ...]) -> pd.DataFrame:
    base, rows, offset = dict(params), [], 0
    while True:
        payload = api_page(endpoint, tuple(sorted((base | {"limit": 500, "offset": offset}).items())))
        rows.extend(payload["items"])
        offset += len(payload["items"])
        if offset >= payload["pagination"]["total"] or not payload["items"]:
            return pd.DataFrame(rows)


@st.cache_resource(show_spinner=False)
def state_geojson() -> dict:
    with GEOJSON_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def pct(value: float | int | None) -> str:
    return "-" if value is None else f"{float(value):,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def number(value: float | int | None) -> str:
    return "-" if value is None else f"{int(value):,}".replace(",", ".")


def bar(data: pd.DataFrame, x: str, y: str, title: str, color: str = "#006B5E") -> None:
    fig = px.bar(data, x=x, y=y, title=title, color_discrete_sequence=[color], text_auto=".3s")
    fig.update_layout(height=410, margin=dict(l=10, r=10, t=55, b=10), paper_bgcolor="#fff",
                      plot_bgcolor="#fff", xaxis_title=None, yaxis_title=None, font=dict(color="#182326"))
    fig.update_traces(marker_line_width=0, hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>")
    st.plotly_chart(fig, width="stretch")


try:
    api_page("/health")
except requests.RequestException:
    st.error("API analítica indisponível.")
    st.stop()

with st.sidebar:
    st.title("NASCENTE BRASIL")
    st.caption("Dados materno-infantis | 2024")
    page = st.radio("Área", ["Visão geral", "Nascimentos", "Parto e pré-natal", "Recém-nascidos",
                              "Saúde materna", "Mortalidade", "Comparação e mapa", "Qualidade dos dados"])
    st.markdown('<p class="status">API e banco operacionais</p>', unsafe_allow_html=True)

births_br = api_all("/api/v1/nascimentos", (("nivel", "brasil"),)).iloc[0]
deaths_br = api_all("/api/v1/mortalidade", (("nivel", "brasil"),)).iloc[0]

if page == "Visão geral":
    st.title("Visão geral")
    cols = st.columns(4)
    cols[0].metric("Nascidos vivos", number(births_br.nascidos_vivos))
    cols[1].metric("Cesáreas", pct(births_br.percentual_cesareas))
    cols[2].metric("Prematuridade", pct(births_br.percentual_prematuridade))
    cols[3].metric("Mortalidade infantil", f"{float(deaths_br.taxa_observada_mortalidade_infantil_por_mil_nv):.2f} por mil")
    regions = api_all("/api/v1/nascimentos", (("nivel", "regiao"),))
    left, right = st.columns(2)
    with left: bar(regions, "territorio", "nascidos_vivos", "Nascidos vivos por região")
    with right: bar(regions, "territorio", "percentual_prematuridade", "Prematuridade por região", "#C94B40")
    st.markdown('<p class="note">Indicadores observados em registros administrativos. Taxas de mortalidade não substituem estimativas oficiais corrigidas.</p>', unsafe_allow_html=True)

elif page == "Nascimentos":
    st.title("Nascimentos")
    level = st.segmented_control("Nível", ["regiao", "estado"], default="regiao")
    data = api_all("/api/v1/nascimentos", (("nivel", level),))
    cols = st.columns(3)
    cols[0].metric("Brasil", number(births_br.nascidos_vivos))
    cols[1].metric("Mães adolescentes", number(births_br.nascidos_vivos_maes_adolescentes))
    cols[2].metric("Idade materna avançada", number(births_br.nascidos_vivos_idade_materna_avancada))
    bar(data, "territorio", "nascidos_vivos", f"Nascidos vivos por {'região' if level == 'regiao' else 'UF'}")
    st.dataframe(data, hide_index=True, width="stretch")

elif page == "Parto e pré-natal":
    st.title("Parto e pré-natal")
    data = api_all("/api/v1/nascimentos", (("nivel", "regiao"),))
    cols = st.columns(3)
    cols[0].metric("Cesáreas", pct(births_br.percentual_cesareas))
    cols[1].metric("7+ consultas", pct(births_br.percentual_prenatal_7_mais))
    cols[2].metric("Gestação múltipla", number(births_br.nascidos_vivos_gestacao_multipla))
    left, right = st.columns(2)
    with left: bar(data, "territorio", "percentual_cesareas", "Cesáreas entre partos informados", "#376996")
    with right: bar(data, "territorio", "percentual_prenatal_7_mais", "Sete ou mais consultas pré-natais")

elif page == "Recém-nascidos":
    st.title("Recém-nascidos")
    data = api_all("/api/v1/nascimentos", (("nivel", "regiao"),))
    cols = st.columns(3)
    cols[0].metric("Prematuros", pct(births_br.percentual_prematuridade))
    cols[1].metric("Baixo peso", pct(births_br.percentual_baixo_peso))
    cols[2].metric("Apgar 5 min < 7", pct(births_br.percentual_apgar5_menor_7))
    labels = {"percentual_prematuridade": "Prematuridade", "percentual_baixo_peso": "Baixo peso",
              "percentual_apgar5_menor_7": "Apgar 5 min < 7"}
    metric = st.selectbox("Indicador", list(labels), format_func=labels.get)
    bar(data, "territorio", metric, "Distribuição regional", "#C94B40")

elif page == "Saúde materna":
    st.title("Morbidades maternas")
    level = st.segmented_control("Nível", ["brasil", "regiao", "estado"], default="brasil")
    data = api_all("/api/v1/morbidades", (("nivel", level),))
    groups = sorted(data.grupo_morbidade.unique())
    group_labels = {
        "complicacoes_anestesicas": "Complicações anestésicas",
        "diabetes_gestacional": "Diabetes gestacional",
        "hemorragia_obstetrica": "Hemorragia obstétrica",
        "hipertensao_gestacional": "Hipertensão gestacional",
        "infeccoes_puerperais": "Infecções puerperais",
    }
    group = st.selectbox(
        "Grupo",
        groups,
        format_func=lambda value: group_labels.get(value, value.replace("_", " ").capitalize()),
    )
    selected = data[data.grupo_morbidade == group]
    trend = selected.groupby("competencia", as_index=False)["registros_aih"].sum()
    trend["competencia"] = trend["competencia"].astype(str)
    fig = px.line(trend, x="competencia", y="registros_aih", markers=True, color_discrete_sequence=["#704C5E"])
    fig.update_layout(height=390, xaxis_type="category", xaxis_title=None, yaxis_title="AIHs",
                      paper_bgcolor="#fff", plot_bgcolor="#fff")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(selected, hide_index=True, width="stretch")
    st.markdown('<p class="note">Registros representam AIHs obstétricas, não mulheres únicas ou prevalência populacional.</p>', unsafe_allow_html=True)

elif page == "Mortalidade":
    st.title("Mortalidade")
    level = st.segmented_control("Nível", ["regiao", "estado"], default="regiao")
    data = api_all("/api/v1/mortalidade", (("nivel", level),))
    cols = st.columns(3)
    cols[0].metric("Óbitos infantis", number(deaths_br.obitos_infantis))
    cols[1].metric("Óbitos neonatais", number(deaths_br.obitos_neonatais))
    cols[2].metric("Causa obstétrica CID O", number(deaths_br.obitos_causa_obstetrica_cid_o))
    labels = {"taxa_observada_mortalidade_infantil_por_mil_nv": "Infantil por mil NV",
              "taxa_observada_mortalidade_neonatal_por_mil_nv": "Neonatal por mil NV",
              "razao_observada_causa_obstetrica_por_100mil_nv": "Causa obstétrica por 100 mil NV"}
    metric = st.selectbox("Taxa observada", list(labels), format_func=labels.get)
    bar(data, "territorio", metric, "Comparação territorial", "#C94B40")

elif page == "Comparação e mapa":
    st.title("Comparação estadual")
    births = api_all("/api/v1/nascimentos", (("nivel", "estado"),))
    deaths = api_all("/api/v1/mortalidade", (("nivel", "estado"),))
    data = births.merge(deaths[["codigo_territorio", "taxa_observada_mortalidade_infantil_por_mil_nv"]], on="codigo_territorio")
    data["codigo_ibge_uf"] = data.codigo_territorio.map(UF_GEOCODES)
    metrics = {
        "percentual_cesareas": "Cesáreas (%)",
        "percentual_prematuridade": "Prematuridade (%)",
        "percentual_baixo_peso": "Baixo peso (%)",
        "taxa_observada_mortalidade_infantil_por_mil_nv": "Mortalidade infantil (por mil NV)",
    }
    metric = st.selectbox("Indicador", list(metrics), format_func=metrics.get)
    for column in metrics:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    uf_codes = data.codigo_territorio.tolist()
    uf_labels = [f"{code} - {UF_NAMES[code]}" for code in uf_codes]
    selected_labels = st.multiselect("UFs", uf_labels, default=uf_labels[:5])
    chosen = [label[:2] for label in selected_labels]
    bar(data[data.codigo_territorio.isin(chosen)], "codigo_territorio", metric, "UFs selecionadas", "#376996")
    fig = px.choropleth_map(
        data,
        geojson=state_geojson(),
        locations="codigo_ibge_uf",
        featureidkey="properties.codarea",
        color=metric,
        hover_name="territorio",
        hover_data={"codigo_ibge_uf": False, "codigo_territorio": True, "nascidos_vivos": ":,"},
        color_continuous_scale=["#F1E7C9", "#D9A441", "#C94B40"],
        labels={metric: metrics[metric], "codigo_territorio": "UF", "nascidos_vivos": "Nascidos vivos"},
        center={"lat": -14.2, "lon": -51.9},
        zoom=2.7,
        map_style="white-bg",
        opacity=0.9,
    )
    fig.update_traces(marker_line_color="#FFFFFF", marker_line_width=0.8)
    fig.update_layout(
        height=560,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="#fff",
        coloraxis_colorbar=dict(title=metrics[metric]),
    )
    st.plotly_chart(fig, width="stretch")

else:
    st.title("Qualidade dos dados")
    checks = pd.DataFrame([
        ["SINASC 2024", "2.389.325", "54 residências sem match", "Validado"],
        ["SIM 2024", "1.532.015", "2.290 residências sem match", "Validado"],
        ["SINAN SIFG 2024", "89.934", "Preliminar; não integrado ao Gold", "Avaliado"],
        ["SIH/SUS 2024", "14.171.364", "AIH não equivale a pessoa", "Validado"],
    ], columns=["Fonte", "Registros", "Observação", "Status"])
    st.dataframe(checks, hide_index=True, width="stretch")
    st.subheader("Cobertura pública")
    st.write("Brasil, região e UF. Indicadores municipais permanecem internos até aprovação de supressão de células pequenas.")
    st.subheader("Definições")
    st.write("Cada percentual usa somente registros com o campo correspondente informado. Contagens hospitalares representam AIHs; mortalidade usa residência e nascidos vivos do mesmo período.")
