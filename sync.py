# -*- coding: utf-8 -*-
"""
Sincronizacao do banco de dados com GitHub via API REST.
Usa a API do GitHub diretamente (sem depender de git CLI).
"""
import os
import base64
import json
import hashlib
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
import streamlit as st

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(REPO_DIR, "data", "borboleta.db")
DB_REPO_PATH = "data/borboleta.db"  # caminho dentro do repo de DADOS (Secret github_repo)

# Status do ultimo sync (visivel na sidebar)
_last_sync_status = {"ok": None, "msg": "", "detail": ""}

# Trava de seguranca: so libera o push depois que o pull deu certo (ou se ainda nao
# existe banco na nuvem). Evita sobrescrever os dados da nuvem com um banco vazio.
_estado = {"push_liberado": False, "pendente": False}  # pendente = ha alteracao local que nao foi p/ a nuvem


def _log(msg):
    print(f"[SYNC] {msg}", flush=True)


def get_last_sync_status():
    """Retorna status do ultimo sync para exibir na UI."""
    return _last_sync_status.copy()


def _set_status(ok, msg, detail=""):
    _last_sync_status["ok"] = ok
    _last_sync_status["msg"] = msg
    _last_sync_status["detail"] = detail


def _get_config():
    """Retorna token, owner e repo do secrets."""
    token = ""
    repo_url = ""

    try:
        # Tenta varias formas de ler os secrets
        if hasattr(st, "secrets"):
            # Forma 1: acesso direto
            try:
                token = st.secrets["github_token"]
            except (KeyError, Exception):
                pass
            try:
                repo_url = st.secrets["github_repo"]
            except (KeyError, Exception):
                pass

            # Forma 2: .get()
            if not token:
                token = getattr(st.secrets, "get", lambda k, d: d)("github_token", "")
            if not repo_url:
                repo_url = getattr(st.secrets, "get", lambda k, d: d)("github_repo", "")

            # Log das chaves disponiveis para debug
            try:
                keys = list(st.secrets.keys()) if hasattr(st.secrets, "keys") else []
                _log(f"Secrets keys: {keys}")
            except Exception:
                _log("Nao conseguiu listar keys dos secrets")
    except Exception as e:
        _log(f"Erro ao ler secrets: {e}")
        _set_status(False, "Erro ao ler secrets", str(e))
        return None, None, None

    if not token:
        _log("Token vazio!")
        _set_status(False, "Token GitHub vazio", "Chave github_token nao encontrada nos secrets")
        return None, None, None

    if not repo_url:
        _log("Repo URL vazio!")
        _set_status(False, "Repo URL vazio", "Chave github_repo nao encontrada nos secrets")
        return None, None, None

    # Aceita "luanavolponi/borboleta" ou URL completa
    repo_url = repo_url.strip().rstrip("/").replace(".git", "")
    if "github.com" in repo_url:
        parts = repo_url.split("/")
        owner, repo = parts[-2], parts[-1]
    elif "/" in repo_url:
        owner, repo = repo_url.split("/", 1)
    else:
        _log(f"Formato de repo invalido: {repo_url}")
        _set_status(False, "Formato de repo invalido")
        return None, None, None
    _log(f"Config OK: {owner}/{repo}")
    return token, owner, repo


# Para o arquivo do banco: o formato padrao da API so devolve arquivos de ate 1 MB (acima disso, erro 403).
# O formato "object" funciona ate 100 MB (devolve sha e download_url; o conteudo vem vazio).
ACCEPT_OBJETO = "application/vnd.github.object+json"


