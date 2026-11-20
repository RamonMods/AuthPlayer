# -*- coding: utf-8 -*-
# --- Autenticação Free Fire: Access Token, JWT e UID+senha. ---
import base64
import json
import re
import time
import warnings
from typing import Dict, Optional

import requests
from urllib.parse import parse_qs, urlparse
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# --- endpoints da Garena usados pelo cliente do jogo. ---
MSDK_REGISTER = "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest:register"
MSDK_GRANT = "https://100067.connect.garena.com/oauth/guest/token/grant"
MSDK_GRANT_ALT = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
GARENA_CALLBACK = "https://api-otrss.garena.com/support/callback/"

CLIENT_ID = "100067"
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
USER_AGENT = "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt;BR;)"

ERROS_CALLBACK = {
    "no_character": "Essa conta não tem personagem criado no Free Fire.",
    "err_access_token": "O access token é inválido ou expirou.",
    "invalid_token": "O access token é inválido ou expirou.",
}


class AuthError(Exception):
    # --- erro de autenticação com código para a API. ---
    def __init__(self, mensagem: str, codigo: str = "autenticacao", status: int = 401):
        super().__init__(mensagem)
        self.codigo = codigo
        self.status = status


def _sessao() -> requests.Session:
    sessao = requests.Session()
    sessao.verify = False
    return sessao


def _mascara(valor, visiveis: int = 10) -> Optional[str]:
    # --- nunca devolve o segredo inteiro. ---
    if valor is None or valor == "":
        return None
    texto = str(valor)
    if len(texto) <= visiveis + 4:
        return texto[:visiveis] + "…"
    return texto[:visiveis] + "… (" + str(len(texto)) + " caracteres)"


# --- modo 3: troca UID + senha por access_token e open_id. ---
def login_uid_senha(uid: str, senha: str, timeout: int = 20) -> Dict[str, str]:
    if not re.match(r"^\d{5,15}$", uid or ""):
        raise AuthError("O UID precisa ter de 5 a 15 dígitos.", "uid_invalido", 400)
    if not senha:
        raise AuthError("Informe a senha da conta.", "senha_vazia", 400)

    corpo = {
        "uid": uid,
        "password": senha,
        "response_type": "token",
        "client_type": "2",
        "client_secret": CLIENT_SECRET,
        "client_id": CLIENT_ID,
    }
    sessao = _sessao()
    for url in (MSDK_GRANT, MSDK_GRANT_ALT):
        try:
            resposta = sessao.post(
                url, data=corpo, timeout=timeout,
                headers={"User-Agent": USER_AGENT, "Connection": "Keep-Alive"},
            )
        except requests.RequestException:
            continue
        if resposta.status_code != 200:
            continue
        dados = resposta.json() if resposta.content else {}
        if dados.get("access_token"):
            return {
                "access_token": dados["access_token"],
                "open_id": dados.get("open_id"),
                "expires_in": int(dados.get("expires_in") or 0),
            }
    raise AuthError("A Garena recusou o UID ou a senha.", "credenciais_invalidas", 401)


