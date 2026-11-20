# -*- coding: utf-8 -*-
# --- API do AuthPlayer: serve o site e responde /auth nos três modos. ---
import os
import sys
import time
from typing import Dict, Tuple

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

from core.msdk import AuthError, autenticar  # noqa: E402

app = Flask(__name__, static_folder=os.path.join(RAIZ, "public"), static_url_path="")
app.config["JSON_SORT_KEYS"] = False

TAMANHO_MAXIMO = 4096


@app.after_request
def _cabecalhos(resposta):
    # --- respostas de autenticação nunca devem ficar em cache. ---
    if request.path.startswith("/auth") or request.path.startswith("/api/"):
        resposta.headers["Access-Control-Allow-Origin"] = "*"
        resposta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resposta.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resposta.headers["Cache-Control"] = "no-store"
    elif resposta.mimetype in ("text/css", "application/javascript"):
        resposta.headers["Cache-Control"] = "public, max-age=3600"
    elif resposta.mimetype == "text/html":
        resposta.headers["Cache-Control"] = "no-cache"
    return resposta


@app.route("/")
def inicio():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/healthz")
def healthz():
    return jsonify({"servico": "AuthPlayer", "status": "online"})


def _pegar_parametros() -> Dict[str, str]:
    # --- POST com JSON é o preferido (o segredo não vai na URL); GET continua aceito. ---
    if request.method == "POST":
        corpo = request.get_json(silent=True) or {}
        origem = {chave: corpo.get(chave, "") for chave in ("eat", "jwt", "uid", "pass")}
    else:
        origem = {
            "eat": request.args.get("eat", ""),
            "jwt": request.args.get("jwt", ""),
            "uid": request.args.get("uid", ""),
            "pass": request.args.get("pass", ""),
        }

    parametros = {}
    for chave, valor in origem.items():
        texto = str(valor or "").strip()
        if len(texto) > TAMANHO_MAXIMO:
            raise AuthError("O campo %s é longo demais." % chave, "parametro_grande", 400)
        parametros[chave] = texto
    return parametros


@app.route("/auth", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/auth", methods=["GET", "POST", "OPTIONS"])
def autenticar_jogador():
    if request.method == "OPTIONS":
        return ("", 204)

    inicio = time.time()
    try:
        parametros = _pegar_parametros()
        if not (parametros["eat"] or parametros["jwt"] or (parametros["uid"] and parametros["pass"])):
            raise AuthError(
                "Use ?eat=TOKEN, ?jwt=TOKEN ou ?uid=ID&pass=SENHA.", "parametros_faltando", 400
            )
        resultado = autenticar(
            eat=parametros["eat"],
            jwt_token=parametros["jwt"],
            uid=parametros["uid"],
            senha=parametros["pass"],
        )
        return jsonify(resultado)
    except AuthError as erro:
        return jsonify({
            "ok": False,
            "codigo": erro.codigo,
            "erro": str(erro),
            "tempo_ms": int((time.time() - inicio) * 1000),
        }), erro.status
    except Exception:
        return jsonify({
            "ok": False,
            "codigo": "interno",
            "erro": "Algo falhou ao consultar a Garena. Tente de novo em alguns segundos.",
        }), 500


@app.errorhandler(404)
def _nao_achou(_erro):
    if request.path.startswith("/auth") or request.path.startswith("/api/"):
        return jsonify({"ok": False, "codigo": "rota", "erro": "Rota não encontrada."}), 404
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
