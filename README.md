# AuthPlayer

Autenticação de conta do Free Fire em três modos: **access token (EAT)**, **JWT** ou **UID + senha**. Site e API no mesmo serviço.

- Site: https://ramonmods.github.io/AuthPlayer/

## Modos

| Modo | O que você tem | Como chamar |
|---|---|---|
| Access token | `access_token` da conta Garena | `/auth?eat=TOKEN` |
| JWT | token do servidor de jogo | `/auth?jwt=TOKEN` |
| UID + senha | credenciais da conta | `/auth?uid=13775111115&pass=SENHA` |

O modo UID + senha troca as credenciais por `access_token` + `open_id` e depois valida o token no callback da Garena. O modo JWT lê as claims localmente, sem chamar a Garena e sem verificar assinatura.

## API

```
POST /auth
Content-Type: application/json

{"jwt": "eyJhbGciOi...."}
```

GET também funciona (`/auth?eat=...`). Alias: `/api/auth`. CORS liberado, `Cache-Control: no-store`.

```json
{
  "ok": true,
  "metodo": "jwt",
  "conta": {
    "uid": "13775111115",
    "nome": "JOgAdOr_FF",
    "regiao": "BR",
    "open_id": null,
    "access_token": null,
    "jwt": "eyJhbGciOi… (741 caracteres)",
    "expira_em": 1795222540
  },
  "avisos": ["JWT é lido localmente, sem chamar a Garena. Assinatura não é verificada."],
  "consultado_em": 1795193740,
  "tempo_ms": 0
}
```

Tokens e JWTs **nunca** voltam completos: só um trecho e o tamanho. A senha não aparece em lugar nenhum da resposta.

Erros vêm com `ok: false`, `codigo` e `erro`:

| HTTP | `codigo` | Quando acontece |
|---|---|---|
| 400 | `parametros_faltando` | Nenhum modo foi informado |
| 400 | `uid_invalido` / `senha_vazia` | UID ou senha inválidos |
| 400 | `jwt_invalido` | JWT não tem três partes ou claims ilegíveis |
| 400 | `token_invalido` | Access token muito curto |
| 401 | `credenciais_invalidas` | Garena recusou UID ou senha |
| 401 | `token_invalido` / `jwt_expirado` | Token recusado ou vencido |
| 502 | `garena_indisponivel` | Garena não respondeu |
| 500 | `interno` | Falha inesperada |

## Rodando local

```bash
pip install -r api/requirements.txt
python api/app.py
```

Abre em `http://127.0.0.1:5000` (use `PORT` para trocar a porta). Nada é salvo em disco ou banco.

## Estrutura

```
api/       Flask: site, /healthz e /auth
core/      cliente MSDK (grant, callback, JWT) e normalização da resposta
public/    site (HTML, CSS, JS, ícones e fontes)
render.yaml  serviço da API
```

---

Se o AuthPlayer te ajudou, um café ajuda a manter os testes de API no ar: **[pixgg.com/ramon](https://pixgg.com/ramon)**
