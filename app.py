import io
import streamlit as st
import pandas as pd
import requests

# ============================================================
# CONFIGURAÇÃO — cole aqui o link da sua planilha publicada
# ============================================================
# Como conseguir esse link:
# 1. Abra sua planilha no Google Sheets
# 2. Vá em Arquivo -> Compartilhar -> Publicar na web
# 3. Escolha a aba "Carteira" e o formato "Valores separados por vírgula (.csv)"
# 4. Clique em Publicar e copie o link gerado
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQGHswrii-CDmpipihNPKIfGFKCuYdD-OoWUGnaH3MML0fEZubpSMO9LzuSHklCmA/pub?gid=2049328970&single=true&output=csv"

# Link da aba "Metas" (Categoria | % Alvo), publicada da mesma forma
METAS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQGHswrii-CDmpipihNPKIfGFKCuYdD-OoWUGnaH3MML0fEZubpSMO9LzuSHklCmA/pub?gid=578310671&single=true&output=csv"

st.set_page_config(page_title="Minha Carteira", page_icon="💰", layout="wide")

st.title("💰 Minha Carteira de Investimentos")


def _baixar_csv(url, tentativas=3):
    """Baixa o CSV se identificando como navegador — o Google às vezes
    demora ou bloqueia pedidos sem isso. Tenta algumas vezes antes de desistir."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = requests.get(url, headers=headers, timeout=30)
            resposta.raise_for_status()
            return io.StringIO(resposta.text)
        except requests.exceptions.RequestException as erro:
            ultimo_erro = erro
    raise ultimo_erro


def _converter_numero_br(valor):
    """Converte números no formato brasileiro (ex: 'R$ 1.234,56', '30,50' ou '8,34%') para float."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip().replace("R$", "").replace("%", "").replace("\xa0", " ").strip()
    if texto == "":
        return None
    if "," in texto:
        # formato brasileiro: ponto é milhar, vírgula é decimal
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


@st.cache_data(ttl=300)  # atualiza os dados a cada 5 minutos
def carregar_dados(url):
    # a planilha tem linhas de título antes da tabela — acha automaticamente
    # em qual linha está o cabeçalho real (a que começa com "Ativo")
    bruto = pd.read_csv(_baixar_csv(url), header=None)
    linha_cabecalho = None
    for i, valor in enumerate(bruto[0]):
        if str(valor).strip() == "Ativo":
            linha_cabecalho = i
            break
    if linha_cabecalho is None:
        raise ValueError("Não encontrei a coluna 'Ativo' na planilha — confira os nomes das colunas.")

    df = pd.read_csv(_baixar_csv(url), skiprows=linha_cabecalho)

    # converte as colunas numéricas (aceita formato brasileiro com vírgula)
    colunas_numericas = [
        "Quantidade",
        "Preço de Compra (R$)",
        "Preço Atual (R$)",
        "Valor Investido (R$)",
        "Valor Atual (R$)",
        "Dividendos 12m (R$)",  # na prática, guarda o yield atual em % (ex: 8,34)
    ]
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = df[col].apply(_converter_numero_br)

    # calcula Preço Teto (yield mínimo desejado de 8%) e a margem de segurança
    # (o quanto o preço atual está abaixo ou acima do teto).
    # a coluna "Dividendos 12m (R$)" guarda o yield atual em %, então primeiro
    # convertemos pra dividendo em R$: Dividendo = Yield% x Preço Atual
    if "Dividendos 12m (R$)" in df.columns:
        dividendo_reais = (df["Dividendos 12m (R$)"] / 100) * df["Preço Atual (R$)"]
        df["Preço Teto (R$)"] = dividendo_reais / 0.08
        df["Margem de Segurança (%)"] = (
            (df["Preço Teto (R$)"] - df["Preço Atual (R$)"]) / df["Preço Teto (R$)"] * 100
        )
    else:
        df["Preço Teto (R$)"] = None
        df["Margem de Segurança (%)"] = None

    # mantém só linhas de ativo de verdade — a seção "Resumo" abaixo da tabela
    # não tem Quantidade preenchida, então serve como corte natural
    df = df.dropna(subset=["Ativo", "Quantidade"])
    return df


@st.cache_data(ttl=300)
def carregar_metas(url):
    """Lê a aba 'Metas' (Categoria | % Alvo)."""
    df = pd.read_csv(_baixar_csv(url))
    df = df.dropna(subset=[df.columns[0]])
    df.columns = ["Categoria", "% Alvo"]
    df["% Alvo"] = df["% Alvo"].apply(_converter_numero_br)
    return df


if CSV_URL == "COLE_AQUI_O_LINK_DA_SUA_PLANILHA":
    st.warning("⚠️ Ainda falta colar o link da planilha na variável CSV_URL, no topo do arquivo app.py.")
    st.stop()

try:
    df = carregar_dados(CSV_URL)
except Exception as e:
    st.error(f"Não consegui ler a planilha. Verifique se o link está correto e publicado. Detalhe: {e}")
    st.stop()

if df.empty:
    st.info("Sua planilha ainda não tem nenhum investimento preenchido.")
    st.stop()

