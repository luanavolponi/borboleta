# -*- coding: utf-8 -*-
"""
Banco de dados (SQLite) do app Borboleta Estudio Criativo.
Estoque de filamentos/insumos/produtos, clientes, pedidos e financeiro.
"""
import calendar
import os
import sqlite3
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "borboleta.db")

STATUS_PEDIDO = ["Orçamento", "Confirmado", "Produzindo", "Pronto", "Entregue", "Cancelado"]
STATUS_ABERTOS = ["Confirmado", "Produzindo", "Pronto"]
CANAIS = ["Instagram", "WhatsApp", "Shopee", "Mercado Livre", "Elo7", "Feira/Evento", "Indicação", "Outro"]
FORMAS_PAGAMENTO = ["Pix", "Dinheiro", "Cartão de crédito", "Cartão de débito", "Boleto", "Marketplace", "Outro"]
MATERIAIS = ["PLA", "PLA Silk", "PETG", "ABS", "TPU", "Resina", "Outro"]
TIPOS_FILAMENTO = ["Simples", "Especial"]
MATERIAIS_ESPECIAIS = {"PLA Silk", "TPU", "Resina"}  # sugestao de tipo no cadastro
CATEGORIAS_ENTRADA = ["Venda", "Aporte dos sócios", "Outros"]
CATEGORIAS_SAIDA = [
    "Filamento", "Insumos", "Embalagem", "Equipamentos", "Manutenção", "Energia",
    "Frete", "Marketing", "Taxas/Marketplace", "Juros e tarifas", "Impostos (MEI)", "Pró-labore", "Outros",
]
# Analise de investimento: depois da 1a venda, so estas categorias contam como investimento
CATEGORIAS_INVESTIMENTO = ["Equipamentos"]
# Custos que existem mesmo sem vender (base do ponto de equilibrio)
CATEGORIAS_FIXAS = ["Energia", "Marketing", "Impostos (MEI)", "Pró-labore", "Manutenção", "Juros e tarifas", "Outros"]
# Entradas que sao receita do negocio (aporte dos socios nao e faturamento)
CATEGORIAS_RECEITA = ["Venda", "Outros"]

CONFIG_PADRAO = {
    "custo_kwh": 0.95,           # R$ por kWh (conta de luz)
    "hora_trabalho": 25.0,       # R$ por hora de trabalho manual (acabamento, embalar...)
    "margem_padrao": 100.0,      # % de lucro sobre o custo
    "taxa_falha": 10.0,          # % extra de material para cobrir falhas/suportes
    "taxa_venda": 0.0,           # % de taxa da maquininha/marketplace
    "preco_kg_simples": 115.0,   # R$/kg p/ filamentos simples, definido pela Luana (0 = media automatica)
    "preco_kg_especial": 150.0,  # R$/kg p/ filamentos especiais, definido pela Luana (0 = media automatica)
    "custos_fixos_mensais": 0.0, # R$/mes p/ ponto de equilibrio (0 = media das despesas fixas dos ultimos 3 meses)
    "inicio_vendas": 0.0,        # data (ordinal) que separa investimento inicial de operacao (0 = 1a venda)
}


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