# --- modo 1: valida o access token e lê os dados da conta. ---
def validar_access_token(access_token: str, timeout: int = 20) -> Dict:
    if not access_token or len(access_token) < 20:
        raise AuthError("Informe um access token válido.", "token_invalido", 400)

    sessao = _sessao()
    try:
        resposta = sessao.get(
            GARENA_CALLBACK,
            params={"access_token": access_token},
            allow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
    except requests.RequestException:
        raise AuthError("Não foi possível falar com a Garena agora.", "garena_indisponivel", 502)

    destino = resposta.headers.get("Location", "")
    if not (300 <= resposta.status_code < 400 and destino):
        raise AuthError("A Garena não reconheceu esse access token.", "token_invalido", 401)

    consulta = parse_qs(urlparse(destino).query)
    if "err" in consulta:
        codigo = consulta["err"][0]
        raise AuthError(
            ERROS_CALLBACK.get(codigo, "A Garena recusou esse access token (%s)." % codigo),
            "token_invalido", 401,
        )

    conta_id = consulta.get("account_id", [None])[0]
    if not conta_id:
        raise AuthError("A Garena não devolveu o UID dessa conta.", "token_invalido", 401)

    return {
        "uid": str(conta_id),
        "nome": consulta.get("nickname", [None])[0],
        "regiao": (consulta.get("region", [None])[0] or "").upper() or None,
        "access_token": consulta.get("access_token", [access_token])[0],
    }


# --- modo 2: lê as claims do JWT sem verificar a assinatura. ---
def decodificar_jwt(token: str) -> Dict:
    partes = (token or "").split(".")
    if len(partes) != 3:
        raise AuthError("Isso não é um JWT (esperava-se três partes).", "jwt_invalido", 400)

    try:
        bloco = partes[1] + "=" * (-len(partes[1]) % 4)
        dados = json.loads(base64.urlsafe_b64decode(bloco.encode("ascii")))
    except Exception:
        raise AuthError("Não foi possível ler as claims desse JWT.", "jwt_invalido", 400)

    if not dados.get("account_id"):
        raise AuthError("Esse JWT não tem account_id.", "jwt_invalido", 400)

    expiracao = int(dados.get("exp") or 0)
    if expiracao and expiracao < int(time.time()):
        raise AuthError("Esse JWT expirou.", "jwt_expirado", 401)

    return {
        "uid": str(dados.get("account_id")),
        "nome": dados.get("nickname"),
        "regiao": (dados.get("lock_region") or dados.get("country_code") or "").upper() or None,
        "expira_em": expiracao or None,
        "claims": dados,
    }


# --- normaliza a resposta dos três modos. ---
def autenticar(eat: str = "", jwt_token: str = "", uid: str = "", senha: str = "") -> Dict:
    inicio = time.time()
    avisos = []
    conta: Dict = {}

    if eat:
        dados = validar_access_token(eat)
        metodo = "access_token"
        conta = {
            "uid": dados["uid"],
            "nome": dados["nome"],
            "regiao": dados["regiao"],
            "open_id": None,
            "access_token": _mascara(dados["access_token"]),
            "jwt": None,
            "expira_em": None,
        }
        avisos.append("O open_id não vem no callback da Garena; ele só aparece no modo UID + senha.")

    elif jwt_token:
        dados = decodificar_jwt(jwt_token)
        metodo = "jwt"
        conta = {
            "uid": dados["uid"],
            "nome": dados["nome"],
            "regiao": dados["regiao"],
            "open_id": dados["claims"].get("external_uid"),
            "access_token": None,
            "jwt": _mascara(jwt_token),
            "expira_em": dados["expira_em"],
        }
        avisos.append("JWT é lido localmente, sem chamar a Garena. Assinatura não é verificada.")

    elif uid and senha:
        dados = login_uid_senha(uid, senha)
        metodo = "uid_pass"
        conta = {
            "uid": uid,
            "nome": None,
            "regiao": None,
            "open_id": dados.get("open_id"),
            "access_token": _mascara(dados["access_token"]),
            "jwt": None,
            "expira_em": int(time.time()) + dados["expires_in"] if dados["expires_in"] else None,
        }
        try:
            validado = validar_access_token(dados["access_token"])
            conta["uid"] = validado["uid"]
            conta["nome"] = validado["nome"]
            conta["regiao"] = validado["regiao"]
        except AuthError as erro:
            avisos.append("Login aceito, mas a Garena não devolveu o perfil: " + str(erro))

    else:
        raise AuthError("Escolha um dos três modos.", "parametros_faltando", 400)

    return {
        "ok": True,
        "metodo": metodo,
        "conta": conta,
        "avisos": avisos,
        "consultado_em": int(time.time()),
        "tempo_ms": int((time.time() - inicio) * 1000),
    }