# ============================================================
# RESUMO GERAL
# ============================================================
valor_investido = df["Valor Investido (R$)"].sum()
valor_atual = df["Valor Atual (R$)"].sum()
rendimento_total = (valor_atual - valor_investido) / valor_investido if valor_investido else 0

col1, col2, col3 = st.columns(3)
col1.metric("Valor Investido", f"R$ {valor_investido:,.2f}")
col2.metric("Valor Atual", f"R$ {valor_atual:,.2f}")
diferenca = valor_atual - valor_investido
sinal = "-" if diferenca < 0 else ""
col3.metric(
    "Rendimento Total",
    f"{rendimento_total * 100:.1f}%",
    delta=f"{sinal}R$ {abs(diferenca):,.2f}",
)

st.divider()

# ============================================================
# GRÁFICO — divisão da carteira por categoria
# ============================================================
st.subheader("Divisão da carteira por categoria")
por_categoria = df.groupby("Categoria")["Valor Atual (R$)"].sum()
st.bar_chart(por_categoria)

# ============================================================
# TABELA DETALHADA POR ATIVO
# ============================================================
st.subheader("Detalhe por ativo")

df_exibir = df.copy()
df_exibir["Rendimento (%)"] = (
    (df_exibir["Valor Atual (R$)"] - df_exibir["Valor Investido (R$)"])
    / df_exibir["Valor Investido (R$)"]
    * 100
)

st.dataframe(
    df_exibir[
        [
            "Ativo",
            "Categoria",
            "Quantidade",
            "Preço de Compra (R$)",
            "Preço Atual (R$)",
            "Valor Investido (R$)",
            "Valor Atual (R$)",
            "Rendimento (%)",
            "Preço Teto (R$)",
            "Margem de Segurança (%)",
        ]
    ].style.format(
        {
            "Preço de Compra (R$)": "R$ {:.2f}",
            "Preço Atual (R$)": "R$ {:.2f}",
            "Valor Investido (R$)": "R$ {:.2f}",
            "Valor Atual (R$)": "R$ {:.2f}",
            "Rendimento (%)": "{:.1f}%",
            "Preço Teto (R$)": "R$ {:.2f}",
            "Margem de Segurança (%)": "{:.1f}%",
        }
    ),
    use_container_width=True,
)
st.caption(
    "Preço Teto = Dividendos pagos nos últimos 12 meses ÷ 8% (yield mínimo desejado). "
    "Margem de Segurança positiva significa que o preço atual está abaixo do teto (desconto)."
)

# ============================================================
# METAS E REBALANCEAMENTO
# ============================================================
st.divider()
st.subheader("🎯 Metas por categoria e rebalanceamento")

try:
    metas = carregar_metas(METAS_URL)
except Exception as e:
    metas = None
    st.info(f"Não consegui ler a aba 'Metas' ainda. Detalhe: {e}")

if metas is not None and not metas.empty:
    # % atual de cada categoria na carteira
    atual_categoria = df.groupby("Categoria")["Valor Atual (R$)"].sum()
    pct_atual = (atual_categoria / valor_atual * 100).rename("% Atual")

    comparativo = metas.set_index("Categoria").join(pct_atual, how="outer")
    comparativo["% Atual"] = comparativo["% Atual"].fillna(0)
    comparativo["% Alvo"] = comparativo["% Alvo"].fillna(0)
    comparativo["Diferença (p.p.)"] = comparativo["% Atual"] - comparativo["% Alvo"]
    comparativo = comparativo.reset_index()

    st.dataframe(
        comparativo.style.format(
            {"% Atual": "{:.1f}%", "% Alvo": "{:.1f}%", "Diferença (p.p.)": "{:+.1f}"}
        ),
        use_container_width=True,
    )

    # categorias abaixo da meta = onde vale a pena aportar mais
    categorias_abaixo = comparativo[comparativo["Diferença (p.p.)"] < -1]["Categoria"].tolist()

    if categorias_abaixo:
        st.markdown(f"**Categorias abaixo da meta:** {', '.join(categorias_abaixo)}")
        st.markdown(
            "Entre os ativos dessas categorias, aqui estão os mais descontados "
            "(maior margem de segurança em relação ao Preço Teto) — bons candidatos "
            "para priorizar no próximo aporte:"
        )
        candidatos = df[
            df["Categoria"].isin(categorias_abaixo) & df["Margem de Segurança (%)"].notna()
        ].sort_values("Margem de Segurança (%)", ascending=False)

        if not candidatos.empty:
            st.dataframe(
                candidatos[
                    ["Ativo", "Categoria", "Preço Atual (R$)", "Preço Teto (R$)", "Margem de Segurança (%)"]
                ].style.format(
                    {
                        "Preço Atual (R$)": "R$ {:.2f}",
                        "Preço Teto (R$)": "R$ {:.2f}",
                        "Margem de Segurança (%)": "{:.1f}%",
                    }
                ),
                use_container_width=True,
            )
        else:
            st.caption(
                "Nenhum ativo dessas categorias tem Dividendos 12m preenchido ainda "
                "para calcular a margem de segurança."
            )
    else:
        st.success("Sua carteira está dentro das metas definidas (ou acima delas) em todas as categorias! 🎉")

st.caption("Os dados são atualizados automaticamente a cada 5 minutos a partir da sua planilha.")