def _hoje():
    return date.today().isoformat()


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor REAL
        );
        CREATE TABLE IF NOT EXISTS impressoras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            potencia_w REAL DEFAULT 150,
            valor_compra REAL DEFAULT 0,
            vida_util_horas REAL DEFAULT 5000,
            ativa INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS filamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material TEXT NOT NULL,
            cor TEXT NOT NULL,
            marca TEXT DEFAULT '',
            preco_rolo REAL DEFAULT 0,
            peso_rolo_g REAL DEFAULT 1000,
            estoque_g REAL DEFAULT 0,
            estoque_minimo_g REAL DEFAULT 300,
            obs TEXT DEFAULT '',
            ativo INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS insumos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            unidade TEXT DEFAULT 'un',
            custo_unit REAL DEFAULT 0,
            estoque REAL DEFAULT 0,
            estoque_minimo REAL DEFAULT 0,
            ativo INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT DEFAULT '',
            filamento_id INTEGER REFERENCES filamentos(id) ON DELETE SET NULL,
            impressora_id INTEGER REFERENCES impressoras(id) ON DELETE SET NULL,
            gramas REAL DEFAULT 0,
            horas_impressao REAL DEFAULT 0,
            minutos_trabalho REAL DEFAULT 0,
            custo_extra REAL DEFAULT 0,
            margem_pct REAL,
            preco_venda REAL DEFAULT 0,
            estoque_pronto INTEGER DEFAULT 0,
            estoque_minimo INTEGER DEFAULT 0,
            obs TEXT DEFAULT '',
            ativo INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT DEFAULT '',
            instagram TEXT DEFAULT '',
            email TEXT DEFAULT '',
            cidade TEXT DEFAULT '',
            obs TEXT DEFAULT '',
            criado_em TEXT
        );
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
            data TEXT NOT NULL,
            prazo TEXT,
            status TEXT DEFAULT 'Confirmado',
            canal TEXT DEFAULT '',
            forma_pagamento TEXT DEFAULT '',
            desconto REAL DEFAULT 0,
            frete REAL DEFAULT 0,
            valor_recebido REAL DEFAULT 0,
            estoque_baixado INTEGER DEFAULT 0,
            obs TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS pedido_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
            produto_id INTEGER REFERENCES produtos(id) ON DELETE SET NULL,
            descricao TEXT NOT NULL,
            qtd INTEGER DEFAULT 1,
            preco_unit REAL DEFAULT 0,
            custo_unit REAL DEFAULT 0,
            filamento_id INTEGER REFERENCES filamentos(id) ON DELETE SET NULL,
            gramas_unit REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS movimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo_item TEXT NOT NULL,          -- filamento | insumo | produto
            item_id INTEGER NOT NULL,
            qtd REAL NOT NULL,                -- positivo = entrada, negativo = saida
            motivo TEXT DEFAULT '',
            pedido_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('entrada','saida')),
            categoria TEXT DEFAULT '',
            descricao TEXT DEFAULT '',
            valor REAL NOT NULL,
            forma_pagamento TEXT DEFAULT '',
            pedido_id INTEGER,
            criado_por TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS compras_parceladas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_compra TEXT NOT NULL,
            descricao TEXT NOT NULL,
            fornecedor TEXT DEFAULT '',
            categoria TEXT DEFAULT '',
            valor_total REAL NOT NULL,
            n_parcelas INTEGER NOT NULL,
            primeiro_vencimento TEXT NOT NULL,
            forma_pagamento TEXT DEFAULT '',
            criado_por TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS produto_fotos (
            produto_id INTEGER PRIMARY KEY REFERENCES produtos(id) ON DELETE CASCADE,
            foto BLOB NOT NULL,                -- JPEG reduzido (~700 px)
            miniatura BLOB NOT NULL,           -- JPEG ~160 px para tabelas
            atualizado_em TEXT
        );
        CREATE TABLE IF NOT EXISTS despesas_fixas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            categoria TEXT DEFAULT 'Outros',
            valor REAL NOT NULL,
            dia_vencimento INTEGER DEFAULT 10,
            forma_pagamento TEXT DEFAULT '',
            inicio TEXT NOT NULL,              -- 1o mes de vencimento (YYYY-MM)
            ativo INTEGER DEFAULT 1,
            criado_por TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS despesas_fixas_geradas (
            fixa_id INTEGER NOT NULL,
            mes TEXT NOT NULL,                 -- YYYY-MM ja lancado (mesmo que depois excluido)
            PRIMARY KEY (fixa_id, mes)
        );
        CREATE TABLE IF NOT EXISTS importacoes (
            id TEXT PRIMARY KEY,
            quando TEXT,
            resumo TEXT
        );
        CREATE TABLE IF NOT EXISTS acessos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            quando TEXT
        );
        """)
        # Migracoes: colunas novas em bancos ja existentes
        for tabela, col, tipo in [("filamentos", "tipo", "TEXT DEFAULT 'Simples'"),
                                  ("produtos", "tipo_filamento", "TEXT"),
                                  # Endereco do cliente (cidade ja existia)
                                  ("clientes", "cep", "TEXT DEFAULT ''"), ("clientes", "endereco", "TEXT DEFAULT ''"),
                                  ("clientes", "numero", "TEXT DEFAULT ''"),
                                  ("clientes", "complemento", "TEXT DEFAULT ''"),
                                  ("clientes", "bairro", "TEXT DEFAULT ''"), ("clientes", "uf", "TEXT DEFAULT ''")]:
            if col not in {r["name"] for r in c.execute(f"PRAGMA table_info({tabela})")}:
                c.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(lancamentos)")}
        for col, tipo in [("pago", "INTEGER DEFAULT 1"), ("parcelamento_id", "INTEGER"),
                          ("parcela_num", "INTEGER"), ("parcela_total", "INTEGER"),
                          ("data_compra", "TEXT"),  # data em que a despesa foi feita (data = vencimento)
                          ("fixa_id", "INTEGER")]:  # lancamento gerado por uma despesa fixa mensal
            if col not in cols:
                c.execute(f"ALTER TABLE lancamentos ADD COLUMN {col} {tipo}")
        for k, v in CONFIG_PADRAO.items():
            c.execute("INSERT OR IGNORE INTO config(chave, valor) VALUES (?, ?)", (k, v))


# ---------------------------------------------------------------- config

def get_config():
    with _conn() as c:
        cfg = dict(CONFIG_PADRAO)
        cfg.update({r["chave"]: r["valor"] for r in c.execute("SELECT * FROM config")})
        return cfg


def set_config(valores):
    with _conn() as c:
        for k, v in valores.items():
            c.execute("INSERT OR REPLACE INTO config(chave, valor) VALUES (?, ?)", (k, float(v)))


def registrar_acesso(usuario):
    with _conn() as c:
        c.execute("INSERT INTO acessos(usuario, quando) VALUES (?, ?)",
                  (usuario, datetime.now().strftime("%Y-%m-%d %H:%M")))


def get_acessos(limite=10):
    with _conn() as c:
        return _rows(c.execute("SELECT * FROM acessos ORDER BY id DESC LIMIT ?", (limite,)))


# ---------------------------------------------------------------- tabelas simples (CRUD generico)

_COLUNAS = {
    "impressoras": ["nome", "potencia_w", "valor_compra", "vida_util_horas", "ativa"],
    "filamentos": ["material", "cor", "marca", "preco_rolo", "peso_rolo_g", "estoque_g",
                   "estoque_minimo_g", "obs", "ativo", "tipo"],
    "insumos": ["nome", "unidade", "custo_unit", "estoque", "estoque_minimo", "ativo"],
    "produtos": ["nome", "categoria", "filamento_id", "impressora_id", "gramas", "horas_impressao",
                 "minutos_trabalho", "custo_extra", "margem_pct", "preco_venda", "estoque_pronto",
                 "estoque_minimo", "obs", "ativo", "tipo_filamento"],
    "clientes": ["nome", "telefone", "instagram", "email", "cidade", "obs",
                 "cep", "endereco", "numero", "complemento", "bairro", "uf"],
}


def listar(tabela, apenas_ativos=False):
    assert tabela in _COLUNAS
    sql = f"SELECT * FROM {tabela}"
    if apenas_ativos and tabela != "clientes":
        campo = "ativa" if tabela == "impressoras" else "ativo"
        sql += f" WHERE {campo} = 1"
    ordem = {"filamentos": "material, cor", "clientes": "nome COLLATE NOCASE"}.get(tabela, "nome COLLATE NOCASE")
    with _conn() as c:
        return _rows(c.execute(sql + f" ORDER BY {ordem}"))


def obter(tabela, item_id):
    assert tabela in _COLUNAS
    with _conn() as c:
        r = c.execute(f"SELECT * FROM {tabela} WHERE id = ?", (item_id,)).fetchone()
        return dict(r) if r else None


def inserir(tabela, dados):
    assert tabela in _COLUNAS
    dados = {k: v for k, v in dados.items() if k in _COLUNAS[tabela]}
    if tabela == "clientes":
        dados["criado_em"] = _hoje()
    cols = ", ".join(dados)
    marks = ", ".join("?" for _ in dados)
    with _conn() as c:
        cur = c.execute(f"INSERT INTO {tabela} ({cols}) VALUES ({marks})", list(dados.values()))
        return cur.lastrowid


def atualizar(tabela, item_id, dados):
    assert tabela in _COLUNAS
    dados = {k: v for k, v in dados.items() if k in _COLUNAS[tabela]}
    if not dados:
        return
    sets = ", ".join(f"{k} = ?" for k in dados)
    with _conn() as c:
        c.execute(f"UPDATE {tabela} SET {sets} WHERE id = ?", list(dados.values()) + [item_id])


def excluir(tabela, item_id):
    assert tabela in _COLUNAS
    with _conn() as c:
        c.execute(f"DELETE FROM {tabela} WHERE id = ?", (item_id,))


UFS = ["", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE",
       "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]


def endereco_formatado(cli):
    """'Rua X, 123 - apto 4 - Bairro - Cidade/UF - CEP 00000-000' (so com as partes preenchidas)."""
    if not cli:
        return ""
    g = lambda k: (cli.get(k) or "").strip()  # noqa: E731
    rua = ", ".join(p for p in (g("endereco"), g("numero")) if p)
    cidade = "/".join(p for p in (g("cidade"), g("uf")) if p)
    cep = re_digitos(g("cep"))
    cep = f"CEP {cep[:5]}-{cep[5:]}" if len(cep) == 8 else (f"CEP {g('cep')}" if g("cep") else "")
    return " - ".join(p for p in (rua, g("complemento"), g("bairro"), cidade, cep) if p)


def re_digitos(texto):
    return "".join(ch for ch in (texto or "") if ch.isdigit())


def nome_filamento(f):
    if not f:
        return "—"
    marca = f" ({f['marca']})" if f.get("marca") else ""
    return f"{f['material']} {f['cor']}{marca}"


# ---------------------------------------------------------------- precificacao

def medias_filamento(cfg=None):
    """Preco por kg usado nos custos, por tipo: {"Simples": {...}, "Especial": {...}}.

    Cada tipo usa o valor fixo das Configuracoes (se > 0) ou a media simples do R$/kg dos
    filamentos ativos daquele tipo. Tipo sem filamento cadastrado usa a media do outro.
    """
    cfg = cfg or get_config()
    with _conn() as c:
        fils = _rows(c.execute("""SELECT COALESCE(tipo, 'Simples') AS tipo, preco_rolo, peso_rolo_g
                                  FROM filamentos WHERE ativo=1 AND preco_rolo > 0 AND peso_rolo_g > 0"""))
    out = {}
    for t in TIPOS_FILAMENTO:
        precos = [f["preco_rolo"] / f["peso_rolo_g"] * 1000 for f in fils if f["tipo"] == t]
        fixo = cfg.get(f"preco_kg_{t.lower()}") or 0
        out[t] = {"preco_kg": fixo if fixo > 0 else (sum(precos) / len(precos) if precos else 0.0),
                  "qtd": len(precos), "fixo": fixo > 0}
    for t, outro in (("Simples", "Especial"), ("Especial", "Simples")):
        if not out[t]["preco_kg"]:
            out[t]["preco_kg"] = out[outro]["preco_kg"]
    return out


def calcular_custo(gramas, horas, minutos_trabalho, custo_extra, filamento=None, impressora=None, cfg=None,
                   tipo_filamento=None, medias=None):
    """Retorna dict com o custo detalhado de UMA unidade.

    O material usa o preco MEDIO por kg do tipo (Simples/Especial), nao o preco do rolo:
    o tipo vem de `tipo_filamento` ou, se nao vier, do filamento informado.
    """
    cfg = cfg or get_config()
    medias = medias or medias_filamento(cfg)
    tipo = tipo_filamento or (filamento or {}).get("tipo") or "Simples"
    custo_g = medias.get(tipo, medias["Simples"])["preco_kg"] / 1000
    material = (gramas or 0) * custo_g * (1 + (cfg["taxa_falha"] or 0) / 100)

    potencia = (impressora or {}).get("potencia_w") or 150
    energia = (horas or 0) * potencia / 1000 * (cfg["custo_kwh"] or 0)

    depreciacao = 0.0
    if impressora and (impressora.get("vida_util_horas") or 0) > 0:
        depreciacao = (horas or 0) * (impressora.get("valor_compra") or 0) / impressora["vida_util_horas"]

    mao_obra = (minutos_trabalho or 0) / 60 * (cfg["hora_trabalho"] or 0)
    extra = custo_extra or 0
    total = material + energia + depreciacao + mao_obra + extra
    return {
        "Material": material, "Energia": energia, "Desgaste da impressora": depreciacao,
        "Mão de obra": mao_obra, "Extras (embalagem, peças...)": extra, "total": total,
    }


def preco_sugerido(custo_total, margem_pct, taxa_venda_pct=0.0):
    """Custo + margem, ja embutindo a taxa de venda (maquininha/marketplace)."""
    base = custo_total * (1 + (margem_pct or 0) / 100)
    taxa = (taxa_venda_pct or 0) / 100
    if taxa >= 1:
        return base
    return base / (1 - taxa)


def custo_produto(produto, cfg=None, medias=None):
    fil = obter("filamentos", produto["filamento_id"]) if produto.get("filamento_id") else None
    imp = obter("impressoras", produto["impressora_id"]) if produto.get("impressora_id") else None
    return calcular_custo(produto.get("gramas"), produto.get("horas_impressao"),
                          produto.get("minutos_trabalho"), produto.get("custo_extra"), fil, imp, cfg,
                          tipo_filamento=produto.get("tipo_filamento"), medias=medias)


# ---------------------------------------------------------------- estoque

def _mover(c, tipo_item, item_id, qtd, motivo, pedido_id=None, data=None):
    tabela, campo = {
        "filamento": ("filamentos", "estoque_g"),
        "insumo": ("insumos", "estoque"),
        "produto": ("produtos", "estoque_pronto"),
    }[tipo_item]
    c.execute(f"UPDATE {tabela} SET {campo} = COALESCE({campo}, 0) + ? WHERE id = ?", (qtd, item_id))
    c.execute("INSERT INTO movimentos(data, tipo_item, item_id, qtd, motivo, pedido_id) VALUES (?,?,?,?,?,?)",
              (data or _hoje(), tipo_item, item_id, qtd, motivo, pedido_id))


def ajustar_estoque(tipo_item, item_id, qtd, motivo):
    with _conn() as c:
        _mover(c, tipo_item, item_id, qtd, motivo)


def registrar_compra(tipo_item, item_id, qtd, valor_total, data, lancar_financeiro, usuario="",
                     n_parcelas=1, primeiro_vencimento=None, forma_pagamento=""):
    """Entrada de estoque por compra (filamento em gramas, insumo na unidade dele).

    Com n_parcelas > 1 a despesa vira uma compra parcelada (uma saida por mes).
    """
    with _conn() as c:
        if tipo_item == "filamento":
            f = dict(c.execute("SELECT * FROM filamentos WHERE id=?", (item_id,)).fetchone())
            nome, categoria = nome_filamento(f), "Filamento"
        else:
            i = dict(c.execute("SELECT * FROM insumos WHERE id=?", (item_id,)).fetchone())
            nome, categoria = i["nome"], "Insumos"
        parc = f" em {n_parcelas}x" if n_parcelas > 1 else ""
        _mover(c, tipo_item, item_id, qtd, f"Compra (R$ {valor_total:.2f}{parc})", data=data)
        if lancar_financeiro and valor_total > 0:
            _lancar_despesa(c, f"Compra: {nome}", categoria, valor_total, n_parcelas,
                            primeiro_vencimento or data, data, forma_pagamento, usuario=usuario)


def registrar_producao(produto_id, qtd, motivo="Produção", pedido_id=None, c=None):
    """Produz N unidades: baixa o filamento e soma no estoque de produtos prontos."""
    def _fazer(c):
        p = dict(c.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone())
        if p.get("filamento_id") and (p.get("gramas") or 0) > 0:
            _mover(c, "filamento", p["filamento_id"], -p["gramas"] * qtd,
                   f"{motivo}: {qtd}x {p['nome']}", pedido_id)
        _mover(c, "produto", produto_id, qtd, f"{motivo}: {qtd}x", pedido_id)
    if c is not None:
        _fazer(c)
    else:
        with _conn() as c2:
            _fazer(c2)


def get_movimentos(limite=200):
    with _conn() as c:
        return _rows(c.execute("SELECT * FROM movimentos ORDER BY id DESC LIMIT ?", (limite,)))


def get_alertas_estoque():
    with _conn() as c:
        fil = _rows(c.execute("""SELECT * FROM filamentos WHERE ativo=1 AND estoque_g <= estoque_minimo_g
                                 ORDER BY estoque_g"""))
        ins = _rows(c.execute("""SELECT * FROM insumos WHERE ativo=1 AND estoque <= estoque_minimo
                                 AND estoque_minimo > 0 ORDER BY nome"""))
        prod = _rows(c.execute("""SELECT * FROM produtos WHERE ativo=1 AND estoque_minimo > 0
                                  AND estoque_pronto < estoque_minimo ORDER BY nome"""))
    return fil, ins, prod


# ---------------------------------------------------------------- pedidos

def listar_pedidos(status=None, data_ini=None, data_fim=None):
    sql = """SELECT p.*, COALESCE(c.nome, '—') AS cliente,
                    COALESCE((SELECT SUM(qtd * preco_unit) FROM pedido_itens WHERE pedido_id = p.id), 0) AS subtotal,
                    COALESCE((SELECT SUM(qtd * custo_unit) FROM pedido_itens WHERE pedido_id = p.id), 0) AS custo
             FROM pedidos p LEFT JOIN clientes c ON c.id = p.cliente_id WHERE 1=1"""
    args = []
    if status:
        sql += f" AND p.status IN ({','.join('?' for _ in status)})"
        args += list(status)
    if data_ini:
        sql += " AND p.data >= ?"
        args.append(data_ini)
    if data_fim:
        sql += " AND p.data <= ?"
        args.append(data_fim)
    sql += " ORDER BY p.data DESC, p.id DESC"
    with _conn() as c:
        rows = _rows(c.execute(sql, args))
    for r in rows:
        r["total"] = r["subtotal"] - (r["desconto"] or 0) + (r["frete"] or 0)
        r["a_receber"] = max(r["total"] - (r["valor_recebido"] or 0), 0) if r["status"] != "Cancelado" else 0
        r["lucro"] = r["subtotal"] - (r["desconto"] or 0) - r["custo"]
    return rows


def obter_pedido(pedido_id):
    with _conn() as c:
        p = c.execute("SELECT * FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
        if not p:
            return None, []
        itens = _rows(c.execute("SELECT * FROM pedido_itens WHERE pedido_id=? ORDER BY id", (pedido_id,)))
        return dict(p), itens


def salvar_pedido(pedido, itens, pedido_id=None, usuario=""):
    """Cria/atualiza pedido + itens, sincroniza estoque e o recebimento no financeiro."""
    campos = ["cliente_id", "data", "prazo", "status", "canal", "forma_pagamento",
              "desconto", "frete", "valor_recebido", "obs"]
    dados = [pedido.get(k) for k in campos]
    with _conn() as c:
        if pedido_id:
            c.execute(f"UPDATE pedidos SET {', '.join(k + '=?' for k in campos)} WHERE id=?",
                      dados + [pedido_id])
            c.execute("DELETE FROM pedido_itens WHERE pedido_id=?", (pedido_id,))
        else:
            cur = c.execute(f"INSERT INTO pedidos ({', '.join(campos)}) VALUES ({', '.join('?' for _ in campos)})",
                            dados)
            pedido_id = cur.lastrowid
        for it in itens:
            c.execute("""INSERT INTO pedido_itens(pedido_id, produto_id, descricao, qtd, preco_unit,
                         custo_unit, filamento_id, gramas_unit) VALUES (?,?,?,?,?,?,?,?)""",
                      (pedido_id, it.get("produto_id"), it["descricao"], int(it.get("qtd") or 1),
                       float(it.get("preco_unit") or 0), float(it.get("custo_unit") or 0),
                       it.get("filamento_id"), float(it.get("gramas_unit") or 0)))
        _sincronizar_estoque_pedido(c, pedido_id)
        _sincronizar_recebimento(c, pedido_id, usuario)
    return pedido_id


def excluir_pedido(pedido_id):
    with _conn() as c:
        _desfazer_baixa(c, pedido_id)
        c.execute("DELETE FROM lancamentos WHERE pedido_id=?", (pedido_id,))
        c.execute("DELETE FROM pedidos WHERE id=?", (pedido_id,))


def _desfazer_baixa(c, pedido_id):
    movs = _rows(c.execute("SELECT * FROM movimentos WHERE pedido_id=?", (pedido_id,)))
    tabelas = {"filamento": ("filamentos", "estoque_g"), "insumo": ("insumos", "estoque"),
               "produto": ("produtos", "estoque_pronto")}
    for m in movs:
        tabela, campo = tabelas[m["tipo_item"]]
        c.execute(f"UPDATE {tabela} SET {campo} = {campo} - ? WHERE id=?", (m["qtd"], m["item_id"]))
    c.execute("DELETE FROM movimentos WHERE pedido_id=?", (pedido_id,))
    c.execute("UPDATE pedidos SET estoque_baixado=0 WHERE id=?", (pedido_id,))


def _sincronizar_estoque_pedido(c, pedido_id):
    """Quando o pedido fica 'Entregue', da baixa no estoque; se sair de 'Entregue', devolve.

    Itens de catalogo saem do estoque de produtos prontos; o que faltar e produzido na
    hora (baixa de filamento). Itens personalizados baixam o filamento direto.
    """
    p = dict(c.execute("SELECT * FROM pedidos WHERE id=?", (pedido_id,)).fetchone())
    # Sempre refaz a baixa do zero: itens podem ter mudado
    if p["estoque_baixado"]:
        _desfazer_baixa(c, pedido_id)
    if p["status"] != "Entregue":
        return
    itens = _rows(c.execute("SELECT * FROM pedido_itens WHERE pedido_id=?", (pedido_id,)))
    for it in itens:
        qtd = int(it["qtd"] or 0)
        if qtd <= 0:
            continue
        if it["produto_id"]:
            prod = c.execute("SELECT * FROM produtos WHERE id=?", (it["produto_id"],)).fetchone()
            if prod:
                disponivel = max(int(prod["estoque_pronto"] or 0), 0)
                faltam = max(qtd - disponivel, 0)
                if faltam:
                    registrar_producao(it["produto_id"], faltam, f"Produção p/ pedido #{pedido_id}", pedido_id, c)
                _mover(c, "produto", it["produto_id"], -qtd, f"Pedido #{pedido_id}", pedido_id)
                continue
        if it["filamento_id"] and (it["gramas_unit"] or 0) > 0:
            _mover(c, "filamento", it["filamento_id"], -it["gramas_unit"] * qtd,
                   f"Pedido #{pedido_id}: {it['descricao']}", pedido_id)
    c.execute("UPDATE pedidos SET estoque_baixado=1 WHERE id=?", (pedido_id,))


def _sincronizar_recebimento(c, pedido_id, usuario=""):
    """Mantem 1 lancamento de entrada (Venda) com o valor recebido do pedido."""
    p = dict(c.execute("""SELECT p.*, COALESCE(cl.nome, '') AS cliente FROM pedidos p
                          LEFT JOIN clientes cl ON cl.id = p.cliente_id WHERE p.id=?""",
                       (pedido_id,)).fetchone())
    existente = c.execute("SELECT id, data FROM lancamentos WHERE pedido_id=?", (pedido_id,)).fetchone()
    valor = float(p["valor_recebido"] or 0)
    if valor <= 0 or p["status"] == "Cancelado":
        c.execute("DELETE FROM lancamentos WHERE pedido_id=?", (pedido_id,))
        return
    desc = f"Pedido #{pedido_id}" + (f" — {p['cliente']}" if p["cliente"] else "")
    if existente:
        c.execute("""UPDATE lancamentos SET valor=?, descricao=?, forma_pagamento=? WHERE id=?""",
                  (valor, desc, p["forma_pagamento"] or "", existente["id"]))
    else:
        c.execute("""INSERT INTO lancamentos(data, tipo, categoria, descricao, valor, forma_pagamento,
                     pedido_id, criado_por) VALUES (?, 'entrada', 'Venda', ?, ?, ?, ?, ?)""",
                  (_hoje(), desc, valor, p["forma_pagamento"] or "", pedido_id, usuario))


def itens_vendidos(data_ini=None, data_fim=None):
    """Ranking de itens vendidos (pedidos que nao sao orcamento nem cancelados)."""
    sql = """SELECT COALESCE(pr.nome, i.descricao) AS item, SUM(i.qtd) AS qtd,
                    SUM(i.qtd * i.preco_unit) AS receita,
                    SUM(i.qtd * (i.preco_unit - i.custo_unit)) AS lucro
             FROM pedido_itens i JOIN pedidos p ON p.id = i.pedido_id
             LEFT JOIN produtos pr ON pr.id = i.produto_id
             WHERE p.status NOT IN ('Orçamento', 'Cancelado')"""
    args = []
    if data_ini:
        sql += " AND p.data >= ?"
        args.append(data_ini)
    if data_fim:
        sql += " AND p.data <= ?"
        args.append(data_fim)
    with _conn() as c:
        return _rows(c.execute(sql + " GROUP BY item ORDER BY receita DESC", args))


# ---------------------------------------------------------------- financeiro

def listar_lancamentos(data_ini=None, data_fim=None):
    sql = "SELECT * FROM lancamentos WHERE 1=1"
    args = []
    if data_ini:
        sql += " AND data >= ?"
        args.append(data_ini)
    if data_fim:
        sql += " AND data <= ?"
        args.append(data_fim)
    with _conn() as c:
        return _rows(c.execute(sql + " ORDER BY data DESC, id DESC", args))


def inserir_lancamento(data, tipo, categoria, descricao, valor, forma_pagamento="", usuario="", pago=True):
    with _conn() as c:
        c.execute("""INSERT INTO lancamentos(data, tipo, categoria, descricao, valor, forma_pagamento, criado_por, pago)
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (data, tipo, categoria, descricao, abs(float(valor)), forma_pagamento, usuario, 1 if pago else 0))