def _github_api(method, url, token, data=None, timeout=60, accept="application/vnd.github.v3+json"):
    """Faz uma chamada a API do GitHub."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": accept,
        "User-Agent": "BorboletaApp",
    }
    if data:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    else:
        body = None

    req = urllib_request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _log(f"API {method} {e.code}: {error_body[:300]}")
        return e.code, {"error": error_body}
    except URLError as e:
        _log(f"API conexao falhou: {e.reason}")
        return 0, {"error": f"Conexao falhou: {e.reason}"}
    except Exception as e:
        _log(f"API erro inesperado: {e}")
        return 0, {"error": str(e)}


def _baixar_raw(url, token, timeout=120):
    """Baixa o conteudo bruto de um arquivo pela API (funciona para arquivos de 1 a 100 MB)."""
    req = urllib_request.Request(url, headers={"Authorization": f"token {token}", "User-Agent": "BorboletaApp",
                                               "Accept": "application/vnd.github.raw+json"})
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            dados = resp.read()
        _log(f"Download raw OK: {len(dados)} bytes")
        return dados
    except Exception as e:
        _log(f"Download raw falhou: {e}")
        return None


def tem_pendencia():
    """True se ha alteracoes salvas so no servidor, que ainda nao chegaram a nuvem."""
    return bool(_estado.get("pendente"))


# Marca em disco com o SHA da versao da nuvem em que o banco local se baseia. Sobrevive quando o
# app e atualizado com sessoes abertas (o modulo recarrega e _estado volta ao inicio, mas o
# arquivo do banco continua no disco com alteracoes que talvez nao tenham subido).
MARCA_PATH = DB_PATH + ".base_nuvem"


def _gravar_marca(sha):
    try:
        if sha:
            with open(MARCA_PATH, "w") as f:
                f.write(sha)
    except OSError as e:
        _log(f"Nao gravei a marca da nuvem: {e}")


def _ler_marca():
    try:
        with open(MARCA_PATH) as f:
            return f.read().strip() or None
    except OSError:
        return None


def _local_cobre_nuvem(url, token):
    """True se o banco local tem tudo o que esta na nuvem (enviar nao apagaria nada).

    Confere tabela por tabela que o local tem pelo menos as linhas da nuvem e todas as cargas ja importadas.
    """
    import sqlite3
    from contextlib import closing
    nuvem = _baixar_raw(url, token)
    if not nuvem or not os.path.exists(DB_PATH):
        return False
    tmp = DB_PATH + ".nuvem"
    try:
        with open(tmp, "wb") as f:
            f.write(nuvem)
        with closing(sqlite3.connect(tmp)) as cn, closing(sqlite3.connect(DB_PATH)) as cl:
            tabelas = [r[0] for r in cn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for t in tabelas:
                n_nuvem = cn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                n_local = cl.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                if n_local < n_nuvem:
                    _log(f"Banco local tem menos linhas em {t} ({n_local} < {n_nuvem}): nao libero")
                    return False
            if "importacoes" in tabelas:
                ids_nuvem = {r[0] for r in cn.execute("SELECT id FROM importacoes")}
                ids_local = {r[0] for r in cl.execute("SELECT id FROM importacoes")}
                if not ids_nuvem <= ids_local:
                    _log("Banco local nao tem todas as cargas da nuvem: nao libero")
                    return False
        return True
    except Exception as e:
        _log(f"Conferencia local x nuvem falhou: {e}")
        return False
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _tentar_liberar(url, token):
    """Libera o push sem novo pull quando e seguro: o banco local veio da versao atual da nuvem."""
    status, data = _github_api("GET", url, token, accept=ACCEPT_OBJETO)
    if status != 200:
        return False
    sha_nuvem = data.get("sha", "")
    if sha_nuvem and _ler_marca() == sha_nuvem:
        _log("Push liberado: banco local baseado na versao atual da nuvem (marca)")
    elif _local_cobre_nuvem(url, token):
        _log("Push liberado: banco local contem tudo o que esta na nuvem")
    else:
        return False
    _estado["push_liberado"] = True
    return True


def reconectar():
    """Se o app foi atualizado com a sessao aberta, tenta liberar e enviar o que ficou so no servidor (1x)."""
    if _estado["push_liberado"] or _estado.get("reconexao_tentada") or not os.path.exists(DB_PATH):
        return None
    _estado["reconexao_tentada"] = True
    _log("Sessao aberta sem pull neste processo: tentando reconectar")
    return push_database()


def push_database():
    """Envia o banco para o GitHub. Se falhar, marca a pendencia (o proximo pull nao apaga a alteracao)."""
    ok = _push_database()
    if ok:
        _estado["pendente"] = False
    elif _estado["push_liberado"]:
        _estado["pendente"] = True
    return ok


def pull_database():
    """Baixa o banco de dados mais recente do GitHub (e guarda o motivo, se falhar)."""
    if _estado.get("pendente") and os.path.exists(DB_PATH):
        # O banco local tem alteracoes que nao subiram: baixar agora apagaria essas alteracoes
        _log("Ha alteracoes locais pendentes: tentando enviar antes de baixar")
        if push_database():
            return True
        _set_status(False, "Ha alteracoes que ainda nao foram salvas na nuvem",
                    "O app tenta de novo a cada salvamento; use 'Tentar salvar agora' na barra lateral.")
        return False
    ok = _pull_database()
    _estado["erro_pull"] = None if _estado["push_liberado"] else _last_sync_status.get("msg")
    return ok


def _pull_database():
    _log("=== PULL INICIANDO ===")
    token, owner, repo = _get_config()
    if not token:
        return False

    # Primeiro tenta pegar info do arquivo
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{DB_REPO_PATH}?ref=main"
    status, data = _github_api("GET", url, token, accept=ACCEPT_OBJETO)

    if status == 404:
        # 404 tambem acontece quando o token NAO enxerga o repositorio: conferir antes de liberar o push
        st_repo, _ = _github_api("GET", f"https://api.github.com/repos/{owner}/{repo}", token)
        if st_repo != 200:
            _log(f"Token sem acesso ao repositorio {owner}/{repo} (status {st_repo})")
            _set_status(False, f"O token nao tem acesso ao repositorio {owner}/{repo}",
                        "Gere um token com acesso a esse repositorio e troque o github_token nos Secrets.")
            return False
        _log("Banco ainda nao existe na nuvem (primeiro uso)")
        _set_status(True, "Primeiro uso: banco sera criado na nuvem")
        _estado["push_liberado"] = True
        return False

    if status != 200:
        _log(f"Pull falhou: status={status}")
        _set_status(False, f"Pull falhou (status {status})")
        return False

    # Tentar download_url primeiro (mais confiavel para arquivos grandes)
    # NOTA: download_url e uma URL de CDN/redirect — NAO enviar Authorization header
    download_url = data.get("download_url", "")
    # 1o pela API (sempre a versao mais nova). O download_url passa pelo CDN do GitHub, que pode
    # entregar uma versao de alguns minutos atras e fazer o app perder alteracoes recentes.
    db_bytes = _baixar_raw(url, token)

    if not db_bytes and download_url:
        _log(f"Baixando via download_url (sem auth)...")
        try:
            req = urllib_request.Request(download_url)
            req.add_header("User-Agent", "BorboletaApp")
            with urllib_request.urlopen(req, timeout=60) as resp:
                db_bytes = resp.read()
            _log(f"Download OK: {len(db_bytes)} bytes")
        except Exception as e:
            _log(f"download_url falhou: {e}, tentando base64...")
            db_bytes = None

    # Fallback: decodificar base64 do response da API
    if not db_bytes:
        content_b64 = data.get("content", "")
        if content_b64:
            _log("Usando base64 do response da API...")
            db_bytes = base64.b64decode(content_b64.replace("\n", ""))
        else:
            # Arquivo grande (> 1 MB): a API so manda o conteudo no formato "raw"
            db_bytes = _baixar_raw(url, token)
        if not db_bytes:
            _set_status(False, "Nenhum conteudo disponivel no GitHub")
            return False

    if len(db_bytes) < 1024:
        _log(f"Arquivo suspeito: apenas {len(db_bytes)} bytes!")
        _set_status(False, f"Arquivo muito pequeno ({len(db_bytes)} bytes)", "Possivel erro no download")
        return False

    # Salvar no disco
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "wb") as f:
        f.write(db_bytes)

    _log(f"Pull OK! {len(db_bytes)} bytes")
    _set_status(True, f"Pull OK ({len(db_bytes)} bytes)")
    _estado["push_liberado"] = True
    _gravar_marca(data.get("sha", ""))
    return True


def _push_database():
    """Envia o banco de dados atualizado para o GitHub."""
    _log("=== PUSH INICIANDO ===")
    token, owner, repo = _get_config()
    if not token:
        return False
    url_contents = f"https://api.github.com/repos/{owner}/{repo}/contents/{DB_REPO_PATH}?ref=main"
    if not _estado["push_liberado"] and not _tentar_liberar(url_contents, token):
        _log("Push BLOQUEADO: o pull nao deu certo nesta execucao")
        _set_status(False, "Os dados da nuvem nao carregaram (" + (_estado.get("erro_pull") or "motivo desconhecido")
                    + ") - nada foi salvo para nao apagar nada",
                    "Recarregue a pagina. Se continuar, confira o github_token nos Secrets.")
        return False

    # Ler o banco local
    if not os.path.exists(DB_PATH):
        _log(f"Banco nao encontrado: {DB_PATH}")
        _set_status(False, "Banco local nao encontrado")
        return False

    with open(DB_PATH, "rb") as f:
        db_bytes = f.read()

    db_size = len(db_bytes)
    db_hash = hashlib.md5(db_bytes).hexdigest()[:8]
    _log(f"Banco local: {db_size} bytes, hash={db_hash}")

    # Pegar o SHA atual do arquivo no GitHub (necessario para update)
    status, data = _github_api("GET", url_contents, token, accept=ACCEPT_OBJETO)

    sha = None
    if status == 200:
        sha = data.get("sha", "")
        _log(f"SHA no GitHub: {sha[:12]}...")
    elif status == 404:
        _log("Arquivo nao existe no GitHub, sera criado")
    else:
        _log(f"Erro ao buscar SHA: status={status}")
        _set_status(False, f"Erro ao buscar arquivo (status {status})", str(data))
        return False

    # Codificar em base64
    content_b64 = base64.b64encode(db_bytes).decode("utf-8")
    _log(f"Base64: {len(content_b64)} chars")

    # Montar payload
    payload = {
        "message": f"Atualiza banco via app ({db_hash})",
        "content": content_b64,
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    # Enviar via PUT (timeout maior para upload)
    _log("Enviando PUT...")
    status, data = _github_api("PUT", url_contents, token, payload, timeout=120)

    if status in (200, 201):
        new_sha = data.get("content", {}).get("sha", "?")
        _log(f"Push OK! status={status}, novo SHA={new_sha[:12] if len(new_sha) > 12 else new_sha}")
        _set_status(True, f"Salvo na nuvem! ({db_size} bytes)")
        _gravar_marca(new_sha if new_sha != "?" else "")
        return True
    else:
        error_msg = data.get("error", str(data))[:200]
        _log(f"Push FALHOU: status={status}, erro={error_msg}")
        _set_status(False, f"Push falhou (status {status})", error_msg)
        return False


def test_sync():
    """Testa se o sync esta funcionando. Retorna dict com diagnostico."""
    result = {
        "is_cloud": is_cloud(),
        "db_exists": os.path.exists(DB_PATH),
        "db_size": 0,
        "secrets_ok": False,
        "api_ok": False,
        "can_read": False,
        "can_write": False,
        "errors": [],
    }

    if result["db_exists"]:
        result["db_size"] = os.path.getsize(DB_PATH)

    # Mostrar chaves dos secrets para debug
    try:
        if hasattr(st.secrets, "keys"):
            result["secrets_keys"] = list(st.secrets.keys())
        result["has_github_token"] = "github_token" in st.secrets
        result["has_github_repo"] = "github_repo" in st.secrets
    except Exception as e:
        result["secrets_error"] = str(e)

    token, owner, repo = _get_config()
    if not token:
        result["errors"].append("Token/repo nao configurado")
        return result
    result["secrets_ok"] = True
    result["repo"] = f"{owner}/{repo}"

    # Testar leitura
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{DB_REPO_PATH}?ref=main"
    status, data = _github_api("GET", url, token, accept=ACCEPT_OBJETO)
    if status == 200:
        result["api_ok"] = True
        result["can_read"] = True
        result["github_sha"] = data.get("sha", "")[:12]
        result["github_size"] = data.get("size", 0)
    else:
        result["errors"].append(f"GET falhou: status={status}")

    return result


def is_cloud():
    """Detecta se esta rodando no Streamlit Cloud."""
    indicators = {
        "/mount/src": os.path.exists("/mount/src"),
        "STREAMLIT_SHARING_MODE": os.environ.get("STREAMLIT_SHARING_MODE") == "true",
        "IS_CLOUD": os.environ.get("IS_CLOUD", "") == "true",
        "HEADLESS": os.environ.get("STREAMLIT_SERVER_HEADLESS") == "true",
        "HOME_appuser": os.environ.get("HOME", "").startswith("/home/appuser"),
    }
    in_cloud = any(indicators.values())
    return in_cloud


IMPORT_DIR = "importar"


def importar_pendentes(aplicar):
    """Aplica cargas de dados deixadas em importar/*.json no repositorio de DADOS (privado).

    `aplicar(dados)` grava no banco local e devolve um resumo (ou None se ja tinha sido
    importado). Depois de salvar o banco na nuvem, apaga os arquivos aplicados.
    Retorna a lista de resumos.
    """
    token, owner, repo = _get_config()
    if not token or not _estado["push_liberado"]:
        return []
    base = f"https://api.github.com/repos/{owner}/{repo}/contents/{IMPORT_DIR}"
    status, itens = _github_api("GET", f"{base}?ref=main", token)
    if status != 200 or not isinstance(itens, list):
        return []
    aplicados, resumos = [], []
    for item in itens:
        if not item.get("name", "").endswith(".json"):
            continue
        st_arq, arq = _github_api("GET", item["url"], token)
        if st_arq != 200:
            continue
        try:
            dados = json.loads(base64.b64decode(arq.get("content", "").replace("\n", "")).decode("utf-8"))
            resumo = aplicar(dados)
        except Exception as e:
            _log(f"Importacao {item['name']} falhou: {e}")
            resumos.append(f"Erro ao importar {item['name']}: {e}")
            continue
        aplicados.append(item)
        if resumo:
            resumos.append(resumo)
    if aplicados and push_database():
        for item in aplicados:
            _github_api("DELETE", f"{base}/{item['name']}", token,
                        {"message": f"Importado pelo app: {item['name']}", "sha": item["sha"], "branch": "main"})
            _log(f"Importado e removido: {item['name']}")
    return resumos


def diagnostico():
    """Checklist da conexao com o repositorio de dados: lista de (ok, texto). Nunca mostra o token."""
    itens = []
    try:
        chaves = list(st.secrets.keys())
    except Exception:
        chaves = []
    for chave, nome in (("github_token", "Token do GitHub (github_token)"),
                        ("github_repo", "Repositório de dados (github_repo)"),
                        ("passwords", "Senhas ([passwords])")):
        itens.append((chave in chaves, f"{nome} {'configurado' if chave in chaves else 'FALTANDO'} nos Secrets"))

    token, owner, repo = _get_config()
    if not token:
        itens.append((False, "Sem token/repositório válidos nos Secrets — confira os nomes e as aspas"))
        return itens

    status, data = _github_api("GET", f"https://api.github.com/repos/{owner}/{repo}", token)
    if status == 200:
        itens.append((True, f"O token enxerga o repositório {owner}/{repo}"))
        pode = (data.get("permissions") or {}).get("push")
        itens.append((bool(pode), "O token pode gravar no repositório" if pode
                      else "O token NÃO tem permissão de gravar (precisa do escopo 'repo')"))
    elif status == 401:
        itens.append((False, "Token inválido ou expirado (erro 401) — gere um novo e troque nos Secrets"))
        return itens
    else:
        itens.append((False, f"O token não enxerga {owner}/{repo} (erro {status}) — nome do repositório errado "
                             "ou token sem acesso a ele"))
        return itens

    st_db, _ = _github_api("GET", f"https://api.github.com/repos/{owner}/{repo}/contents/{DB_REPO_PATH}?ref=main",
                           token, accept=ACCEPT_OBJETO)
    itens.append((st_db in (200, 404), "Banco de dados já existe na nuvem" if st_db == 200
                  else ("Banco ainda não foi criado na nuvem (nada foi salvo até agora)" if st_db == 404
                        else f"Erro ao procurar o banco na nuvem ({st_db})")))
    st_imp, arqs = _github_api("GET", f"https://api.github.com/repos/{owner}/{repo}/contents/{IMPORT_DIR}?ref=main",
                               token)
    n = len([a for a in arqs if a.get("name", "").endswith(".json")]) if st_imp == 200 and isinstance(arqs, list) else 0
    itens.append((True, f"{n} carga(s) de dados esperando importação" if n else "Nenhuma carga esperando importação"))
    itens.append((_estado["push_liberado"], "Salvamento na nuvem liberado nesta sessão" if _estado["push_liberado"]
                  else "Salvamento na nuvem BLOQUEADO nesta sessão (os dados da nuvem não carregaram)"))
    return itens
