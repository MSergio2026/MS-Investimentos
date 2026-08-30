import io
import os
import pandas as pd
import requests

# ============================================================
# CONFIGURAÇÃO
# ============================================================
# Mesmo link CSV da aba "Carteira" usado no painel Streamlit
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQGHswrii-CDmpipihNPKIfGFKCuYdD-OoWUGnaH3MML0fEZubpSMO9LzuSHklCmA/pub?gid=2049328970&single=true&output=csv"

# Queda mínima (em %) para disparar o alerta
LIMITE_QUEDA = -4.0

# Token e Chat ID do Telegram vêm de variáveis de ambiente (configuradas
# como "Secrets" no GitHub Actions, nunca ficam expostos no código)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def _baixar_csv(url):
    """Baixa o CSV se identificando como navegador — o Google às vezes
    bloqueia pedidos vindos de servidores (como o GitHub Actions) sem isso."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resposta = requests.get(url, headers=headers, timeout=15)
    resposta.raise_for_status()
    return io.StringIO(resposta.text)


def _converter_numero_br(valor):
    """Converte números no formato brasileiro (ex: '30,50' ou '8,34%') para float."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip().replace("R$", "").replace("%", "").replace("\xa0", " ").strip()
    if texto == "":
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def carregar_carteira():
    bruto = pd.read_csv(_baixar_csv(CSV_URL), header=None)
    linha_cabecalho = None
    for i, valor in enumerate(bruto[0]):
        if str(valor).strip() == "Ativo":
            linha_cabecalho = i
            break
    if linha_cabecalho is None:
        raise ValueError("Não encontrei a coluna 'Ativo' na planilha.")

    df = pd.read_csv(_baixar_csv(CSV_URL), skiprows=linha_cabecalho)
    df["Quantidade"] = df["Quantidade"].apply(_converter_numero_br)
    df["Variação Dia (%)"] = df["Variação Dia (%)"].apply(_converter_numero_br)
    df = df.dropna(subset=["Ativo", "Quantidade"])
    return df


def enviar_telegram(mensagem):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resposta = requests.post(url, data={"chat_id": CHAT_ID, "text": mensagem}, timeout=15)
    resposta.raise_for_status()


def main():
    df = carregar_carteira()

    quedas = df[df["Variação Dia (%)"] <= LIMITE_QUEDA]

    if quedas.empty:
        print("Nenhum ativo com queda relevante hoje.")
        return

    linhas = [
        f"🔴 {row['Ativo']}: {row['Variação Dia (%)']:.2f}%"
        for _, row in quedas.iterrows()
    ]
    mensagem = "⚠️ Alerta de queda na carteira (hoje):\n\n" + "\n".join(linhas)
    enviar_telegram(mensagem)
    print("Alerta enviado:\n" + mensagem)


if __name__ == "__main__":
    main()