def somar_meses(d, n):
    """Mesma data n meses depois (dia 31 vira o ultimo dia do mes, se preciso)."""
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _valores_parcelas(total, n):
    """Divide em n parcelas; a ultima absorve os centavos do arredondamento."""
    base = round(total / n, 2)
    return [base] * (n - 1) + [round(total - base * (n - 1), 2)]


def _lancar_despesa(c, descricao, categoria, valor_total, n_parcelas, primeiro_vencimento, data_compra,
                    forma_pagamento="", fornecedor="", usuario=""):
    """Lanca uma despesa a vista (1 saida) ou parcelada (1 saida por mes, ligadas a uma compra).

    Cada parcela entra no mes do seu vencimento. Parcelas com vencimento ate hoje ja
    nascem pagas; as futuras ficam 'a pagar'. Retorna o id da compra parcelada (ou None).
    """
    n = max(int(n_parcelas or 1), 1)
    venc0 = date.fromisoformat(str(primeiro_vencimento)[:10])
    hoje = date.today()
    parc_id = None
    if n > 1:
        cur = c.execute("""INSERT INTO compras_parceladas(data_compra, descricao, fornecedor, categoria, valor_total,
                           n_parcelas, primeiro_vencimento, forma_pagamento, criado_por)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (str(data_compra)[:10], descricao, fornecedor, categoria, float(valor_total), n,
                         venc0.isoformat(), forma_pagamento, usuario))
        parc_id = cur.lastrowid
    for i, v in enumerate(_valores_parcelas(float(valor_total), n)):
        venc = somar_meses(venc0, i)
        c.execute("""INSERT INTO lancamentos(data, tipo, categoria, descricao, valor, forma_pagamento, criado_por,
                     pago, parcelamento_id, parcela_num, parcela_total, data_compra)
                     VALUES (?, 'saida', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (venc.isoformat(), categoria, f"{descricao} ({i + 1}/{n})" if n > 1 else descricao, v,
                   forma_pagamento, usuario, 1 if venc <= hoje else 0, parc_id,
                   i + 1 if n > 1 else None, n if n > 1 else None, str(data_compra)[:10]))
    return parc_id


def registrar_despesa(descricao, categoria, valor_total, n_parcelas, primeiro_vencimento, data_compra,
                      forma_pagamento="", fornecedor="", usuario=""):
    with _conn() as c:
        return _lancar_despesa(c, descricao, categoria, valor_total, n_parcelas, primeiro_vencimento,
                               data_compra, forma_pagamento, fornecedor, usuario)


def listar_parcelamentos():
    """Compras parceladas com o andamento (pagas, restante, proxima parcela)."""
    with _conn() as c:
        compras = _rows(c.execute("SELECT * FROM compras_parceladas ORDER BY data_compra DESC, id DESC"))
        for p in compras:
            parcelas = _rows(c.execute("SELECT * FROM lancamentos WHERE parcelamento_id=? ORDER BY parcela_num",
                                       (p["id"],)))
            p["parcelas"] = parcelas
            p["pagas"] = sum(1 for l in parcelas if l["pago"])
            p["valor_pago"] = sum(l["valor"] for l in parcelas if l["pago"])
            p["valor_restante"] = sum(l["valor"] for l in parcelas if not l["pago"])
            p["proxima"] = next((l for l in parcelas if not l["pago"]), None)
    return compras


def excluir_parcelamento(parc_id):
    """Apaga a compra parcelada e TODAS as parcelas dela."""
    with _conn() as c:
        c.execute("DELETE FROM lancamentos WHERE parcelamento_id=?", (parc_id,))
        c.execute("DELETE FROM compras_parceladas WHERE id=?", (parc_id,))


def contas_a_pagar():
    """Saidas ainda nao pagas (vencidas e futuras), da mais antiga para a mais nova."""
    with _conn() as c:
        return _rows(c.execute("""SELECT * FROM lancamentos WHERE tipo='saida' AND COALESCE(pago, 1)=0
                                  ORDER BY data, id"""))


def marcar_pago(ids, pago=True):
    with _conn() as c:
        c.executemany("UPDATE lancamentos SET pago=? WHERE id=?", [(1 if pago else 0, i) for i in ids])


def marcar_vencidas_pagas():
    """Marca como pagas as saidas com vencimento ate hoje. Retorna quantas mudaram."""
    with _conn() as c:
        cur = c.execute("UPDATE lancamentos SET pago=1 WHERE tipo='saida' AND COALESCE(pago, 1)=0 AND data<=?",
                        (_hoje(),))
        return cur.rowcount


def projecao_a_pagar():
    """Total ainda a pagar por mes de vencimento (YYYY-MM)."""
    with _conn() as c:
        return _rows(c.execute("""SELECT substr(data, 1, 7) AS mes, SUM(valor) AS valor, COUNT(*) AS qtd
                                  FROM lancamentos WHERE tipo='saida' AND COALESCE(pago, 1)=0
                                  GROUP BY mes ORDER BY mes"""))


def atualizar_lancamento(lanc_id, dados):
    permitidos = ["data", "tipo", "categoria", "descricao", "valor", "forma_pagamento", "pago"]
    dados = {k: v for k, v in dados.items() if k in permitidos}
    if not dados:
        return
    with _conn() as c:
        c.execute(f"UPDATE lancamentos SET {', '.join(k + '=?' for k in dados)} WHERE id=?",
                  list(dados.values()) + [lanc_id])


def excluir_lancamento(lanc_id):
    with _conn() as c:
        c.execute("DELETE FROM lancamentos WHERE id=?", (lanc_id,))


def resumo_mensal(meses=12):
    """Entradas/saidas por mes (YYYY-MM) dos ultimos N meses com movimento, ate o mes atual.

    Parcelas futuras ficam de fora (elas aparecem em projecao_a_pagar).
    """
    with _conn() as c:
        rows = _rows(c.execute("""
            SELECT substr(data, 1, 7) AS mes,
                   SUM(CASE WHEN tipo='entrada' THEN valor ELSE 0 END) AS entradas,
                   SUM(CASE WHEN tipo='saida' THEN valor ELSE 0 END) AS saidas
            FROM lancamentos WHERE substr(data, 1, 7) <= ?
            GROUP BY mes ORDER BY mes DESC LIMIT ?""", (_hoje()[:7], meses)))
    rows.reverse()
    for r in rows:
        r["resultado"] = r["entradas"] - r["saidas"]
    return rows


def saldo_caixa():
    """Dinheiro que de fato entrou menos o que de fato foi pago (ignora contas a pagar)."""
    with _conn() as c:
        r = c.execute("""SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN valor ELSE -valor END), 0)
                         FROM lancamentos WHERE COALESCE(pago, 1)=1""").fetchone()
        return r[0]


def exportar_tabelas():
    """Todas as tabelas como {nome: lista de dicts} (para o Excel)."""
    nomes = ["clientes", "pedidos", "pedido_itens", "produtos", "filamentos", "insumos",
             "impressoras", "lancamentos", "compras_parceladas", "despesas_fixas", "movimentos", "config"]
    with _conn() as c:
        return {n: _rows(c.execute(f"SELECT * FROM {n}")) for n in nomes}


# ---------------------------------------------------------------- importacao (carga de dados)

def aplicar_importacao(dados, usuario="Importação"):
    """Aplica uma carga {id, despesas, filamentos, insumos, impressoras} uma unica vez.

    Pula o que ja existir (filamento com mesmo material/cor/marca, insumo com mesmo nome,
    despesa com mesma descricao e valor) para nao duplicar o que foi lancado a mao.
    Retorna um resumo em texto, ou None se essa carga ja tinha sido aplicada.
    """
    with _conn() as c:
        if c.execute("SELECT 1 FROM importacoes WHERE id=?", (dados["id"],)).fetchone():
            return None
        n_desp = n_fil = n_ins = n_imp = pulados = 0

        for d in dados.get("despesas", []):
            ja = c.execute("""SELECT 1 FROM compras_parceladas WHERE descricao=? AND ABS(valor_total-?)<0.01
                              UNION SELECT 1 FROM lancamentos WHERE descricao=? AND ABS(valor-?)<0.01""",
                           (d["descricao"], d["valor_total"], d["descricao"], d["valor_total"])).fetchone()
            if ja:
                pulados += 1
                continue
            _lancar_despesa(c, d["descricao"], d["categoria"], d["valor_total"], d.get("n_parcelas", 1),
                            d["primeiro_vencimento"], d["data_compra"], d.get("forma_pagamento", ""),
                            d.get("fornecedor", ""), usuario)
            n_desp += 1

        for f in dados.get("filamentos", []):
            ja = c.execute("""SELECT 1 FROM filamentos WHERE lower(material)=lower(?) AND lower(cor)=lower(?)
                              AND lower(COALESCE(marca,''))=lower(?)""",
                           (f["material"], f["cor"], f.get("marca", ""))).fetchone()
            if ja:
                pulados += 1
                continue
            peso = f.get("peso_rolo_g", 1000)
            tipo = f.get("tipo") or ("Especial" if f["material"] in MATERIAIS_ESPECIAIS else "Simples")
            cur = c.execute("""INSERT INTO filamentos(material, cor, marca, preco_rolo, peso_rolo_g, estoque_g,
                               estoque_minimo_g, obs, ativo, tipo) VALUES (?,?,?,?,?,0,?,?,1,?)""",
                            (f["material"], f["cor"], f.get("marca", ""), f.get("preco_rolo", 0), peso,
                             f.get("estoque_minimo_g", 300), f.get("obs", ""), tipo))
            if f.get("rolos", 0) > 0:
                _mover(c, "filamento", cur.lastrowid, f["rolos"] * peso, "Estoque inicial (importação)")
            n_fil += 1

        for i in dados.get("insumos", []):
            if c.execute("SELECT 1 FROM insumos WHERE lower(nome)=lower(?)", (i["nome"],)).fetchone():
                pulados += 1
                continue
            cur = c.execute("""INSERT INTO insumos(nome, unidade, custo_unit, estoque, estoque_minimo, ativo)
                               VALUES (?,?,?,0,?,1)""",
                            (i["nome"], i.get("unidade", "un"), i.get("custo_unit", 0), i.get("estoque_minimo", 0)))
            if i.get("quantidade", 0) > 0:
                _mover(c, "insumo", cur.lastrowid, i["quantidade"], "Estoque inicial (importação)")
            n_ins += 1

        for u in dados.get("atualizar_insumos", []):
            # Atualiza campos de um insumo que ja existe (pelo nome), ex.: custo por unidade
            campos = {k: u[k] for k in ("custo_unit", "estoque_minimo", "unidade") if k in u}
            if campos:
                cur = c.execute(f"UPDATE insumos SET {', '.join(k + '=?' for k in campos)} WHERE lower(nome)=lower(?)",
                                list(campos.values()) + [u["nome"]])
                if not cur.rowcount:
                    pulados += 1

        for aj in dados.get("ajustes_data_compra", []):
            # Completa a data da compra de lancamentos antigos (anteriores a coluna data_compra)
            c.execute("UPDATE lancamentos SET data_compra=? WHERE descricao=? AND data_compra IS NULL",
                      (aj["data_compra"], aj["descricao"]))

        for fx in dados.get("despesas_fixas", []):
            if c.execute("SELECT 1 FROM despesas_fixas WHERE lower(descricao)=lower(?)", (fx["descricao"],)).fetchone():
                pulados += 1
                continue
            c.execute("""INSERT INTO despesas_fixas(descricao, categoria, valor, dia_vencimento, forma_pagamento,
                         inicio, ativo, criado_por) VALUES (?,?,?,?,?,?,1,?)""",
                      (fx["descricao"], fx.get("categoria", "Outros"), fx["valor"], fx.get("dia_vencimento", 10),
                       fx.get("forma_pagamento", ""), fx["inicio"], usuario))
            n_desp += 1

        for m in dados.get("impressoras", []):
            if c.execute("SELECT 1 FROM impressoras WHERE lower(nome)=lower(?)", (m["nome"],)).fetchone():
                pulados += 1
                continue
            c.execute("""INSERT INTO impressoras(nome, potencia_w, valor_compra, vida_util_horas, ativa)
                         VALUES (?,?,?,?,1)""",
                      (m["nome"], m.get("potencia_w", 150), m.get("valor_compra", 0), m.get("vida_util_horas", 5000)))
            n_imp += 1

        resumo = (f"Importado: {n_desp} despesa(s) no Financeiro, {n_fil} filamento(s), {n_ins} insumo(s)"
                  f" e {n_imp} impressora(s)"
                  + (f" · {pulados} item(ns) já existiam e foram pulados" if pulados else ""))
        c.execute("INSERT INTO importacoes(id, quando, resumo) VALUES (?,?,?)",
                  (dados["id"], datetime.now().strftime("%Y-%m-%d %H:%M"), resumo))
        return resumo


# ---------------------------------------------------------------- analise de investimento

def _mes_seguinte(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y + (m == 12):04d}-{1 if m == 12 else m + 1:02d}"


def inicio_vendas(cfg=None):
    """Data que separa a montagem do estudio (investimento) da operacao.

    Valor fixo das Configuracoes, se houver; senao a data da 1a venda (pedido valido ou
    recebimento). None = ainda nao houve venda (tudo ate agora e investimento).
    """
    cfg = cfg or get_config()
    if (cfg.get("inicio_vendas") or 0) > 0:
        return date.fromordinal(int(cfg["inicio_vendas"]))
    with _conn() as c:
        r = c.execute("""SELECT MIN(d) FROM (
                             SELECT MIN(data) AS d FROM pedidos WHERE status NOT IN ('Orçamento', 'Cancelado')
                             UNION ALL
                             SELECT MIN(data) FROM lancamentos WHERE tipo='entrada' AND categoria='Venda')""").fetchone()
    return date.fromisoformat(r[0][:10]) if r and r[0] else None


def analise_investimento(cfg=None):
    """Numeros da aba de investimento: investido, faturamento, lucro, ponto de equilibrio e payback."""
    cfg = cfg or get_config()
    inicio = inicio_vendas(cfg)
    hoje = date.today()
    mes_atual = hoje.strftime("%Y-%m")
    with _conn() as c:
        lancs = _rows(c.execute("""SELECT l.*, COALESCE(l.data_compra, cp.data_compra, l.data) AS data_ref,
                                          cp.descricao AS compra_desc
                                   FROM lancamentos l LEFT JOIN compras_parceladas cp ON cp.id = l.parcelamento_id"""))
    pedidos = [p for p in listar_pedidos() if p["status"] not in ("Orçamento", "Cancelado")]

    def eh_investimento(l):
        if l["tipo"] != "saida":
            return False
        if l["categoria"] in CATEGORIAS_INVESTIMENTO:
            return True
        return inicio is None or l["data_ref"][:10] < inicio.isoformat()

    # Investimento agrupado por compra (parcelas da mesma compra viram 1 linha)
    compras = {}
    for l in lancs:
        if not eh_investimento(l):
            continue
        chave = ("p", l["parcelamento_id"]) if l["parcelamento_id"] else ("l", l["id"])
        item = compras.setdefault(chave, {"descricao": l["compra_desc"] or l["descricao"], "categoria": l["categoria"],
                                          "data": l["data_ref"][:10], "valor": 0.0, "pago": 0.0})
        item["valor"] += l["valor"]
        if l["pago"]:
            item["pago"] += l["valor"]
    itens_invest = sorted(compras.values(), key=lambda x: x["data"])
    investido = sum(i["valor"] for i in itens_invest)
    investido_pago = sum(i["pago"] for i in itens_invest)
    por_categoria = {}
    for i in itens_invest:
        por_categoria[i["categoria"]] = por_categoria.get(i["categoria"], 0) + i["valor"]

    # Linha do tempo mensal (ate o mes atual)
    meses_mov = [l["data"][:7] for l in lancs] + [l["data_ref"][:7] for l in lancs] + [p["data"][:7] for p in pedidos]
    meses = []
    if meses_mov:
        m = min(meses_mov)
        while m <= mes_atual:
            meses.append(m)
            m = _mes_seguinte(m)
    linhas = []
    acum_lucro = acum_invest = acum_fat = 0.0
    for m in meses:
        faturamento = sum(p["total"] for p in pedidos if p["data"][:7] == m)
        receita = sum(l["valor"] for l in lancs if l["tipo"] == "entrada" and l["categoria"] in CATEGORIAS_RECEITA
                      and l["data"][:7] == m)
        desp_oper = sum(l["valor"] for l in lancs if l["tipo"] == "saida" and not eh_investimento(l)
                        and l["data"][:7] == m)
        fixos = sum(l["valor"] for l in lancs if l["tipo"] == "saida" and not eh_investimento(l)
                    and l["categoria"] in CATEGORIAS_FIXAS and l["data"][:7] == m)
        invest = sum(l["valor"] for l in lancs if eh_investimento(l) and l["data_ref"][:7] == m)
        acum_lucro += receita - desp_oper
        acum_invest += invest
        acum_fat += faturamento
        linhas.append({"mes": m, "faturamento": faturamento, "recebido": receita, "despesas": desp_oper,
                       "fixos": fixos, "lucro": receita - desp_oper, "investimento": invest,
                       "lucro_acumulado": acum_lucro, "saldo": acum_lucro - acum_invest})

    # Meses de operacao (a partir da 1a venda) para as medias
    operando = [x for x in linhas if inicio and x["mes"] >= inicio.strftime("%Y-%m")]
    ultimos = operando[-3:]
    lucro_medio = sum(x["lucro"] for x in ultimos) / len(ultimos) if ultimos else 0.0
    fat_medio = sum(x["faturamento"] for x in ultimos) / len(ultimos) if ultimos else 0.0
    fixos_auto = sum(x["fixos"] for x in ultimos) / len(ultimos) if ultimos else 0.0
    with _conn() as c:
        soma_fixas = c.execute("SELECT COALESCE(SUM(valor), 0) FROM despesas_fixas WHERE ativo=1").fetchone()[0]
    if cfg.get("custos_fixos_mensais"):
        fixos, fixos_origem = cfg["custos_fixos_mensais"], "valor definido nas Premissas"
    elif soma_fixas:
        fixos, fixos_origem = soma_fixas, "soma das despesas fixas cadastradas"
    else:
        fixos, fixos_origem = fixos_auto, "média das despesas fixas dos últimos 3 meses"

    # Margem de contribuicao: realizada nos pedidos ou, sem vendas, a da precificacao padrao
    receita_ped = sum(p["subtotal"] - (p["desconto"] or 0) for p in pedidos)
    custo_ped = sum(p["custo"] for p in pedidos)
    taxa = (cfg.get("taxa_venda") or 0) / 100
    if receita_ped > 0:
        mc = max((receita_ped - custo_ped) / receita_ped - taxa, 0.0)
        mc_origem = "pedidos vendidos"
    else:
        mg = (cfg.get("margem_padrao") or 0) / 100
        mc = (1 - taxa) * mg / (1 + mg) if mg > 0 else 0.0
        mc_origem = "margem padrão da precificação"
    ticket = receita_ped / len(pedidos) if pedidos else 0.0

    falta = investido - acum_lucro
    payback_meses = falta / lucro_medio if lucro_medio > 0 and falta > 0 else None
    return {
        "inicio": inicio, "investido": investido, "investido_pago": investido_pago,
        "investido_a_pagar": investido - investido_pago, "por_categoria": por_categoria,
        "itens_investimento": itens_invest, "meses": linhas,
        "faturamento_total": acum_fat, "lucro_acumulado": acum_lucro,
        "retorno_pct": (acum_lucro / investido * 100) if investido else 0.0,
        "lucro_medio": lucro_medio, "faturamento_medio": fat_medio, "meses_operando": len(operando),
        "custos_fixos": fixos, "custos_fixos_auto": fixos_auto, "custos_fixos_origem": fixos_origem,
        "margem_contribuicao": mc, "mc_origem": mc_origem, "ticket_medio": ticket, "n_pedidos": len(pedidos),
        "ponto_equilibrio": fixos / mc if mc > 0 else None,
        "falta_recuperar": max(falta, 0.0), "payback_meses": payback_meses,
        "pago_de_volta": investido > 0 and falta <= 0,
    }


# ---------------------------------------------------------------- despesas fixas (mensais)

def _venc_no_mes(ym, dia):
    y, m = int(ym[:4]), int(ym[5:7])
    return date(y, m, min(int(dia or 1), calendar.monthrange(y, m)[1]))


def listar_despesas_fixas():
    with _conn() as c:
        return _rows(c.execute("SELECT * FROM despesas_fixas ORDER BY ativo DESC, descricao COLLATE NOCASE"))


def inserir_despesa_fixa(descricao, categoria, valor, dia_vencimento, inicio, forma_pagamento="", usuario=""):
    with _conn() as c:
        c.execute("""INSERT INTO despesas_fixas(descricao, categoria, valor, dia_vencimento, forma_pagamento, inicio,
                     ativo, criado_por) VALUES (?,?,?,?,?,?,1,?)""",
                  (descricao, categoria, float(valor), int(dia_vencimento), forma_pagamento, inicio, usuario))
    return gerar_despesas_fixas()


def gerar_despesas_fixas():
    """Lanca cada despesa fixa ativa em todos os meses desde o inicio ate o mes que vem.

    Cada mes so e gerado uma vez (despesas_fixas_geradas): se um lancamento for excluido a mao,
    ele nao volta. Os lancamentos nascem 'a pagar'. Retorna quantos foram criados.
    """
    ate = _mes_seguinte(_hoje()[:7])
    criados = 0
    with _conn() as c:
        for fx in _rows(c.execute("SELECT * FROM despesas_fixas WHERE ativo=1")):
            mes = fx["inicio"][:7]
            while mes <= ate:
                if not c.execute("SELECT 1 FROM despesas_fixas_geradas WHERE fixa_id=? AND mes=?",
                                 (fx["id"], mes)).fetchone():
                    venc = _venc_no_mes(mes, fx["dia_vencimento"]).isoformat()
                    c.execute("""INSERT INTO lancamentos(data, tipo, categoria, descricao, valor, forma_pagamento,
                                 criado_por, pago, data_compra, fixa_id)
                                 VALUES (?, 'saida', ?, ?, ?, ?, 'Despesa fixa', 0, ?, ?)""",
                              (venc, fx["categoria"], f"{fx['descricao']} ({mes[5:7]}/{mes[:4]})", fx["valor"],
                               fx["forma_pagamento"] or "", venc, fx["id"]))
                    c.execute("INSERT INTO despesas_fixas_geradas(fixa_id, mes) VALUES (?, ?)", (fx["id"], mes))
                    criados += 1
                mes = _mes_seguinte(mes)
    return criados


def atualizar_despesa_fixa(fixa_id, dados):
    """Atualiza a despesa fixa e as parcelas dela ainda nao pagas (a partir deste mes)."""
    campos = {k: v for k, v in dados.items()
              if k in ("descricao", "categoria", "valor", "dia_vencimento", "forma_pagamento", "ativo")}
    if not campos:
        return
    mes_atual = _hoje()[:7]
    with _conn() as c:
        antes = c.execute("SELECT ativo, inicio FROM despesas_fixas WHERE id=?", (fixa_id,)).fetchone()
        if antes and not antes["ativo"] and campos.get("ativo"):
            # Reativada: recomeca neste mes, sem lancar os meses em que ficou parada; os meses a partir
            # de agora cujas contas foram apagadas na desativacao voltam a ser gerados
            campos["inicio"] = max(antes["inicio"][:7], mes_atual)
            c.execute("""DELETE FROM despesas_fixas_geradas WHERE fixa_id=? AND mes >= ? AND NOT EXISTS (
                             SELECT 1 FROM lancamentos l WHERE l.fixa_id=despesas_fixas_geradas.fixa_id
                             AND substr(l.data, 1, 7)=despesas_fixas_geradas.mes)""", (fixa_id, mes_atual))
        c.execute(f"UPDATE despesas_fixas SET {', '.join(k + '=?' for k in campos)} WHERE id=?",
                  list(campos.values()) + [fixa_id])
        fx = dict(c.execute("SELECT * FROM despesas_fixas WHERE id=?", (fixa_id,)).fetchone())
        abertos = _rows(c.execute("""SELECT id, data FROM lancamentos WHERE fixa_id=? AND COALESCE(pago, 1)=0
                                     AND substr(data, 1, 7) >= ?""", (fixa_id, mes_atual)))
        for l in abertos:
            if not fx["ativo"]:
                c.execute("DELETE FROM lancamentos WHERE id=?", (l["id"],))
                continue
            mes = l["data"][:7]
            venc = _venc_no_mes(mes, fx["dia_vencimento"]).isoformat()
            c.execute("""UPDATE lancamentos SET valor=?, categoria=?, forma_pagamento=?, data=?, data_compra=?,
                         descricao=? WHERE id=?""",
                      (fx["valor"], fx["categoria"], fx["forma_pagamento"] or "", venc, venc,
                       f"{fx['descricao']} ({mes[5:7]}/{mes[:4]})", l["id"]))


def excluir_despesa_fixa(fixa_id):
    """Remove a despesa fixa e as parcelas dela ainda nao pagas deste mes em diante (o historico pago fica)."""
    with _conn() as c:
        c.execute("""DELETE FROM lancamentos WHERE fixa_id=? AND COALESCE(pago, 1)=0
                     AND substr(data, 1, 7) >= ?""", (fixa_id, _hoje()[:7]))
        c.execute("DELETE FROM despesas_fixas_geradas WHERE fixa_id=?", (fixa_id,))
        c.execute("DELETE FROM despesas_fixas WHERE id=?", (fixa_id,))


# ---------------------------------------------------------------- fotos dos produtos

FOTO_LADO = 700       # px do maior lado da foto guardada
MINIATURA_LADO = 160  # px da miniatura das tabelas


def _jpeg(img, lado, qualidade):
    import io
    copia = img.copy()
    copia.thumbnail((lado, lado))
    buf = io.BytesIO()
    copia.save(buf, format="JPEG", quality=qualidade, optimize=True)
    return buf.getvalue()


def salvar_foto_produto(produto_id, dados):
    """Reduz a foto (corrige a rotacao do celular) e guarda foto + miniatura. Retorna o tamanho em KB."""
    import io
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(dados))
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        fundo = Image.new("RGB", img.size, (255, 255, 255))  # transparencia vira fundo branco
        fundo.paste(img, mask=img.split()[-1])
        img = fundo
    else:
        img = img.convert("RGB")
    foto = _jpeg(img, FOTO_LADO, 80)
    mini = _jpeg(img, MINIATURA_LADO, 70)
    with _conn() as c:
        c.execute("""INSERT OR REPLACE INTO produto_fotos(produto_id, foto, miniatura, atualizado_em)
                     VALUES (?,?,?,?)""",
                  (produto_id, foto, mini, datetime.now().strftime("%Y-%m-%d %H:%M")))
    return round(len(foto) / 1024)


def obter_foto(produto_id):
    with _conn() as c:
        r = c.execute("SELECT foto FROM produto_fotos WHERE produto_id=?", (produto_id,)).fetchone()
    return bytes(r[0]) if r else None


def miniaturas_produtos():
    """{produto_id: bytes da miniatura}"""
    with _conn() as c:
        return {r[0]: bytes(r[1]) for r in c.execute("SELECT produto_id, miniatura FROM produto_fotos")}


def remover_foto_produto(produto_id):
    with _conn() as c:
        c.execute("DELETE FROM produto_fotos WHERE produto_id=?", (produto_id,))
