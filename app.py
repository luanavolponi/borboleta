# -*- coding: utf-8 -*-
"""
Borboleta Estudio Criativo — gestao da empresa (impressao 3D).
Pedidos, clientes, produtos & precificacao, estoque e financeiro.
"""
import io
import math
import os
import sys
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import database as db

# --- Identidade visual (Manual da marca v1.1, out/2026) ---
ASSETS = os.path.join(BASE_DIR, "assets")
LOGO_FUNDO_AZUL = os.path.join(ASSETS, "logo-fundo-azul.png")    # versao principal (nome branco)
LOGO_FUNDO_CLARO = os.path.join(ASSETS, "logo-fundo-claro.png")  # nome em azul, p/ fundo branco
SIMBOLO = os.path.join(ASSETS, "simbolo.png")                    # B com asas
SLOGAN = "Feito para transformar."
VERSAO = "1.7 · 11/10/2026"  # atualizar a cada publicacao: aparece no login e no menu

AZUL = "#190A76"      # fundo principal, textos
ROSA = "#F1287C"      # o B e titulos grandes
LARANJA = "#FF5110"   # asas e destaques
VERDE = "#4BB74F"     # assinatura
ROXO = "#9428B3"      # asas
LILAS = "#D2CBF4"     # textos de apoio sobre o azul
LAVANDA = "#EEEBFC"   # quadros e detalhes sobre o branco
# Papeis semanticos usados nas telas
VERMELHO = LARANJA    # despesas / alerta
AMBAR = ROSA          # a receber

