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
DB_REPO_PATH = "data/borboleta.db"

# Status do ultimo sync (visivel na sidebar)
_last_sync_status = {"ok": None, "msg": "", "detail": ""}


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


def _github_api(method, url, token, data=None, timeout=60):
    """Faz uma chamada a API do GitHub."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
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


def pull_database():
    """Baixa o banco de dados mais recente do GitHub."""
    _log("=== PULL INICIANDO ===")
    token, owner, repo = _get_config()
    if not token:
        return False

    # Primeiro tenta pegar info do arquivo
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{DB_REPO_PATH}?ref=main"
    status, data = _github_api("GET", url, token)

    if status != 200:
        _log(f"Pull falhou: status={status}")
        _set_status(False, f"Pull falhou (status {status})")
        return False

    # Tentar download_url primeiro (mais confiavel para arquivos grandes)
    # NOTA: download_url e uma URL de CDN/redirect — NAO enviar Authorization header
    download_url = data.get("download_url", "")
    db_bytes = None

    if download_url:
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
    return True


def push_database():
    """Envia o banco de dados atualizado para o GitHub."""
    _log("=== PUSH INICIANDO ===")
    token, owner, repo = _get_config()
    if not token:
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
    url_contents = f"https://api.github.com/repos/{owner}/{repo}/contents/{DB_REPO_PATH}?ref=main"
    status, data = _github_api("GET", url_contents, token)

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
    status, data = _github_api("GET", url, token)
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