# --- Page Config (DEVE vir antes de qualquer outro comando st) ---
st.set_page_config(
    page_title="Borboleta · Estúdio Criativo",
    page_icon=Image.open(SIMBOLO),
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

    /* Fonte da marca em tudo, menos nos icones do Streamlit */
    html, body, .stApp *:not([data-testid="stIconMaterial"]):not(code):not(pre) {{
        font-family: 'Plus Jakarta Sans', 'Source Sans Pro', sans-serif;
    }}
    .stApp h1 {{ color:{AZUL}; font-weight:800; letter-spacing:-.01em; }}
    .stApp h2, .stApp h3, .stApp h4, .stApp h5 {{ color:{AZUL}; font-weight:700; }}

    /* Camadas: faixas nas cores da marca (no branco, a primeira e azul) */
    .camadas {{ display:flex; gap:4px; margin:-6px 0 18px 0; }}
    .camadas span {{ height:6px; width:44px; border-radius:3px; }}
    .slogan {{ color:{ROXO}; font-weight:600; margin:-4px 0 4px 0; }}

    /* Cartoes de numeros */
    .card {{ background:#FFFFFF; border:1px solid {LAVANDA}; border-radius:14px; padding:14px 16px;
             box-shadow:0 1px 3px rgba(25,10,118,.07); margin-bottom:10px; }}
    .card-t {{ color:{ROXO}; font-size:.72em; font-weight:700; text-transform:uppercase; letter-spacing:.08em; }}
    .card-v {{ color:{AZUL}; font-size:1.45em; font-weight:800; margin-top:2px; }}
    .card-s {{ color:#6B6597; font-size:.8em; margin-top:2px; }}

    /* Barra lateral no azul da marca */
    section[data-testid="stSidebar"] {{ background-color:{AZUL}; }}
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label {{ color:#FFFFFF; }}
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color:{LILAS}; }}
    section[data-testid="stSidebar"] hr {{ border-color:rgba(255,255,255,.15); }}
    section[data-testid="stSidebar"] [data-testid="stIconMaterial"] {{ color:#FFFFFF; }}
    section[data-testid="stSidebar"] .stButton button {{ justify-content:flex-start; border-radius:10px; }}
    section[data-testid="stSidebar"] button[kind="secondary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {{
        background:transparent; border:1px solid rgba(255,255,255,.16); color:#FFFFFF; }}
    section[data-testid="stSidebar"] button[kind="secondary"]:hover,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {{
        background:rgba(255,255,255,.08); border-color:{ROSA}; color:#FFFFFF; }}
    section[data-testid="stSidebar"] button[kind="primary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {{
        background:{ROSA}; border-color:{ROSA}; color:#FFFFFF; font-weight:700; }}
    section[data-testid="stSidebar"] [data-testid="stAlert"] {{ background:#FFE4EC; border-radius:10px; }}
    section[data-testid="stSidebar"] [data-testid="stAlert"] p {{ color:#7A1630; font-weight:600; }}
</style>
""", unsafe_allow_html=True)


def camadas(fundo_azul=False):
    # Manual: no azul a primeira faixa e branca; no branco, ela e azul
    cores = ["#FFFFFF" if fundo_azul else AZUL, ROSA, LARANJA, VERDE, ROXO]
    return '<div class="camadas">' + "".join(f'<span style="background:{c}"></span>' for c in cores) + "</div>"


def titulo(texto, slogan=False):
    """Titulo de pagina no padrao da marca: titulo + faixas 'camadas'."""
    st.title(texto)
    if slogan:
        st.markdown(f'<div class="slogan">{SLOGAN}</div>', unsafe_allow_html=True)
    st.markdown(camadas(), unsafe_allow_html=True)


# === TELA DE LOGIN ===
def check_password():
    """Retorna True se o usuario esta autenticado."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""

    if st.session_state.authenticated:
        return True

    # Tela de entrada no azul da marca, com a versao principal do logo (nome em branco)
    st.markdown(f"""
    <style>
        .stApp {{ background:{AZUL}; }}
        header[data-testid="stHeader"] {{ background:transparent; }}
        .block-container {{ max-width: 430px; padding-top: 3rem; }}
        [data-testid="stForm"] {{ background:#FFFFFF; border:none; border-radius:18px; padding:22px; }}
        .login-slogan {{ text-align:center; color:#FFFFFF; font-size:1.25em; font-weight:700; margin:6px 0 2px 0; }}
        .login-rodape {{ text-align:center; color:{LILAS}; font-size:.82em; margin-top:26px; }}
    </style>
    """, unsafe_allow_html=True)
    _, c_logo, _ = st.columns([1, 3, 1])
    c_logo.image(LOGO_FUNDO_AZUL, use_container_width=True)
    st.markdown(f'<div class="login-slogan">{SLOGAN}</div>'
                f'<div style="display:flex;justify-content:center;">{camadas(fundo_azul=True)}</div>',
                unsafe_allow_html=True)

    with st.form("login_form"):
        usuario = st.text_input("👤 Usuário", placeholder="Digite seu nome")
        senha = st.text_input("🔒 Senha", type="password", placeholder="Digite sua senha")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if submitted:
            usuario_lower = usuario.strip().lower()
            try:
                senhas = dict(st.secrets["passwords"])
            except Exception:
                senhas = {}

            if not senhas:
                # Fecha o acesso se as senhas nao estiverem nos Secrets (sem senha reserva)
                print("[ACESSO] FALHA senhas nao configuradas nos Secrets", flush=True)
                st.error("Login indisponível: as senhas não estão configuradas nos Secrets do app.")
            elif usuario_lower in senhas and senha == senhas[usuario_lower]:
                st.session_state.authenticated = True
                st.session_state.username = usuario_lower.capitalize()
                st.rerun()
            else:
                print(f"[ACESSO] FALHA login usuario='{usuario_lower}'", flush=True)
                st.error("Usuário ou senha incorretos.")

    st.markdown(f'<div class="login-rodape">🔒 Acesso restrito a Luana e Tayrone<br>versão {VERSAO}</div>',
                unsafe_allow_html=True)
    return False


if not check_password():
    st.stop()


# --- Sync: puxa dados mais recentes do GitHub (na nuvem) ---
from sync import (pull_database, push_database, is_cloud, get_last_sync_status,  # noqa: E402
                  importar_pendentes, diagnostico)

if is_cloud() and "db_pulled" not in st.session_state:
    pull_database()
    st.session_state.db_pulled = True

db.init_db()
USUARIO = st.session_state.get("username", "")

# --- Cargas de dados deixadas no repositorio de dados (importar/*.json), uma vez por sessao ---
if is_cloud() and "importacao_feita" not in st.session_state:
    st.session_state.importacao_feita = True
    try:
        st.session_state["importacao_msgs"] = importar_pendentes(db.aplicar_importacao)
    except Exception as _e:
        print(f"[IMPORTACAO] erro: {_e}", flush=True)

if "acesso_logado" not in st.session_state:
    st.session_state.acesso_logado = True
    try:
        db.registrar_acesso(USUARIO)
        print(f"[ACESSO] OK usuario='{USUARIO}'", flush=True)
        if is_cloud():
            push_database()
    except Exception as _e:
        print(f"[ACESSO] erro ao registrar: {_e}", flush=True)


# =====================================================================
# Utilidades
# =====================================================================

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
EMOJI_STATUS = {"Orçamento": "📝", "Confirmado": "📌", "Produzindo": "🖨️", "Pronto": "📦",
                "Entregue": "✅", "Cancelado": "❌"}
DINHEIRO = "R$ %.2f"


def salvo(msg="Salvo!"):
    """Envia o banco para a nuvem (quando publicado) e avisa."""
    # Recria as tabelas editaveis do zero (edicoes antigas nao "pulam" para outra linha)
    st.session_state["ed_v"] = st.session_state.get("ed_v", 0) + 1
    if is_cloud():
        try:
            if not push_database():
                st.toast(f"Erro ao salvar na nuvem: {get_last_sync_status().get('msg', '?')}", icon="❌")
                return
        except Exception as e:
            st.toast(f"Erro ao salvar na nuvem: {e}", icon="❌")
            return
    st.toast(msg, icon="✅")


def ev():
    """Versao das tabelas editaveis (muda a cada salvamento)."""
    return st.session_state.get("ed_v", 0)


def brl(v):
    v = v or 0
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {s}" if v < 0 else f"R$ {s}"


def fmt_data(s):
    if not s:
        return "—"
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(s)


def para_data(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def mes_label(ym):
    y, m = ym.split("-")
    return f"{MESES[int(m) - 1]}/{y}"


def lista_meses(n=24):
    hoje = date.today()
    y, m = hoje.year, hoje.month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return out


def intervalo_mes(ym):
    y, m = map(int, ym.split("-"))
    ini = date(y, m, 1)
    prox = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return ini.isoformat(), (prox - timedelta(days=1)).isoformat()


def seletor_mes(key):
    return st.selectbox("Mês", lista_meses(), format_func=mes_label, key=key)


def _num(v, padrao=0.0):
    try:
        if v is None or pd.isna(v):
            return padrao
        return float(v)
    except (TypeError, ValueError):
        return padrao


def _txt(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def _bool(v):
    try:
        return bool(v) and not pd.isna(v)
    except (TypeError, ValueError):
        return bool(v)


def card(titulo, valor, cor=ROXO, sub=""):
    return (f'<div class="card" style="border-left:5px solid {cor}">'
            f'<div class="card-t">{titulo}</div><div class="card-v">{valor}</div>'
            f'<div class="card-s">{sub or "&nbsp;"}</div></div>')


def linha_cards(cards):
    for col, c in zip(st.columns(len(cards)), cards):
        col.markdown(card(*c), unsafe_allow_html=True)


def opcoes_filamentos(apenas_ativos=True):
    return {f"#{f['id']} {db.nome_filamento(f)}": f for f in db.listar("filamentos", apenas_ativos)}


def opcoes_impressoras(apenas_ativos=True):
    return {f"#{i['id']} {i['nome']}": i for i in db.listar("impressoras", apenas_ativos)}


def rotulo_por_id(opcoes, item_id):
    if item_id is None:
        return None
    return next((k for k, v in opcoes.items() if v["id"] == item_id), None)


def impressora_padrao():
    imps = db.listar("impressoras", apenas_ativos=True)
    return imps[0] if imps else None


def layout_grafico(fig, altura=340):
    fig.update_layout(height=altura, margin=dict(l=10, r=10, t=30, b=10), separators=",.",
                      font=dict(family="Plus Jakarta Sans, sans-serif", color=AZUL),
                      legend=dict(orientation="h", y=1.12), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def aplicar_edicoes(tabela, df_editado, converter):
    """Salva um st.data_editor com colunas 'id' e 'Excluir?'. Retorna (alterados, excluidos)."""
    alterados = excluidos = 0
    for _, r in df_editado.iterrows():
        rid = int(r["id"])
        if _bool(r.get("Excluir?")):
            db.excluir(tabela, rid)
            excluidos += 1
            continue
        dados = converter(r)
        if dados:
            db.atualizar(tabela, rid, dados)
            alterados += 1
    return alterados, excluidos


# =====================================================================
# Menu lateral
# =====================================================================

PG_INICIO = "🏠 Início"
PG_PEDIDOS = "🧾 Pedidos"
PG_CLIENTES = "👥 Clientes"
PG_PRODUTOS = "🏷️ Produtos & Preços"
PG_ESTOQUE = "📦 Estoque"
PG_FINANCEIRO = "💰 Financeiro"
PG_CONFIG = "⚙️ Configurações"
PAGINAS = [PG_INICIO, PG_PEDIDOS, PG_CLIENTES, PG_PRODUTOS, PG_ESTOQUE, PG_FINANCEIRO, PG_CONFIG]

if "pagina" not in st.session_state:
    st.session_state.pagina = PG_INICIO

with st.sidebar:
    _, _c_logo, _ = st.columns([1, 5, 1])
    _c_logo.image(LOGO_FUNDO_AZUL, use_container_width=True)
    st.markdown(camadas(fundo_azul=True), unsafe_allow_html=True)
    for _p in PAGINAS:
        if st.button(_p, key=f"nav_{_p}", use_container_width=True,
                     type="primary" if _p == st.session_state.pagina else "secondary"):
            st.session_state.pagina = _p
            st.rerun()
    st.divider()
    if is_cloud() and get_last_sync_status().get("ok") is False:
        st.error(f"☁️ {get_last_sync_status().get('msg')}")
    st.caption(f"Olá, {USUARIO}! · {SLOGAN}")
    st.caption(f"versão {VERSAO}")
    if st.button("Sair", key="logout", use_container_width=True):
        for _k in list(st.session_state.keys()):
            del st.session_state[_k]
        st.rerun()


# =====================================================================
# 🏠 Inicio
# =====================================================================

def pagina_inicio():
    c_logo, c_tit = st.columns([1, 7], vertical_alignment="center")
    c_logo.image(LOGO_FUNDO_CLARO, use_container_width=True)
    with c_tit:
        titulo("Painel do estúdio", slogan=True)
    c1, _ = st.columns([1, 3])
    with c1:
        mes = seletor_mes("inicio_mes")
    ini, fim = intervalo_mes(mes)

    lancs = db.listar_lancamentos(ini, fim)
    entradas = sum(l["valor"] for l in lancs if l["tipo"] == "entrada")
    saidas = sum(l["valor"] for l in lancs if l["tipo"] == "saida")
    recebido_vendas = sum(l["valor"] for l in lancs if l["tipo"] == "entrada" and l["categoria"] == "Venda")

    todos = db.listar_pedidos()
    validos = [p for p in todos if p["status"] not in ("Orçamento", "Cancelado")]
    do_mes = [p for p in validos if ini <= p["data"] <= fim]
    vendido = sum(p["total"] for p in do_mes)
    lucro_mes = sum(p["lucro"] for p in do_mes)
    abertos = [p for p in todos if p["status"] in db.STATUS_ABERTOS]
    a_receber = sum(p["a_receber"] for p in validos)
    orcamentos = [p for p in todos if p["status"] == "Orçamento"]

    st.markdown(f"#### 📊 {mes_label(mes)}")
    linha_cards([
        ("Vendido no mês", brl(vendido), ROXO, f"{len(do_mes)} pedido(s) · lucro est. {brl(lucro_mes)}"),
        ("Recebido no mês", brl(recebido_vendas), VERDE, f"entradas totais {brl(entradas)}"),
        ("Despesas do mês", brl(saidas), VERMELHO, ""),
        ("Resultado do mês", brl(entradas - saidas), VERDE if entradas >= saidas else VERMELHO,
         "entradas − despesas"),
    ])
    contas = db.contas_a_pagar()
    hoje = date.today()
    a_pagar_30 = [l for l in contas if (para_data(l["data"]) or hoje) <= hoje + timedelta(days=30)]
    linha_cards([
        ("Pedidos em aberto", str(len(abertos)), AZUL, f"+ {len(orcamentos)} orçamento(s) pendente(s)"),
        ("A receber", brl(a_receber), AMBAR, "de pedidos já fechados"),
        ("A pagar em 30 dias", brl(sum(l["valor"] for l in a_pagar_30)), VERMELHO,
         f"inclui vencidas · total em aberto {brl(sum(l['valor'] for l in contas))}"),
        ("Saldo em caixa", brl(db.saldo_caixa()), ROXO, "só o que já entrou e já foi pago"),
    ])

    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.markdown("#### 🗓️ Próximas entregas")
        if not abertos:
            st.info("Nenhum pedido em aberto. 🎉")
        else:
            hoje = date.today()
            linhas = []
            for p in sorted(abertos, key=lambda x: x["prazo"] or "9999"):
                prazo = para_data(p["prazo"])
                if not prazo:
                    situ = "sem prazo"
                elif prazo < hoje:
                    situ = f"⚠️ atrasado {(hoje - prazo).days}d"
                elif prazo == hoje:
                    situ = "🔔 hoje"
                else:
                    situ = f"em {(prazo - hoje).days} dia(s)"
                linhas.append({"Nº": p["id"], "Cliente": p["cliente"],
                               "Status": f"{EMOJI_STATUS.get(p['status'], '')} {p['status']}",
                               "Prazo": fmt_data(p["prazo"]), "Situação": situ,
                               "Total": p["total"], "A receber": p["a_receber"]})
            st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True,
                         column_config={"Total": st.column_config.NumberColumn(format=DINHEIRO),
                                        "A receber": st.column_config.NumberColumn(format=DINHEIRO)})

    with col_b:
        vencendo = [l for l in contas if (para_data(l["data"]) or hoje) <= hoje + timedelta(days=7)]
        if vencendo:
            st.markdown("#### 📌 Contas da semana")
            for l in vencendo[:6]:
                st.warning(f"**{l['descricao']}** — {brl(l['valor'])} · "
                           f"{situacao_vencimento(l['data'], False)}")
            if len(vencendo) > 6:
                st.caption(f"+ {len(vencendo) - 6} outra(s) em 💰 Financeiro → Contas a pagar")
        st.markdown("#### 🚨 Estoque baixo")
        fil, ins, prod = db.get_alertas_estoque()
        if not (fil or ins or prod):
            st.success("Tudo certo com o estoque!")
        for f in fil:
            st.warning(f"🧵 **{db.nome_filamento(f)}** — restam {f['estoque_g']:.0f} g "
                       f"(mínimo {f['estoque_minimo_g']:.0f} g)")
        for i in ins:
            st.warning(f"🧰 **{i['nome']}** — restam {i['estoque']:g} {i['unidade']}")
        for p in prod:
            st.info(f"🎁 **{p['nome']}** — {p['estoque_pronto']} pronto(s), mínimo {p['estoque_minimo']}")

    col_c, col_d = st.columns([3, 2])
    with col_c:
        st.markdown("#### 📈 Entradas × despesas por mês")
        res = db.resumo_mensal(12)
        if not res:
            st.caption("Os gráficos aparecem quando houver lançamentos no Financeiro.")
        else:
            df = pd.DataFrame(res)
            df["Mês"] = df["mes"].map(mes_label)
            fig = go.Figure()
            fig.add_bar(x=df["Mês"], y=df["entradas"], name="Entradas", marker_color=VERDE)
            fig.add_bar(x=df["Mês"], y=df["saidas"], name="Despesas", marker_color=VERMELHO)
            fig.add_scatter(x=df["Mês"], y=df["resultado"], name="Resultado", mode="lines+markers",
                            line=dict(color=AZUL, width=3), marker=dict(color=AZUL))
            fig.update_layout(barmode="group", yaxis_tickprefix="R$ ")
            st.plotly_chart(layout_grafico(fig), key="graf_inicio_mensal")
    with col_d:
        st.markdown("#### 🏆 Mais vendidos no mês")
        top = db.itens_vendidos(ini, fim)[:8]
        if not top:
            st.caption("Nenhuma venda registrada neste mês.")
        else:
            st.dataframe(pd.DataFrame(top).rename(columns={"item": "Item", "qtd": "Qtd",
                                                           "receita": "Receita", "lucro": "Lucro"}),
                         hide_index=True, use_container_width=True,
                         column_config={"Receita": st.column_config.NumberColumn(format=DINHEIRO),
                                        "Lucro": st.column_config.NumberColumn(format=DINHEIRO)})


# =====================================================================
# 🧾 Pedidos
# =====================================================================

PERSONALIZADO = "✨ Personalizado"
COLS_ITENS = ["Produto", "Descrição", "Qtd", "Preço un.", "Filamento", "Gramas/un", "Horas/un", "Custo un."]


def pagina_pedidos():
    titulo("🧾 Pedidos")
    if "ped_msg" in st.session_state:
        st.success(st.session_state.pop("ped_msg"))

    # ---------- Lista
    f1, f2 = st.columns([3, 1])
    with f1:
        status_sel = st.multiselect("Status", db.STATUS_PEDIDO,
                                    default=[s for s in db.STATUS_PEDIDO if s != "Cancelado"],
                                    key="ped_filtro_status")
    with f2:
        periodo = st.selectbox("Período", ["Todos", "Este mês", "Mês passado", "Últimos 90 dias"],
                               key="ped_filtro_periodo")
    ini = fim = None
    hoje = date.today()
    if periodo == "Este mês":
        ini, fim = intervalo_mes(hoje.strftime("%Y-%m"))
    elif periodo == "Mês passado":
        ini, fim = intervalo_mes(lista_meses(2)[1])
    elif periodo == "Últimos 90 dias":
        ini = (hoje - timedelta(days=90)).isoformat()

    peds = db.listar_pedidos(status_sel or None, ini, fim) if status_sel else []
    if peds:
        validos = [p for p in peds if p["status"] not in ("Orçamento", "Cancelado")]
        linha_cards([
            ("Pedidos", str(len(peds)), ROXO, ""),
            ("Total vendido", brl(sum(p["total"] for p in validos)), VERDE, "sem orçamentos/cancelados"),
            ("A receber", brl(sum(p["a_receber"] for p in validos)), AMBAR, ""),
            ("Lucro estimado", brl(sum(p["lucro"] for p in validos)), ROSA, "vendas − custo das peças"),
        ])
        df = pd.DataFrame([{
            "Nº": p["id"], "Data": fmt_data(p["data"]), "Cliente": p["cliente"],
            "Status": f"{EMOJI_STATUS.get(p['status'], '')} {p['status']}",
            "Total": p["total"], "Recebido": p["valor_recebido"] or 0, "A receber": p["a_receber"],
            "Lucro est.": p["lucro"], "Prazo": fmt_data(p["prazo"]), "Canal": p["canal"] or "",
        } for p in peds])
        st.dataframe(df, hide_index=True, use_container_width=True, column_config={
            c: st.column_config.NumberColumn(format=DINHEIRO)
            for c in ["Total", "Recebido", "A receber", "Lucro est."]})
    else:
        st.info("Nenhum pedido encontrado com esses filtros.")

    st.divider()

    # ---------- Novo / editar
    todos = db.listar_pedidos()
    opcoes = {"➕ Novo pedido": None}
    for p in todos:
        opcoes[f"#{p['id']} — {p['cliente']} · {p['status']} · {fmt_data(p['data'])}"] = p["id"]
    if "ped_sel_next_id" in st.session_state:
        alvo = st.session_state.pop("ped_sel_next_id")
        st.session_state["ped_sel"] = next((k for k, v in opcoes.items() if v == alvo), "➕ Novo pedido")
    if st.session_state.get("ped_sel") not in opcoes:
        st.session_state["ped_sel"] = "➕ Novo pedido"

    escolha = st.selectbox("✏️ Abrir pedido para editar (ou criar um novo)", list(opcoes), key="ped_sel")
    pid = opcoes[escolha]
    pedido, itens = db.obter_pedido(pid) if pid else ({}, [])
    st.markdown(f"#### {'✏️ Editando pedido #' + str(pid) if pid else '➕ Novo pedido'}")

    cfg = db.get_config()
    clientes = db.listar("clientes")
    cli_opts = {"— sem cliente —": None, "➕ Cadastrar cliente novo": "novo"}
    cli_opts.update({f"{c['nome']} (#{c['id']})": c["id"] for c in clientes})
    cli_default = next((k for k, v in cli_opts.items() if v == pedido.get("cliente_id") and v), "— sem cliente —")

    produtos_todos = db.listar("produtos")
    prod_opts = {f"#{p['id']} {p['nome']}": p for p in produtos_todos}
    ids_no_pedido = {it["produto_id"] for it in itens}
    prod_ativos = [k for k, p in prod_opts.items() if p["ativo"] or p["id"] in ids_no_pedido]
    fil_opts = opcoes_filamentos(apenas_ativos=False)
    imp_padrao = impressora_padrao()

    linhas = []
    for it in itens:
        linhas.append({
            "Produto": rotulo_por_id(prod_opts, it["produto_id"]) or PERSONALIZADO,
            "Descrição": it["descricao"], "Qtd": float(it["qtd"]), "Preço un.": it["preco_unit"],
            "Filamento": rotulo_por_id(fil_opts, it["filamento_id"]), "Gramas/un": it["gramas_unit"],
            "Horas/un": None, "Custo un.": it["custo_unit"],
        })
    if not linhas:
        linhas = [{c: None for c in COLS_ITENS} | {"Qtd": 1.0}]
    df_itens = pd.DataFrame(linhas, columns=COLS_ITENS).astype({
        "Qtd": "float", "Preço un.": "float", "Gramas/un": "float", "Horas/un": "float", "Custo un.": "float",
        "Produto": "object", "Descrição": "object", "Filamento": "object"})

    k = f"{pid or 'novo'}_{st.session_state.get('ped_v', 0)}"
    with st.form(f"form_pedido_{k}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            cli_escolha = st.selectbox("Cliente", list(cli_opts), index=list(cli_opts).index(cli_default),
                                       key=f"ped_cli_{k}")
            novo_cli_nome = st.text_input("Nome do cliente novo (se for cadastrar)", key=f"ped_ncli_{k}")
            novo_cli_contato = st.text_input("WhatsApp / Instagram do cliente novo", key=f"ped_ncont_{k}")
        with c2:
            data_ped = st.date_input("Data do pedido", value=para_data(pedido.get("data")) or date.today(),
                                     format="DD/MM/YYYY", key=f"ped_data_{k}")
            prazo = st.date_input("Prazo de entrega", value=para_data(pedido.get("prazo")),
                                  format="DD/MM/YYYY", key=f"ped_prazo_{k}")
            status = st.selectbox("Status", db.STATUS_PEDIDO,
                                  index=db.STATUS_PEDIDO.index(pedido.get("status") or "Confirmado"),
                                  format_func=lambda s: f"{EMOJI_STATUS.get(s, '')} {s}", key=f"ped_status_{k}",
                                  help="Ao marcar como ✅ Entregue, o estoque é baixado automaticamente.")
        with c3:
            canal_atual = pedido.get("canal") or "Instagram"
            canal = st.selectbox("Canal de venda", db.CANAIS,
                                 index=db.CANAIS.index(canal_atual) if canal_atual in db.CANAIS else 0,
                                 key=f"ped_canal_{k}")
            fp_atual = pedido.get("forma_pagamento") or "Pix"
            forma = st.selectbox("Forma de pagamento", db.FORMAS_PAGAMENTO,
                                 index=db.FORMAS_PAGAMENTO.index(fp_atual) if fp_atual in db.FORMAS_PAGAMENTO else 0,
                                 key=f"ped_forma_{k}")

        st.markdown("**Itens do pedido**")
        st.caption("Escolha um produto do catálogo — preço, custo e filamento vêm sozinhos (deixe em branco). "
                   "Para peças sob encomenda, escolha ✨ Personalizado e preencha descrição, preço, filamento, "
                   "gramas e horas de impressão. Use o ➕ embaixo da tabela para adicionar linhas.")
        itens_edit = st.data_editor(
            df_itens, num_rows="dynamic", hide_index=True, use_container_width=True, key=f"ped_itens_{k}",
            column_config={
                "Produto": st.column_config.SelectboxColumn(options=[PERSONALIZADO] + prod_ativos, width="medium"),
                "Descrição": st.column_config.TextColumn(width="medium"),
                "Qtd": st.column_config.NumberColumn(min_value=1, step=1, format="%d"),
                "Preço un.": st.column_config.NumberColumn(min_value=0, format=DINHEIRO),
                "Filamento": st.column_config.SelectboxColumn(options=list(fil_opts), width="medium",
                                                              help="Só para itens personalizados"),
                "Gramas/un": st.column_config.NumberColumn(min_value=0, format="%.0f g"),
                "Horas/un": st.column_config.NumberColumn(min_value=0, format="%.2f h",
                                                          help="Tempo de impressão (personalizados)"),
                "Custo un.": st.column_config.NumberColumn(min_value=0, format=DINHEIRO,
                                                           help="Deixe em branco para calcular sozinho"),
            })

        c4, c5, c6, c7 = st.columns(4)
        desconto = c4.number_input("Desconto (R$)", min_value=0.0, step=1.0,
                                   value=float(pedido.get("desconto") or 0), key=f"ped_desc_{k}")
        frete = c5.number_input("Frete cobrado (R$)", min_value=0.0, step=1.0,
                                value=float(pedido.get("frete") or 0), key=f"ped_frete_{k}")
        recebido = c6.number_input("Valor já recebido (R$)", min_value=0.0, step=1.0,
                                   value=float(pedido.get("valor_recebido") or 0), key=f"ped_receb_{k}",
                                   help="Entra automaticamente no Financeiro como venda.")
        with c7:
            st.write("")
            pago_tudo = st.checkbox("💰 Recebi o valor total", key=f"ped_pago_{k}")
        obs = st.text_area("Observações", value=pedido.get("obs") or "", height=70, key=f"ped_obs_{k}")

        enviar = st.form_submit_button("💾 Salvar pedido", type="primary", use_container_width=True)

    if enviar:
        novos_itens = []
        for _, r in itens_edit.iterrows():
            prod_label = _txt(r.get("Produto"))
            desc = _txt(r.get("Descrição"))
            prod = prod_opts.get(prod_label) if prod_label and prod_label != PERSONALIZADO else None
            if not prod and not desc:
                continue
            qtd = int(_num(r.get("Qtd"), 1) or 1)
            preco = _num(r.get("Preço un."))
            custo = _num(r.get("Custo un."))
            if prod:
                novos_itens.append({
                    "produto_id": prod["id"], "descricao": desc or prod["nome"], "qtd": qtd,
                    "preco_unit": preco or prod["preco_venda"] or 0,
                    "custo_unit": custo or db.custo_produto(prod, cfg)["total"],
                    "filamento_id": prod["filamento_id"], "gramas_unit": prod["gramas"] or 0,
                })
            else:
                fil = fil_opts.get(_txt(r.get("Filamento")))
                gramas = _num(r.get("Gramas/un"))
                horas = _num(r.get("Horas/un"))
                custo_calc = db.calcular_custo(gramas, horas, 0, 0, fil, imp_padrao, cfg)["total"]
                novos_itens.append({
                    "produto_id": None, "descricao": desc or "Peça personalizada", "qtd": qtd,
                    "preco_unit": preco, "custo_unit": custo or custo_calc,
                    "filamento_id": fil["id"] if fil else None, "gramas_unit": gramas,
                })

        cliente_id = cli_opts[cli_escolha]
        erro = None
        if not novos_itens:
            erro = "Adicione pelo menos um item ao pedido."
        elif cliente_id == "novo" and not novo_cli_nome.strip():
            erro = "Escreva o nome do cliente novo (ou escolha um cliente da lista)."

        if erro:
            st.error(erro)
        else:
            if cliente_id == "novo":
                contato = novo_cli_contato.strip()
                cliente_id = db.inserir("clientes", {
                    "nome": novo_cli_nome.strip(),
                    "instagram": contato if contato.startswith("@") else "",
                    "telefone": "" if contato.startswith("@") else contato,
                })
            subtotal = sum(i["qtd"] * i["preco_unit"] for i in novos_itens)
            total = subtotal - desconto + frete
            custo_total = sum(i["qtd"] * i["custo_unit"] for i in novos_itens)
            novo_id = db.salvar_pedido({
                "cliente_id": cliente_id, "data": data_ped.isoformat(),
                "prazo": prazo.isoformat() if prazo else None, "status": status, "canal": canal,
                "forma_pagamento": forma, "desconto": desconto, "frete": frete,
                "valor_recebido": total if pago_tudo else recebido, "obs": obs.strip(),
            }, novos_itens, pid, USUARIO)
            st.session_state["ped_msg"] = (
                f"Pedido #{novo_id} salvo! Total {brl(total)} · custo das peças {brl(custo_total)} · "
                f"lucro estimado {brl(subtotal - desconto - custo_total)}")
            st.session_state["ped_sel_next_id"] = novo_id
            st.session_state["ped_v"] = st.session_state.get("ped_v", 0) + 1
            salvo("Pedido salvo!")
            st.rerun()

    if pid:
        with st.expander("🗑️ Excluir este pedido"):
            st.caption("Apaga o pedido, devolve ao estoque o que foi baixado e remove o recebimento do Financeiro.")
            conf = st.checkbox(f"Sim, quero excluir o pedido #{pid}", key=f"ped_del_conf_{k}")
            if st.button("Excluir pedido", disabled=not conf, key=f"ped_del_{k}"):
                db.excluir_pedido(pid)
                st.session_state["ped_sel_next_id"] = None
                st.session_state["ped_msg"] = f"Pedido #{pid} excluído."
                salvo("Pedido excluído")
                st.rerun()


# =====================================================================
# 👥 Clientes
# =====================================================================

def pagina_clientes():
    titulo("👥 Clientes")

    with st.expander("➕ Cadastrar cliente", expanded=False):
        with st.form("form_novo_cliente", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            nome = c1.text_input("Nome *")
            telefone = c2.text_input("WhatsApp / telefone")
            instagram = c3.text_input("Instagram")
            c4, c5 = st.columns(2)
            email = c4.text_input("E-mail")
            cidade = c5.text_input("Cidade")
            obs = st.text_input("Observações (preferências, aniversário...)")
            if st.form_submit_button("Cadastrar", type="primary"):
                if not nome.strip():
                    st.error("O nome é obrigatório.")
                else:
                    db.inserir("clientes", {"nome": nome.strip(), "telefone": telefone.strip(),
                                            "instagram": instagram.strip(), "email": email.strip(),
                                            "cidade": cidade.strip(), "obs": obs.strip()})
                    salvo(f"{nome.strip()} cadastrado(a)!")
                    st.rerun()

    clientes = db.listar("clientes")
    if not clientes:
        st.info("Nenhum cliente cadastrado ainda. Dá pra cadastrar aqui ou direto ao criar um pedido.")
        return

    pedidos = [p for p in db.listar_pedidos() if p["status"] not in ("Orçamento", "Cancelado")]
    stats = {}
    for p in pedidos:
        s = stats.setdefault(p["cliente_id"], {"n": 0, "total": 0.0, "ultimo": ""})
        s["n"] += 1
        s["total"] += p["total"]
        s["ultimo"] = max(s["ultimo"], p["data"])

    busca = st.text_input("🔎 Buscar cliente", placeholder="nome, telefone ou Instagram")
    termo = busca.strip().lower()
    if termo:
        clientes = [c for c in clientes if termo in " ".join(
            [c["nome"], c["telefone"] or "", c["instagram"] or ""]).lower()]

    df = pd.DataFrame([{
        "id": c["id"], "Nome": c["nome"], "WhatsApp": c["telefone"] or "", "Instagram": c["instagram"] or "",
        "E-mail": c["email"] or "", "Cidade": c["cidade"] or "", "Obs": c["obs"] or "",
        "Pedidos": stats.get(c["id"], {}).get("n", 0),
        "Total comprado": stats.get(c["id"], {}).get("total", 0.0),
        "Último pedido": fmt_data(stats.get(c["id"], {}).get("ultimo")),
        "Excluir?": False,
    } for c in clientes], columns=["id", "Nome", "WhatsApp", "Instagram", "E-mail", "Cidade", "Obs", "Pedidos",
                                   "Total comprado", "Último pedido", "Excluir?"])
    st.caption("Edite direto na tabela e clique em **Salvar alterações**.")
    edit = st.data_editor(df, hide_index=True, use_container_width=True, key=f"cli_editor_{termo}_{ev()}",
                          disabled=["Pedidos", "Total comprado", "Último pedido"],
                          column_config={"id": None,
                                         "Total comprado": st.column_config.NumberColumn(format=DINHEIRO)})
    if st.button("💾 Salvar alterações", type="primary", key="cli_salvar"):
        alt, exc = aplicar_edicoes("clientes", edit, lambda r: {
            "nome": _txt(r["Nome"]) or "Sem nome", "telefone": _txt(r["WhatsApp"]),
            "instagram": _txt(r["Instagram"]), "email": _txt(r["E-mail"]), "cidade": _txt(r["Cidade"]),
            "obs": _txt(r["Obs"])})
        salvo(f"Clientes salvos ({exc} excluído(s))" if exc else "Clientes salvos!")
        st.rerun()

    st.divider()
    st.markdown("#### 📜 Histórico de um cliente")
    opts = {f"{c['nome']} (#{c['id']})": c["id"] for c in clientes}
    if opts:
        sel = st.selectbox("Cliente", list(opts), key="cli_hist")
        hist = [p for p in db.listar_pedidos() if p["cliente_id"] == opts[sel]]
        if not hist:
            st.caption("Esse cliente ainda não tem pedidos.")
        else:
            st.dataframe(pd.DataFrame([{
                "Nº": p["id"], "Data": fmt_data(p["data"]),
                "Status": f"{EMOJI_STATUS.get(p['status'], '')} {p['status']}",
                "Total": p["total"], "A receber": p["a_receber"], "Canal": p["canal"],
            } for p in hist]), hide_index=True, use_container_width=True,
                column_config={"Total": st.column_config.NumberColumn(format=DINHEIRO),
                               "A receber": st.column_config.NumberColumn(format=DINHEIRO)})


# =====================================================================
# 🏷️ Produtos & Precos
# =====================================================================

def arredondar_preco(v):
    """Arredonda para cima terminando em ,90 (ex.: 23,40 -> 23,90)."""
    if v <= 0:
        return 0.0
    return math.ceil(v - 0.9) + 0.9


def pagina_produtos():
    titulo("🏷️ Produtos & Preços")
    tab_calc, tab_cat = st.tabs(["🧮 Calculadora de preço", "📚 Catálogo de produtos"])
    cfg = db.get_config()
    medias = db.medias_filamento(cfg)
    fils = opcoes_filamentos()
    imps = opcoes_impressoras()

    def rotulo_tipo(t):
        m = medias[t]
        origem = "valor fixo" if m["fixo"] else f"média de {m['qtd']} filamento(s)"
        return f"{t} · {brl(m['preco_kg'])}/kg ({origem})"

    with tab_calc:
        if not medias["Simples"]["preco_kg"]:
            st.warning("Cadastre seus filamentos em **📦 Estoque** (com o preço do rolo) para o custo do material "
                       "entrar no cálculo.")
        if not imps:
            st.caption("💡 Cadastre sua impressora em **⚙️ Configurações** para incluir o desgaste da máquina "
                       "(sem ela, a energia é calculada com 150 W).")
        col_in, col_out = st.columns([1, 1], gap="large")
        with col_in:
            st.markdown("##### Dados da peça")
            tipo_fil = st.radio("Filamento", db.TIPOS_FILAMENTO, format_func=rotulo_tipo, key="calc_tipo",
                                help="O custo usa o preço MÉDIO por kg do tipo. Marque cada filamento como "
                                     "Simples ou Especial em 📦 Estoque; dá para fixar os valores em ⚙️ Configurações.")
            imp_label = st.selectbox("Impressora", list(imps) or ["Padrão (150 W)"], key="calc_imp")
            gramas = st.number_input("Peso da peça (g) — o fatiador mostra", min_value=0.0, step=1.0, key="calc_g")
            h1, h2 = st.columns(2)
            horas = h1.number_input("Tempo de impressão: horas", min_value=0, step=1, key="calc_h")
            minutos = h2.number_input("e minutos", min_value=0, max_value=59, step=5, key="calc_m")
            min_trab = st.number_input("Seu trabalho manual (minutos)", min_value=0.0, step=5.0, key="calc_trab",
                                       help="Tirar suporte, lixar, pintar, montar, embalar...")
            extra = st.number_input("Extras por peça (R$)", min_value=0.0, step=0.5, key="calc_extra",
                                    help="Embalagem, ímã, argola de chaveiro, tag, adesivo...")
            m1, m2 = st.columns(2)
            margem = m1.number_input("Margem de lucro (%)", min_value=0.0, step=10.0,
                                     value=float(cfg["margem_padrao"]), key="calc_margem")
            taxa = m2.number_input("Taxa de venda (%)", min_value=0.0, max_value=90.0, step=1.0,
                                   value=float(cfg["taxa_venda"]), key="calc_taxa",
                                   help="Maquininha, Shopee, Elo7... o preço já embute essa taxa.")

        imp = imps.get(imp_label)
        horas_total = horas + minutos / 60
        custo = db.calcular_custo(gramas, horas_total, min_trab, extra, None, imp, cfg,
                                  tipo_filamento=tipo_fil, medias=medias)
        preco = db.preco_sugerido(custo["total"], margem, taxa)
        preco_r = arredondar_preco(preco)
        lucro = preco_r * (1 - taxa / 100) - custo["total"]

        with col_out:
            st.markdown("##### Resultado (por peça)")
            linha_cards([("Preço sugerido", brl(preco_r), ROXO, f"exato: {brl(preco)}"),
                         ("Custo", brl(custo["total"]), VERMELHO, ""),
                         ("Lucro", brl(lucro), VERDE, "já descontada a taxa")])
            partes = {k: v for k, v in custo.items() if k != "total"}
            df_c = pd.DataFrame({"Parte do custo": list(partes), "Valor": list(partes.values())})
            df_c["%"] = (df_c["Valor"] / custo["total"] * 100).round(0) if custo["total"] else 0
            st.dataframe(df_c, hide_index=True, use_container_width=True,
                         column_config={"Valor": st.column_config.NumberColumn(format=DINHEIRO),
                                        "%": st.column_config.NumberColumn(format="%.0f%%")})
            st.caption(f"Material inclui {cfg['taxa_falha']:.0f}% a mais para falhas/suportes. "
                       f"Energia a {brl(cfg['custo_kwh'])}/kWh. Mão de obra a {brl(cfg['hora_trabalho'])}/h. "
                       "Ajuste em ⚙️ Configurações.")

            with st.form("form_salvar_produto", clear_on_submit=True):
                st.markdown("##### 💾 Salvar no catálogo")
                n1, n2 = st.columns(2)
                nome = n1.text_input("Nome do produto *", placeholder="Ex.: Chaveiro borboleta")
                categoria = n2.text_input("Categoria", placeholder="Ex.: Chaveiros, Decoração, Vasos")
                n3, n4 = st.columns(2)
                preco_final = n3.number_input("Preço de venda (R$)", min_value=0.0, step=0.5, value=float(preco_r))
                est_min = n4.number_input("Estoque mínimo de peças prontas", min_value=0, step=1, value=0)
                fil_baixa = st.selectbox("Filamento usado (para dar baixa no estoque ao produzir)",
                                         ["— nenhum —"] + [k for k, f in fils.items()
                                                           if (f.get("tipo") or "Simples") == tipo_fil],
                                         help="Opcional. Não muda o custo, que usa a média do tipo.")
                if st.form_submit_button("Salvar produto", type="primary"):
                    if not nome.strip():
                        st.error("Dê um nome ao produto.")
                    else:
                        fil = fils.get(fil_baixa)
                        db.inserir("produtos", {
                            "nome": nome.strip(), "categoria": categoria.strip(), "tipo_filamento": tipo_fil,
                            "filamento_id": fil["id"] if fil else None, "impressora_id": imp["id"] if imp else None,
                            "gramas": gramas, "horas_impressao": horas_total, "minutos_trabalho": min_trab,
                            "custo_extra": extra, "margem_pct": margem, "preco_venda": preco_final,
                            "estoque_minimo": est_min, "ativo": 1,
                        })
                        salvo(f"{nome.strip()} salvo no catálogo!")
                        st.rerun()

    with tab_cat:
        produtos = db.listar("produtos")
        if not produtos:
            st.info("Nenhum produto ainda. Use a **🧮 Calculadora de preço** e clique em *Salvar produto*.")
            return
        fils_todos = opcoes_filamentos(apenas_ativos=False)
        imps_todas = opcoes_impressoras(apenas_ativos=False)
        so_ativos = st.toggle("Mostrar só produtos ativos", value=True, key="cat_ativos")
        if so_ativos:
            produtos = [p for p in produtos if p["ativo"]]
        linhas = []
        for p in produtos:
            c = db.custo_produto(p, cfg, medias)["total"]
            fil_p = fils_todos.get(rotulo_por_id(fils_todos, p["filamento_id"]) or "") or {}
            mg = p["margem_pct"] if p["margem_pct"] is not None else cfg["margem_padrao"]
            linhas.append({
                "id": p["id"], "Produto": p["nome"], "Categoria": p["categoria"] or "",
                "Tipo": p["tipo_filamento"] or fil_p.get("tipo") or "Simples",
                "Filamento": rotulo_por_id(fils_todos, p["filamento_id"]),
                "Impressora": rotulo_por_id(imps_todas, p["impressora_id"]),
                "Gramas": p["gramas"] or 0.0, "Horas": p["horas_impressao"] or 0.0,
                "Min. trabalho": p["minutos_trabalho"] or 0.0, "Extras": p["custo_extra"] or 0.0,
                "Margem %": mg, "Preço venda": p["preco_venda"] or 0.0,
                "Custo": c, "Sugerido": arredondar_preco(db.preco_sugerido(c, mg, cfg["taxa_venda"])),
                "Lucro/peça": (p["preco_venda"] or 0) * (1 - cfg["taxa_venda"] / 100) - c,
                "Prontas": p["estoque_pronto"] or 0, "Ativo": bool(p["ativo"]), "Excluir?": False,
            })
        df = pd.DataFrame(linhas)
        st.caption("Edite os dados e clique em **Salvar**. *Custo*, *Sugerido* e *Lucro/peça* são recalculados "
                   "ao salvar. Desmarque **Ativo** para tirar um produto de linha sem perder o histórico.")
        edit = st.data_editor(
            df, hide_index=True, use_container_width=True, key=f"cat_editor_{ev()}",
            disabled=["Custo", "Sugerido", "Lucro/peça", "Prontas"],
            column_config={
                "id": None,
                "Tipo": st.column_config.SelectboxColumn(options=db.TIPOS_FILAMENTO, required=True,
                                                         help="Define o preço médio do filamento no custo"),
                "Filamento": st.column_config.SelectboxColumn(options=list(fils_todos),
                                                              help="Opcional: rolo que sai do estoque ao produzir"),
                "Impressora": st.column_config.SelectboxColumn(options=list(imps_todas)),
                "Gramas": st.column_config.NumberColumn(format="%.0f g", min_value=0),
                "Horas": st.column_config.NumberColumn(format="%.2f h", min_value=0),
                "Min. trabalho": st.column_config.NumberColumn(format="%.0f min", min_value=0),
                "Extras": st.column_config.NumberColumn(format=DINHEIRO, min_value=0),
                "Margem %": st.column_config.NumberColumn(format="%.0f%%", min_value=0),
                "Preço venda": st.column_config.NumberColumn(format=DINHEIRO, min_value=0),
                "Custo": st.column_config.NumberColumn(format=DINHEIRO),
                "Sugerido": st.column_config.NumberColumn(format=DINHEIRO),
                "Lucro/peça": st.column_config.NumberColumn(format=DINHEIRO),
            })
        if st.button("💾 Salvar catálogo", type="primary", key="cat_salvar"):
            def conv(r):
                f = fils_todos.get(_txt(r["Filamento"]))
                i = imps_todas.get(_txt(r["Impressora"]))
                return {"nome": _txt(r["Produto"]) or "Sem nome", "categoria": _txt(r["Categoria"]),
                        "tipo_filamento": _txt(r["Tipo"]) or "Simples",
                        "filamento_id": f["id"] if f else None, "impressora_id": i["id"] if i else None,
                        "gramas": _num(r["Gramas"]), "horas_impressao": _num(r["Horas"]),
                        "minutos_trabalho": _num(r["Min. trabalho"]), "custo_extra": _num(r["Extras"]),
                        "margem_pct": _num(r["Margem %"]), "preco_venda": _num(r["Preço venda"]),
                        "ativo": 1 if _bool(r["Ativo"]) else 0}
            aplicar_edicoes("produtos", edit, conv)
            salvo("Catálogo salvo!")
            st.rerun()

        prejuizo = [l["Produto"] for l in linhas if l["Lucro/peça"] < 0]
        if prejuizo:
            st.error("⚠️ Vendendo abaixo do custo: " + ", ".join(prejuizo))


# =====================================================================
# 📦 Estoque
# =====================================================================

def form_compra(tipo, opcoes, unidade_fn, key):
    """Formulario 'Registrar compra' para filamento ou insumo."""
    with st.form(f"form_compra_{key}", clear_on_submit=True):
        label = st.selectbox("Item", list(opcoes), key=f"compra_item_{key}")
        if tipo == "filamento":
            qtd = st.number_input("Quantos rolos?", min_value=0.0, step=1.0, value=1.0, key=f"compra_qtd_{key}")
        else:
            qtd = st.number_input("Quantidade comprada", min_value=0.0, step=1.0, value=1.0,
                                  key=f"compra_qtd_{key}")
        valor = st.number_input("Valor total pago (R$)", min_value=0.0, step=1.0, key=f"compra_valor_{key}",
                                help="Deixe 0 para usar o preço cadastrado × quantidade.")
        data_c = st.date_input("Data da compra", value=date.today(), format="DD/MM/YYYY", key=f"compra_data_{key}")
        lancar = st.checkbox("Lançar como despesa no Financeiro", value=True, key=f"compra_lancar_{key}")
        n_parc, venc, forma = campos_pagamento(f"compra_{key}", forma_padrao="Pix", colunas=False)
        if st.form_submit_button("Registrar compra", type="primary") and label in opcoes and qtd > 0:
            item = opcoes[label]
            if tipo == "filamento":
                gramas = qtd * (item["peso_rolo_g"] or 1000)
                total = valor or qtd * (item["preco_rolo"] or 0)
                db.registrar_compra("filamento", item["id"], gramas, total, data_c.isoformat(), lancar, USUARIO,
                                    n_parc, venc.isoformat(), forma)
            else:
                total = valor or qtd * (item["custo_unit"] or 0)
                db.registrar_compra("insumo", item["id"], qtd, total, data_c.isoformat(), lancar, USUARIO,
                                    n_parc, venc.isoformat(), forma)
            salvo(f"Compra registrada: {unidade_fn(item, qtd)} · {texto_parcelas(total, n_parc)}")
            st.rerun()


def pagina_estoque():
    titulo("📦 Estoque")
    tab_fil, tab_ins, tab_prod, tab_hist = st.tabs(
        ["🧵 Filamentos", "🧰 Insumos", "🎁 Peças prontas", "📜 Histórico"])

    # ---------- Filamentos
    with tab_fil:
        fils = db.listar("filamentos")
        ativos = [f for f in fils if f["ativo"]]
        valor_estoque = sum((f["estoque_g"] or 0) * (f["preco_rolo"] or 0) / (f["peso_rolo_g"] or 1000)
                            for f in ativos)
        baixos = [f for f in ativos if (f["estoque_g"] or 0) <= (f["estoque_minimo_g"] or 0)]
        linha_cards([
            ("Filamento em estoque", f"{sum((f['estoque_g'] or 0) for f in ativos) / 1000:.2f} kg".replace(".", ","),
             ROXO, f"{len(ativos)} cor(es)/material(is)"),
            ("Valor parado em filamento", brl(valor_estoque), AZUL, ""),
            ("Precisa comprar", str(len(baixos)), VERMELHO if baixos else VERDE, "abaixo do mínimo"),
        ])

        c1, c2, c3 = st.columns(3)
        with c1:
            with st.expander("➕ Cadastrar filamento"):
                with st.form("form_novo_fil", clear_on_submit=True):
                    material = st.selectbox("Material", db.MATERIAIS)
                    tipo_novo = st.selectbox("Tipo", db.TIPOS_FILAMENTO,
                                             help="Simples ou Especial (silk, velvet, glitter...). Define o preço "
                                                  "médio por kg usado no custo das peças.")
                    cor = st.text_input("Cor *", placeholder="Ex.: Lilás, Branco, Rosa bebê")
                    marca = st.text_input("Marca", placeholder="Ex.: Voolt3D, 3D Lab, Bambu")
                    preco_rolo = st.number_input("Preço do rolo (R$)", min_value=0.0, step=1.0)
                    peso_rolo = st.number_input("Peso do rolo (g)", min_value=1.0, step=50.0, value=1000.0)
                    est_ini = st.number_input("Rolos que vocês já têm (pode ser 0,5)", min_value=0.0, step=0.5)
                    minimo = st.number_input("Avisar quando tiver menos de (g)", min_value=0.0, step=50.0, value=300.0)
                    if st.form_submit_button("Cadastrar", type="primary"):
                        if not cor.strip():
                            st.error("Informe a cor.")
                        else:
                            fid = db.inserir("filamentos", {
                                "material": material, "cor": cor.strip(), "marca": marca.strip(),
                                "tipo": tipo_novo,
                                "preco_rolo": preco_rolo, "peso_rolo_g": peso_rolo, "estoque_g": 0,
                                "estoque_minimo_g": minimo, "ativo": 1})
                            if est_ini > 0:
                                db.ajustar_estoque("filamento", fid, est_ini * peso_rolo, "Estoque inicial")
                            salvo("Filamento cadastrado!")
                            st.rerun()
        fil_opts = opcoes_filamentos()
        with c2:
            with st.expander("🛒 Registrar compra de filamento"):
                if fil_opts:
                    form_compra("filamento", fil_opts,
                                lambda f, q: f"{q:g} rolo(s) de {db.nome_filamento(f)}", "fil")
                else:
                    st.caption("Cadastre um filamento primeiro.")
        with c3:
            with st.expander("⚖️ Pesei o rolo (corrigir estoque)"):
                if fil_opts:
                    with st.form("form_ajuste_fil", clear_on_submit=True):
                        label = st.selectbox("Filamento", list(fil_opts))
                        real = st.number_input("Quanto tem de verdade agora? (g)", min_value=0.0, step=10.0,
                                               help="Peso do rolo na balança menos o carretel vazio (~200–250 g).")
                        if st.form_submit_button("Corrigir estoque", type="primary"):
                            f = fil_opts[label]
                            dif = real - (f["estoque_g"] or 0)
                            if dif:
                                db.ajustar_estoque("filamento", f["id"], dif, "Conferência (pesagem)")
                            salvo(f"Estoque de {db.nome_filamento(f)} ajustado para {real:.0f} g")
                            st.rerun()
                else:
                    st.caption("Cadastre um filamento primeiro.")

        if fils:
            df = pd.DataFrame([{
                "id": f["id"], "Material": f["material"], "Tipo": f.get("tipo") or "Simples",
                "Cor": f["cor"], "Marca": f["marca"] or "",
                "Preço rolo": f["preco_rolo"] or 0.0, "Peso rolo (g)": f["peso_rolo_g"] or 1000.0,
                "R$/kg": (f["preco_rolo"] or 0) / (f["peso_rolo_g"] or 1000) * 1000,
                "Em estoque (g)": f["estoque_g"] or 0.0,
                "Rolos": (f["estoque_g"] or 0) / (f["peso_rolo_g"] or 1000),
                "Mínimo (g)": f["estoque_minimo_g"] or 0.0,
                "Situação": "🔴 Comprar" if (f["estoque_g"] or 0) <= (f["estoque_minimo_g"] or 0) else "🟢 OK",
                "Obs": f["obs"] or "", "Ativo": bool(f["ativo"]), "Excluir?": False,
            } for f in fils])
            st.caption("O estoque muda sozinho com compras, produção e pedidos entregues. "
                       "Para corrigir, use **⚖️ Pesei o rolo**.")
            edit = st.data_editor(
                df, hide_index=True, use_container_width=True, key=f"fil_editor_{ev()}",
                disabled=["R$/kg", "Em estoque (g)", "Rolos", "Situação"],
                column_config={
                    "id": None,
                    "Material": st.column_config.SelectboxColumn(options=db.MATERIAIS),
                    "Tipo": st.column_config.SelectboxColumn(options=db.TIPOS_FILAMENTO, required=True),
                    "Preço rolo": st.column_config.NumberColumn(format=DINHEIRO, min_value=0),
                    "R$/kg": st.column_config.NumberColumn(format=DINHEIRO),
                    "Peso rolo (g)": st.column_config.NumberColumn(format="%.0f", min_value=1),
                    "Em estoque (g)": st.column_config.NumberColumn(format="%.0f"),
                    "Rolos": st.column_config.NumberColumn(format="%.2f"),
                    "Mínimo (g)": st.column_config.NumberColumn(format="%.0f", min_value=0),
                })
            if st.button("💾 Salvar filamentos", type="primary", key="fil_salvar"):
                aplicar_edicoes("filamentos", edit, lambda r: {
                    "material": _txt(r["Material"]) or "PLA", "tipo": _txt(r["Tipo"]) or "Simples",
                    "cor": _txt(r["Cor"]) or "?",
                    "marca": _txt(r["Marca"]), "preco_rolo": _num(r["Preço rolo"]),
                    "peso_rolo_g": _num(r["Peso rolo (g)"], 1000) or 1000,
                    "estoque_minimo_g": _num(r["Mínimo (g)"]), "obs": _txt(r["Obs"]),
                    "ativo": 1 if _bool(r["Ativo"]) else 0})
                salvo("Filamentos salvos!")
                st.rerun()

    # ---------- Insumos
    with tab_ins:
        st.caption("Tudo que não é filamento: embalagens, ímãs, argolas de chaveiro, tags, tintas, colas...")
        c1, c2, c3 = st.columns(3)
        with c1:
            with st.expander("➕ Cadastrar insumo"):
                with st.form("form_novo_ins", clear_on_submit=True):
                    nome = st.text_input("Nome *", placeholder="Ex.: Argola de chaveiro")
                    unidade = st.selectbox("Unidade", ["un", "pacote", "m", "ml", "g", "folha"])
                    custo_u = st.number_input("Custo por unidade (R$)", min_value=0.0, step=0.1)
                    est_ini = st.number_input("Quantidade que já tem", min_value=0.0, step=1.0)
                    minimo = st.number_input("Avisar quando tiver menos de", min_value=0.0, step=1.0)
                    if st.form_submit_button("Cadastrar", type="primary"):
                        if not nome.strip():
                            st.error("Informe o nome.")
                        else:
                            iid = db.inserir("insumos", {"nome": nome.strip(), "unidade": unidade,
                                                         "custo_unit": custo_u, "estoque": 0,
                                                         "estoque_minimo": minimo, "ativo": 1})
                            if est_ini > 0:
                                db.ajustar_estoque("insumo", iid, est_ini, "Estoque inicial")
                            salvo("Insumo cadastrado!")
                            st.rerun()
        ins_opts = {f"#{i['id']} {i['nome']}": i for i in db.listar("insumos", True)}
        with c2:
            with st.expander("🛒 Registrar compra de insumo"):
                if ins_opts:
                    form_compra("insumo", ins_opts, lambda i, q: f"{q:g} {i['unidade']} de {i['nome']}", "ins")
                else:
                    st.caption("Cadastre um insumo primeiro.")
        with c3:
            with st.expander("🔢 Contei (corrigir estoque)"):
                if ins_opts:
                    with st.form("form_ajuste_ins", clear_on_submit=True):
                        label = st.selectbox("Insumo", list(ins_opts))
                        real = st.number_input("Quantidade real agora", min_value=0.0, step=1.0)
                        motivo = st.text_input("Motivo", value="Conferência / uso")
                        if st.form_submit_button("Corrigir", type="primary"):
                            i = ins_opts[label]
                            dif = real - (i["estoque"] or 0)
                            if dif:
                                db.ajustar_estoque("insumo", i["id"], dif, motivo or "Conferência")
                            salvo("Estoque ajustado!")
                            st.rerun()
                else:
                    st.caption("Cadastre um insumo primeiro.")

        insumos = db.listar("insumos")
        if insumos:
            df = pd.DataFrame([{
                "id": i["id"], "Insumo": i["nome"], "Unidade": i["unidade"],
                "Custo un.": i["custo_unit"] or 0.0, "Em estoque": i["estoque"] or 0.0,
                "Mínimo": i["estoque_minimo"] or 0.0,
                "Situação": "🔴 Comprar" if (i["estoque_minimo"] or 0) > 0 and (i["estoque"] or 0) <= i["estoque_minimo"]
                else "🟢 OK",
                "Ativo": bool(i["ativo"]), "Excluir?": False,
            } for i in insumos])
            edit = st.data_editor(df, hide_index=True, use_container_width=True, key=f"ins_editor_{ev()}",
                                  disabled=["Em estoque", "Situação"],
                                  column_config={"id": None,
                                                 "Custo un.": st.column_config.NumberColumn(format=DINHEIRO)})
            if st.button("💾 Salvar insumos", type="primary", key="ins_salvar"):
                aplicar_edicoes("insumos", edit, lambda r: {
                    "nome": _txt(r["Insumo"]) or "?", "unidade": _txt(r["Unidade"]) or "un",
                    "custo_unit": _num(r["Custo un."]), "estoque_minimo": _num(r["Mínimo"]),
                    "ativo": 1 if _bool(r["Ativo"]) else 0})
                salvo("Insumos salvos!")
                st.rerun()

    # ---------- Pecas prontas
    with tab_prod:
        st.caption("Peças do catálogo já impressas, prontas para vender. Ao registrar uma produção, o filamento "
                   "é descontado. Ao entregar um pedido, as peças saem daqui (e se faltar, o filamento é "
                   "descontado na hora).")
        prods = db.listar("produtos", apenas_ativos=True)
        if not prods:
            st.info("Cadastre produtos em **🏷️ Produtos & Preços** primeiro.")
        else:
            prod_opts = {f"#{p['id']} {p['nome']}": p for p in prods}
            c1, c2 = st.columns(2)
            with c1:
                with st.form("form_producao", clear_on_submit=True):
                    st.markdown("##### 🖨️ Registrar produção")
                    label = st.selectbox("Produto", list(prod_opts))
                    qtd = st.number_input("Quantas peças ficaram prontas?", min_value=1, step=1, value=1)
                    if st.form_submit_button("Registrar", type="primary"):
                        p = prod_opts[label]
                        db.registrar_producao(p["id"], int(qtd))
                        usado = (p["gramas"] or 0) * qtd
                        salvo(f"{int(qtd)}x {p['nome']} no estoque" + (f" · {usado:.0f} g de filamento usados"
                                                                        if usado else ""))
                        st.rerun()
            with c2:
                with st.form("form_ajuste_prod", clear_on_submit=True):
                    st.markdown("##### 🔢 Contei as peças (corrigir)")
                    label = st.selectbox("Produto", list(prod_opts), key="aj_prod_sel")
                    real = st.number_input("Quantidade real", min_value=0, step=1)
                    if st.form_submit_button("Corrigir", type="primary"):
                        p = prod_opts[label]
                        dif = int(real) - int(p["estoque_pronto"] or 0)
                        if dif:
                            db.ajustar_estoque("produto", p["id"], dif, "Conferência")
                        salvo("Estoque de peças ajustado!")
                        st.rerun()
            df = pd.DataFrame([{
                "Produto": p["nome"], "Categoria": p["categoria"] or "", "Prontas": p["estoque_pronto"] or 0,
                "Mínimo": p["estoque_minimo"] or 0,
                "Situação": "🟡 Produzir" if (p["estoque_minimo"] or 0) > 0 and
                (p["estoque_pronto"] or 0) < p["estoque_minimo"] else "🟢 OK",
                "Valor de venda": (p["estoque_pronto"] or 0) * (p["preco_venda"] or 0),
            } for p in prods])
            st.dataframe(df, hide_index=True, use_container_width=True,
                         column_config={"Valor de venda": st.column_config.NumberColumn(format=DINHEIRO)})

    # ---------- Historico
    with tab_hist:
        movs = db.get_movimentos(300)
        if not movs:
            st.caption("Nenhuma movimentação ainda.")
        else:
            nomes = {("filamento", f["id"]): db.nome_filamento(f) for f in db.listar("filamentos")}
            nomes.update({("insumo", i["id"]): i["nome"] for i in db.listar("insumos")})
            nomes.update({("produto", p["id"]): p["nome"] for p in db.listar("produtos")})
            unid = {"filamento": "g", "insumo": "", "produto": "peça(s)"}
            icone = {"filamento": "🧵", "insumo": "🧰", "produto": "🎁"}
            st.dataframe(pd.DataFrame([{
                "Data": fmt_data(m["data"]),
                "Item": f"{icone[m['tipo_item']]} {nomes.get((m['tipo_item'], m['item_id']), '(excluído)')}",
                "Movimento": f"{'+' if m['qtd'] > 0 else ''}{m['qtd']:g} {unid[m['tipo_item']]}",
                "Motivo": m["motivo"],
            } for m in movs]), hide_index=True, use_container_width=True)


# =====================================================================
# 💰 Financeiro
# =====================================================================

def campos_pagamento(key, forma_padrao="Cartão de crédito", colunas=True):
    """Campos 'parcelas / 1o vencimento / forma' para usar dentro de um st.form."""
    cols = st.columns(3) if colunas else [st.container(), st.container(), st.container()]
    n = cols[0].number_input("Parcelas", min_value=1, max_value=48, step=1, value=1, key=f"{key}_parc",
                             help="1 = à vista")
    venc = cols[1].date_input("Vencimento da 1ª parcela", value=date.today(), format="DD/MM/YYYY",
                              key=f"{key}_venc",
                              help="No cartão: o vencimento da fatura em que cai a 1ª parcela. "
                                   "À vista: o dia do pagamento.")
    forma = cols[2].selectbox("Forma de pagamento", db.FORMAS_PAGAMENTO,
                              index=db.FORMAS_PAGAMENTO.index(forma_padrao), key=f"{key}_forma")
    return int(n), venc, forma


def texto_parcelas(total, n):
    if n <= 1:
        return f"à vista ({brl(total)})"
    base = round(total / n, 2)
    ultima = round(total - base * (n - 1), 2)
    return f"{n}x de {brl(base)}" + (f" (última {brl(ultima)})" if abs(ultima - base) >= 0.01 else "")


def situacao_vencimento(data_iso, pago):
    if pago:
        return "✅ Pago"
    venc = para_data(data_iso)
    hoje = date.today()
    if venc is None:
        return "⏳ A pagar"
    if venc < hoje:
        return f"⚠️ Vencida há {(hoje - venc).days}d"
    if venc == hoje:
        return "🔔 Vence hoje"
    return f"⏳ Vence em {(venc - hoje).days}d"


def pagina_financeiro():
    titulo("💰 Financeiro")
    tab_mes, tab_parc, tab_pagar = st.tabs(["📅 Movimento do mês", "💳 Compras parceladas", "📌 Contas a pagar"])
    with tab_mes:
        aba_movimento_mes()
    with tab_parc:
        aba_compras_parceladas()
    with tab_pagar:
        aba_contas_a_pagar()


def aba_movimento_mes():
    c1, _ = st.columns([1, 3])
    with c1:
        mes = seletor_mes("fin_mes")
    ini, fim = intervalo_mes(mes)
    lancs = db.listar_lancamentos(ini, fim)
    entradas = sum(l["valor"] for l in lancs if l["tipo"] == "entrada")
    saidas = sum(l["valor"] for l in lancs if l["tipo"] == "saida")
    em_parcelas = sum(l["valor"] for l in lancs if l["tipo"] == "saida" and l["parcelamento_id"])
    falta_pagar = sum(l["valor"] for l in lancs if l["tipo"] == "saida" and not l["pago"])
    linha_cards([
        ("Entradas", brl(entradas), VERDE, mes_label(mes)),
        ("Despesas", brl(saidas), VERMELHO,
         f"{brl(em_parcelas)} em parcelas" if em_parcelas else mes_label(mes)),
        ("Resultado", brl(entradas - saidas), VERDE if entradas >= saidas else VERMELHO, "entradas − despesas"),
        ("Falta pagar no mês", brl(falta_pagar), AMBAR, "contas e parcelas em aberto"),
        ("Saldo em caixa", brl(db.saldo_caixa()), ROXO, "só o que já entrou e já foi pago"),
    ])

    with st.expander("➕ Novo lançamento à vista", expanded=not lancs):
        tipo = st.radio("Tipo", ["Despesa (saída)", "Entrada"], horizontal=True, key="fin_tipo")
        eh_saida = tipo.startswith("Despesa")
        with st.form("form_lanc", clear_on_submit=True):
            l1, l2, l3 = st.columns(3)
            data_l = l1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            categoria = l2.selectbox("Categoria", db.CATEGORIAS_SAIDA if eh_saida else db.CATEGORIAS_ENTRADA)
            valor = l3.number_input("Valor (R$)", min_value=0.0, step=1.0)
            l4, l5, l6 = st.columns([2, 1, 1])
            descricao = l4.text_input("Descrição", placeholder="Ex.: DAS do MEI, anúncio no Instagram...")
            forma = l5.selectbox("Forma de pagamento", db.FORMAS_PAGAMENTO)
            with l6:
                st.write("")
                pago = st.checkbox("Já foi pago/recebido", value=True,
                                   help="Desmarque para uma conta que ainda vai vencer (ela aparece em Contas a pagar).")
            if st.form_submit_button("Lançar", type="primary"):
                if valor <= 0:
                    st.error("Informe um valor maior que zero.")
                else:
                    db.inserir_lancamento(data_l.isoformat(), "saida" if eh_saida else "entrada", categoria,
                                          descricao.strip(), valor, forma, USUARIO, pago)
                    salvo("Lançamento registrado!")
                    st.rerun()
        st.caption("💡 Comprou parcelado? Use a aba **💳 Compras parceladas**. Vendas entram sozinhas pelo "
                   "valor recebido no pedido, e compras de filamento/insumo pela tela de Estoque.")

    if not lancs:
        st.info(f"Nenhum lançamento em {mes_label(mes)}.")
        return

    st.markdown(f"#### Lançamentos de {mes_label(mes)}")
    todas_cat = list(dict.fromkeys(db.CATEGORIAS_SAIDA + db.CATEGORIAS_ENTRADA +
                                   [l["categoria"] for l in lancs if l["categoria"]]))

    def origem(l):
        if l["pedido_id"]:
            return f"Pedido #{l['pedido_id']}"
        if l["parcelamento_id"]:
            return f"Parcela {l['parcela_num']}/{l['parcela_total']}"
        return "Manual"

    df = pd.DataFrame([{
        "id": l["id"], "Data": para_data(l["data"]),
        "Tipo": "🟢 Entrada" if l["tipo"] == "entrada" else "🔴 Saída",
        "Categoria": l["categoria"], "Descrição": l["descricao"], "Valor": l["valor"],
        "Pagamento": l["forma_pagamento"] or "", "Pago": bool(l["pago"]), "Origem": origem(l),
        "Excluir?": False,
    } for l in lancs])
    edit = st.data_editor(
        df, hide_index=True, use_container_width=True, key=f"fin_editor_{mes}_{ev()}", disabled=["Origem"],
        column_config={
            "id": None,
            "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn(options=["🟢 Entrada", "🔴 Saída"]),
            "Categoria": st.column_config.SelectboxColumn(options=todas_cat),
            "Valor": st.column_config.NumberColumn(format=DINHEIRO, min_value=0),
            "Pagamento": st.column_config.SelectboxColumn(options=db.FORMAS_PAGAMENTO),
            "Pago": st.column_config.CheckboxColumn(help="Desmarcado = ainda vai pagar/receber"),
        })
    st.caption("Parcelas: dá para mudar data, valor (ex.: juros) e marcar como paga aqui; para apagar, "
               "exclua a compra inteira na aba 💳 Compras parceladas.")
    if st.button("💾 Salvar lançamentos", type="primary", key="fin_salvar"):
        ignorados = 0
        por_id = {l["id"]: l for l in lancs}
        for _, r in edit.iterrows():
            rid = int(r["id"])
            orig = por_id[rid]
            d = r["Data"]
            nova_data = orig["data"] if d is None or pd.isna(d) else pd.to_datetime(d).date().isoformat()
            if orig["pedido_id"]:
                # Recebimento de pedido: so muda pelo proprio pedido
                if _bool(r["Excluir?"]) or _num(r["Valor"]) != orig["valor"]:
                    ignorados += 1
                continue
            if orig["parcelamento_id"]:
                if _bool(r["Excluir?"]):
                    ignorados += 1
                db.atualizar_lancamento(rid, {"data": nova_data, "valor": abs(_num(r["Valor"])),
                                              "pago": 1 if _bool(r["Pago"]) else 0,
                                              "forma_pagamento": _txt(r["Pagamento"])})
                continue
            if _bool(r["Excluir?"]):
                db.excluir_lancamento(rid)
                continue
            db.atualizar_lancamento(rid, {
                "data": nova_data,
                "tipo": "entrada" if "Entrada" in _txt(r["Tipo"]) else "saida",
                "categoria": _txt(r["Categoria"]), "descricao": _txt(r["Descrição"]),
                "valor": abs(_num(r["Valor"])), "forma_pagamento": _txt(r["Pagamento"]),
                "pago": 1 if _bool(r["Pago"]) else 0,
            })
        if ignorados:
            st.session_state["fin_aviso"] = (f"{ignorados} alteração(ões) não foram feitas: recebimentos de pedidos "
                                             "mudam pelo pedido, e parcelas são excluídas pela compra parcelada.")
        salvo("Lançamentos salvos!")
        st.rerun()
    if "fin_aviso" in st.session_state:
        st.warning(st.session_state.pop("fin_aviso"))

    desp = {}
    for l in lancs:
        if l["tipo"] == "saida":
            desp[l["categoria"] or "Outros"] = desp.get(l["categoria"] or "Outros", 0) + l["valor"]
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("#### 🧾 Despesas por categoria")
        if desp:
            itens = sorted(desp.items(), key=lambda x: x[1])
            fig = go.Figure(go.Bar(x=[v for _, v in itens], y=[c for c, _ in itens], orientation="h",
                                   marker_color=ROSA, text=[brl(v) for _, v in itens], textposition="auto"))
            fig.update_layout(xaxis_tickprefix="R$ ", showlegend=False)
            st.plotly_chart(layout_grafico(fig, 300), key="graf_fin_cat")
        else:
            st.caption("Sem despesas neste mês.")
    with g2:
        st.markdown("#### 📈 Últimos 12 meses")
        res = db.resumo_mensal(12)
        if res:
            dfr = pd.DataFrame(res)
            dfr["Mês"] = dfr["mes"].map(mes_label)
            fig = go.Figure()
            fig.add_bar(x=dfr["Mês"], y=dfr["entradas"], name="Entradas", marker_color=VERDE)
            fig.add_bar(x=dfr["Mês"], y=dfr["saidas"], name="Despesas", marker_color=VERMELHO)
            fig.update_layout(barmode="group", yaxis_tickprefix="R$ ")
            st.plotly_chart(layout_grafico(fig, 300), key="graf_fin_mensal")


def aba_compras_parceladas():
    compras = db.listar_parcelamentos()
    ativas = [p for p in compras if p["proxima"]]
    mes_atual = date.today().strftime("%Y-%m")
    neste_mes = sum(l["valor"] for p in compras for l in p["parcelas"] if l["data"][:7] == mes_atual)
    linha_cards([
        ("Compras em andamento", str(len(ativas)), AZUL, f"{len(compras) - len(ativas)} já quitada(s)"),
        ("Falta pagar", brl(sum(p["valor_restante"] for p in compras)), VERMELHO, "soma das parcelas em aberto"),
        ("Parcelas deste mês", brl(neste_mes), ROSA, mes_label(mes_atual)),
        ("Já pago", brl(sum(p["valor_pago"] for p in compras)), VERDE, "parcelas quitadas"),
    ])

    with st.expander("➕ Registrar compra parcelada", expanded=not compras):
        st.caption("Ex.: a impressora em 10x no cartão. Cada parcela entra como despesa no mês em que vence, "
                   "e as futuras ficam em **📌 Contas a pagar**.")
        with st.form("form_parcelada", clear_on_submit=True):
            f1, f2 = st.columns([2, 1])
            descricao = f1.text_input("O que foi comprado *", placeholder="Ex.: Impressora Bambu A1")
            fornecedor = f2.text_input("Loja / fornecedor", placeholder="Ex.: Mercado Livre")
            f3, f4, f5 = st.columns(3)
            categoria = f3.selectbox("Categoria", db.CATEGORIAS_SAIDA,
                                     index=db.CATEGORIAS_SAIDA.index("Equipamentos"))
            valor = f4.number_input("Valor total (R$)", min_value=0.0, step=10.0,
                                    help="O total que vai pagar somando todas as parcelas (com juros, se tiver).")
            data_compra = f5.date_input("Data da compra", value=date.today(), format="DD/MM/YYYY")
            n, venc, forma = campos_pagamento("parc_fin")
            if st.form_submit_button("Registrar compra", type="primary"):
                if not descricao.strip() or valor <= 0:
                    st.error("Preencha o que foi comprado e o valor total.")
                else:
                    db.registrar_despesa(descricao.strip(), categoria, valor, n, venc.isoformat(),
                                         data_compra.isoformat(), forma, fornecedor.strip(), USUARIO)
                    salvo(f"{descricao.strip()}: {texto_parcelas(valor, n)}")
                    st.rerun()

    if not compras:
        st.info("Nenhuma compra parcelada registrada.")
        return

    so_ativas = st.toggle("Mostrar só as que ainda têm parcelas", value=True, key="parc_so_ativas")
    lista = ativas if so_ativas else compras
    if lista:
        st.dataframe(pd.DataFrame([{
            "Compra": p["descricao"], "Loja": p["fornecedor"] or "", "Categoria": p["categoria"],
            "Data": fmt_data(p["data_compra"]), "Total": p["valor_total"],
            "Parcelas": f"{p['pagas']}/{p['n_parcelas']} pagas",
            "Progresso": 100 * p["pagas"] / p["n_parcelas"] if p["n_parcelas"] else 100.0,
            "Falta pagar": p["valor_restante"],
            "Próxima": (f"{fmt_data(p['proxima']['data'])} · {brl(p['proxima']['valor'])}"
                        if p["proxima"] else "✅ Quitada"),
            "Forma": p["forma_pagamento"] or "",
        } for p in lista]), hide_index=True, use_container_width=True, column_config={
            "Total": st.column_config.NumberColumn(format=DINHEIRO),
            "Falta pagar": st.column_config.NumberColumn(format=DINHEIRO),
            "Progresso": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
        })
    else:
        st.success("Todas as compras parceladas estão quitadas! 🎉")

    st.markdown("#### 🔎 Parcelas de uma compra")
    opts = {f"#{p['id']} {p['descricao']} — {texto_parcelas(p['valor_total'], p['n_parcelas'])}": p
            for p in compras}
    sel = st.selectbox("Compra", list(opts), key="parc_sel")
    p = opts[sel]
    df = pd.DataFrame([{
        "id": l["id"], "Parcela": f"{l['parcela_num']}/{l['parcela_total']}", "Vencimento": para_data(l["data"]),
        "Valor": l["valor"], "Pago": bool(l["pago"]), "Situação": situacao_vencimento(l["data"], l["pago"]),
    } for l in p["parcelas"]])
    edit = st.data_editor(df, hide_index=True, use_container_width=True, key=f"parc_editor_{p['id']}_{ev()}",
                          disabled=["Parcela", "Situação"],
                          column_config={"id": None,
                                         "Vencimento": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                         "Valor": st.column_config.NumberColumn(format=DINHEIRO, min_value=0)})
    b1, b2 = st.columns([1, 3])
    if b1.button("💾 Salvar parcelas", type="primary", key=f"parc_salvar_{p['id']}"):
        orig = {l["id"]: l for l in p["parcelas"]}
        for _, r in edit.iterrows():
            rid = int(r["id"])
            d = r["Vencimento"]
            db.atualizar_lancamento(rid, {
                "data": orig[rid]["data"] if d is None or pd.isna(d) else pd.to_datetime(d).date().isoformat(),
                "valor": abs(_num(r["Valor"])), "pago": 1 if _bool(r["Pago"]) else 0})
        salvo("Parcelas salvas!")
        st.rerun()
    with b2.expander("🗑️ Excluir esta compra"):
        st.caption("Apaga a compra e todas as parcelas dela do Financeiro (inclusive as já pagas). "
                   "Use se lançou errado.")
        conf = st.checkbox("Sim, excluir a compra e as parcelas", key=f"parc_del_conf_{p['id']}")
        if st.button("Excluir compra", disabled=not conf, key=f"parc_del_{p['id']}"):
            db.excluir_parcelamento(p["id"])
            salvo("Compra parcelada excluída")
            st.rerun()


def aba_contas_a_pagar():
    contas = db.contas_a_pagar()
    hoje = date.today()
    vencidas = [l for l in contas if para_data(l["data"]) and para_data(l["data"]) <= hoje]
    prox30 = [l for l in contas if para_data(l["data"]) and hoje < para_data(l["data"]) <= hoje + timedelta(days=30)]
    linha_cards([
        ("Vencidas / vencem hoje", brl(sum(l["valor"] for l in vencidas)), VERMELHO, f"{len(vencidas)} conta(s)"),
        ("Próximos 30 dias", brl(sum(l["valor"] for l in prox30)), AMBAR, f"{len(prox30)} conta(s)"),
        ("Total a pagar", brl(sum(l["valor"] for l in contas)), AZUL, "inclui parcelas futuras"),
    ])
    if not contas:
        st.success("Nenhuma conta em aberto. 🎉")
        return

    if vencidas:
        st.caption("Pagou no cartão ou débito automático? Marque de uma vez as que já venceram:")
        if st.button(f"✅ Marcar as {len(vencidas)} vencida(s) como pagas", key="pagar_vencidas"):
            n = db.marcar_vencidas_pagas()
            salvo(f"{n} conta(s) marcada(s) como paga(s)")
            st.rerun()

    st.markdown("#### 📋 Em aberto")
    df = pd.DataFrame([{
        "id": l["id"], "Vencimento": fmt_data(l["data"]), "Situação": situacao_vencimento(l["data"], False),
        "Descrição": l["descricao"], "Categoria": l["categoria"], "Valor": l["valor"],
        "Forma": l["forma_pagamento"] or "", "Pago": False,
    } for l in contas])
    edit = st.data_editor(df, hide_index=True, use_container_width=True, key=f"pagar_editor_{ev()}",
                          disabled=["Vencimento", "Situação", "Descrição", "Categoria", "Valor", "Forma"],
                          column_config={"id": None, "Valor": st.column_config.NumberColumn(format=DINHEIRO),
                                         "Pago": st.column_config.CheckboxColumn(help="Marque o que já pagou")})
    if st.button("💾 Salvar pagamentos", type="primary", key="pagar_salvar"):
        ids = [int(r["id"]) for _, r in edit.iterrows() if _bool(r["Pago"])]
        if ids:
            db.marcar_pago(ids)
            salvo(f"{len(ids)} conta(s) paga(s)!")
        st.rerun()

    st.markdown("#### 📆 Compromissos por mês")
    proj = db.projecao_a_pagar()
    dfp = pd.DataFrame(proj)
    dfp["Mês"] = dfp["mes"].map(mes_label)
    fig = go.Figure(go.Bar(x=dfp["Mês"], y=dfp["valor"], marker_color=LARANJA,
                           text=[brl(v) for v in dfp["valor"]], textposition="auto"))
    fig.update_layout(yaxis_tickprefix="R$ ", showlegend=False)
    st.plotly_chart(layout_grafico(fig, 300), key="graf_a_pagar")


# =====================================================================
# ⚙️ Configuracoes
# =====================================================================

def exportar_excel():
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nome, linhas in db.exportar_tabelas().items():
            pd.DataFrame(linhas).to_excel(w, sheet_name=nome[:31], index=False)
    return buf.getvalue()


def pagina_config():
    titulo("⚙️ Configurações")
    cfg = db.get_config()

    st.markdown("#### 💡 Custos usados na precificação")
    with st.form("form_cfg"):
        c1, c2, c3 = st.columns(3)
        kwh = c1.number_input("Preço do kWh (R$)", min_value=0.0, step=0.05, value=float(cfg["custo_kwh"]),
                              help="Na conta de luz: valor total ÷ kWh consumidos.")
        hora = c2.number_input("Valor da hora de trabalho (R$)", min_value=0.0, step=1.0,
                               value=float(cfg["hora_trabalho"]))
        margem = c3.number_input("Margem de lucro padrão (%)", min_value=0.0, step=10.0,
                                 value=float(cfg["margem_padrao"]))
        c4, c5 = st.columns(2)
        falha = c4.number_input("Material extra para falhas/suportes (%)", min_value=0.0, step=1.0,
                                value=float(cfg["taxa_falha"]))
        taxa = c5.number_input("Taxa de venda padrão (%)", min_value=0.0, max_value=90.0, step=1.0,
                               value=float(cfg["taxa_venda"]),
                               help="Maquininha ou marketplace. Use 0 se vendem mais por Pix.")
        st.markdown("**🧵 Preço médio do filamento** (usado no custo de todas as peças)")
        c6, c7 = st.columns(2)
        kg_s = c6.number_input("Simples (R$ por kg)", min_value=0.0, step=5.0,
                               value=float(cfg["preco_kg_simples"]),
                               help="PLA e PETG comuns. Use 0 para o app calcular a média dos filamentos cadastrados.")
        kg_e = c7.number_input("Especial (R$ por kg)", min_value=0.0, step=5.0,
                               value=float(cfg["preco_kg_especial"]),
                               help="Silk, velvet, glitter, TPU... Use 0 para a média automática dos especiais.")
        _med = {t: [f["preco_rolo"] / f["peso_rolo_g"] * 1000 for f in db.listar("filamentos", True)
                    if (f.get("tipo") or "Simples") == t and (f["preco_rolo"] or 0) > 0
                    and (f["peso_rolo_g"] or 0) > 0]
                for t in db.TIPOS_FILAMENTO}
        st.caption("Para comparar, a média real dos rolos cadastrados hoje: "
                   + " · ".join(f"{t} {brl(sum(v) / len(v))}/kg ({len(v)} filamento(s))" if v else f"{t}: nenhum"
                                for t, v in _med.items()))
        if st.form_submit_button("💾 Salvar custos", type="primary"):
            db.set_config({"custo_kwh": kwh, "hora_trabalho": hora, "margem_padrao": margem,
                           "taxa_falha": falha, "taxa_venda": taxa,
                           "preco_kg_simples": kg_s, "preco_kg_especial": kg_e})
            salvo("Custos atualizados!")
            st.rerun()

    st.markdown("#### 🖨️ Impressoras")
    with st.expander("➕ Cadastrar impressora", expanded=not db.listar("impressoras")):
        with st.form("form_imp", clear_on_submit=True):
            i1, i2 = st.columns(2)
            nome = i1.text_input("Nome *", placeholder="Ex.: Bambu A1, Ender 3 V3")
            pot = i2.number_input("Consumo médio (W)", min_value=0.0, step=10.0, value=150.0,
                                  help="Uma impressora FDM comum gasta ~100–200 W em média imprimindo PLA.")
            i3, i4 = st.columns(2)
            valor = i3.number_input("Quanto pagaram (R$)", min_value=0.0, step=100.0)
            vida = i4.number_input("Vida útil estimada (horas)", min_value=1.0, step=500.0, value=5000.0,
                                   help="Usado para dividir o valor da máquina entre as peças (desgaste).")
            st.markdown("**Pagamento da impressora**")
            i5, i6 = st.columns(2)
            data_compra = i5.date_input("Data da compra", value=date.today(), format="DD/MM/YYYY", key="imp_data")
            with i6:
                st.write("")
                lancar = st.checkbox("Lançar a compra no Financeiro", value=True, key="imp_lancar",
                                     help="Desmarque se já registrou em Financeiro → Compras parceladas.")
            n_parc, venc, forma = campos_pagamento("imp")
            if st.form_submit_button("Cadastrar", type="primary"):
                if not nome.strip():
                    st.error("Informe o nome.")
                else:
                    db.inserir("impressoras", {"nome": nome.strip(), "potencia_w": pot, "valor_compra": valor,
                                               "vida_util_horas": vida, "ativa": 1})
                    msg = "Impressora cadastrada!"
                    if lancar and valor > 0:
                        db.registrar_despesa(f"Impressora {nome.strip()}", "Equipamentos", valor, n_parc,
                                             venc.isoformat(), data_compra.isoformat(), forma, usuario=USUARIO)
                        msg = f"Impressora cadastrada · compra lançada: {texto_parcelas(valor, n_parc)}"
                    salvo(msg)
                    st.rerun()
    imps = db.listar("impressoras")
    if imps:
        df = pd.DataFrame([{
            "id": i["id"], "Impressora": i["nome"], "Consumo (W)": i["potencia_w"] or 0.0,
            "Valor pago": i["valor_compra"] or 0.0, "Vida útil (h)": i["vida_util_horas"] or 5000.0,
            "Desgaste por hora": (i["valor_compra"] or 0) / (i["vida_util_horas"] or 5000),
            "Ativa": bool(i["ativa"]), "Excluir?": False,
        } for i in imps])
        edit = st.data_editor(df, hide_index=True, use_container_width=True, key=f"imp_editor_{ev()}",
                              disabled=["Desgaste por hora"],
                              column_config={"id": None,
                                             "Valor pago": st.column_config.NumberColumn(format=DINHEIRO),
                                             "Desgaste por hora": st.column_config.NumberColumn(format=DINHEIRO)})
        if st.button("💾 Salvar impressoras", type="primary", key="imp_salvar"):
            aplicar_edicoes("impressoras", edit, lambda r: {
                "nome": _txt(r["Impressora"]) or "Impressora", "potencia_w": _num(r["Consumo (W)"]),
                "valor_compra": _num(r["Valor pago"]), "vida_util_horas": _num(r["Vida útil (h)"], 5000) or 5000,
                "ativa": 1 if _bool(r["Ativa"]) else 0})
            salvo("Impressoras salvas!")
            st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 📥 Exportar tudo para Excel")
        st.caption("Uma planilha com todas as tabelas — bom como backup ou para o contador.")
        st.download_button("Baixar planilha", data=exportar_excel(),
                           file_name=f"borboleta_{date.today().isoformat()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c2:
        st.markdown("#### ☁️ Nuvem")
        if not is_cloud():
            st.caption("Rodando no computador — os dados ficam em `data/borboleta.db`.")
        else:
            status = get_last_sync_status()
            if status.get("ok"):
                st.success(f"Última sincronização: {status.get('msg')}")
            elif status.get("ok") is False:
                st.error(f"Sync falhou: {status.get('msg')}")
            if st.button("🔍 Diagnosticar conexão", key="diag"):
                for ok, texto in diagnostico():
                    st.markdown(f"{'✅' if ok else '❌'} {texto}")
            if st.button("🔄 Recarregar da nuvem e importar cargas", key="reimportar",
                         help="Puxa os dados da nuvem de novo e aplica as cargas que estiverem esperando."):
                pull_database()
                db.init_db()
                msgs = importar_pendentes(db.aplicar_importacao)
                st.session_state["importacao_msgs"] = msgs or ["Nenhuma carga nova foi importada."]
                st.rerun()
            if st.button("Forçar salvar na nuvem agora"):
                salvo("Dados enviados para a nuvem!")

    st.markdown("#### 🔒 Últimos acessos")
    acessos = db.get_acessos(10)
    if acessos:
        st.dataframe(pd.DataFrame([{"Quem": a["usuario"], "Quando": a["quando"]} for a in acessos]),
                     hide_index=True)


# =====================================================================
# Roteamento
# =====================================================================

for _msg in st.session_state.pop("importacao_msgs", None) or []:
    (st.error if _msg.startswith("Erro") else st.success)(f"📥 {_msg}")

{
    PG_INICIO: pagina_inicio,
    PG_PEDIDOS: pagina_pedidos,
    PG_CLIENTES: pagina_clientes,
    PG_PRODUTOS: pagina_produtos,
    PG_ESTOQUE: pagina_estoque,
    PG_FINANCEIRO: pagina_financeiro,
    PG_CONFIG: pagina_config,
}[st.session_state.pagina]()
