/* --- AuthPlayer: entradas, envio por POST e leitura da resposta. --- */

const form = document.getElementById("form-auth");
const modos = Array.from(document.querySelectorAll(".modo"));
const aviso = document.getElementById("aviso");
const carregando = document.getElementById("carregando");
const secaoResultado = document.getElementById("resultado");
const metaResultado = document.getElementById("resultado-meta");
const grade = document.getElementById("grade-resultado");
const listaAvisos = document.getElementById("lista-avisos");
const jsonResultado = document.getElementById("json-resultado");
const botao = form.querySelector("button[type=submit]");

const metaApi = document.querySelector('meta[name="authplayer-api"]');
const local = location.hostname === "localhost" || location.hostname === "127.0.0.1";
const API_BASE = local ? "" : ((metaApi && metaApi.content) || "").replace(/\/+$/, "");
const SEM_API = !local && !API_BASE;

let modoAtual = "eat";

function escapar(texto) {
  return String(texto === null || texto === undefined ? "" : texto)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function data(unix) {
  const valor = Number(unix || 0);
  if (!valor) return null;
  const d = new Date(valor * 1000);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

/* --- seleção da entrada --- */
function trocarModo(modo) {
  modoAtual = modo;
  modos.forEach((item) => {
    const ativo = item.dataset.modo === modo;
    item.classList.toggle("ativo", ativo);
    item.setAttribute("aria-selected", ativo ? "true" : "false");
  });
  document.querySelectorAll("[data-para]").forEach((bloco) => {
    bloco.hidden = bloco.dataset.para !== modo;
  });
  aviso.hidden = true;
  const primeiro = document.querySelector('[data-para="' + modo + '"] input, [data-para="' + modo + '"] textarea');
  if (primeiro) primeiro.focus();
}

modos.forEach((item) => item.addEventListener("click", () => trocarModo(item.dataset.modo)));

/* --- estados --- */
function limpar() {
  aviso.hidden = true;
  aviso.textContent = "";
  carregando.hidden = true;
  secaoResultado.hidden = true;
}

function mostrarAviso(mensagem) {
  aviso.textContent = mensagem;
  aviso.hidden = false;
}

function campo(rotulo, valor, destaque, copiavel) {
  const vazio = valor === null || valor === undefined || valor === "";
  const copia = copiavel && !vazio
    ? '<button class="copiar-mini" type="button" data-copiar="' + escapar(valor) + '">copiar</button>'
    : "";
  return '<div class="item">'
    + '<span class="rotulo">' + escapar(rotulo) + "</span>"
    + '<span class="valor' + (vazio ? " vazio" : "") + '">'
    + (vazio ? "—" : (destaque ? "<b>" + escapar(valor) + "</b>" : escapar(valor)))
    + copia + "</span></div>";
}

const METODOS = { eat: "access_token", jwt: "jwt", uid: "uid_pass" };

function mostrarResultado(dados) {
  const conta = dados.conta || {};
  const metodo = METODOS[dados.metodo] || dados.metodo || "—";

  document.getElementById("resposta-status").textContent = "200 OK";
  document.getElementById("conta-nome").textContent = conta.nome || "Conta identificada";
  document.getElementById("conta-sub").textContent =
    "UID " + (conta.uid || "—") + " · " + (conta.regiao || "região não informada") + " · " + metodo;
  metaResultado.textContent = metodo + " · " + (dados.tempo_ms || 0) + " ms";

  grade.innerHTML = [
    campo("UID", conta.uid, true, true),
    campo("Nome", conta.nome),
    campo("Região", conta.regiao, true),
    campo("Open ID", conta.open_id, false, true),
    campo("Access token", conta.access_token),
    campo("JWT", conta.jwt),
    campo("Expira em", data(conta.expira_em)),
    campo("Método", metodo),
    campo("Consultado em", data(dados.consultado_em)),
    campo("Tempo de resposta", (dados.tempo_ms || 0) + " ms"),
  ].join("");

  const avisos = dados.avisos || [];
  listaAvisos.innerHTML = avisos.map((item) => "<p>" + escapar(item) + "</p>").join("");
  listaAvisos.hidden = !avisos.length;

  jsonResultado.textContent = JSON.stringify(dados, null, 2);
  secaoResultado.hidden = false;
}

/* --- envio --- */
async function autenticar(corpo) {
  limpar();
  secaoResultado.hidden = false;
  carregando.hidden = false;
  botao.disabled = true;

  try {
    if (SEM_API) {
      mostrarAviso("A API não está hospedada neste momento. Rode api/app.py ou publique o serviço para consultar.");
      return;
    }
    const resposta = await fetch(API_BASE + "/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(corpo),
    });
    const dados = await resposta.json().catch(() => null);

    if (!resposta.ok || !dados || !dados.ok) {
      mostrarAviso((dados && dados.erro) || "Não foi possível autenticar agora.");
      return;
    }
    mostrarResultado(dados);
  } catch (erro) {
    mostrarAviso("A requisição não chegou à API. Verifique a conexão e tente de novo.");
  } finally {
    carregando.hidden = true;
    botao.disabled = false;
  }
}

form.addEventListener("submit", (evento) => {
  evento.preventDefault();

  if (modoAtual === "eat") {
    const eat = document.getElementById("eat").value.trim();
    if (!eat) { mostrarAviso("Cole o access token para continuar."); return; }
    autenticar({ eat: eat });
    return;
  }

  if (modoAtual === "jwt") {
    const jwt = document.getElementById("jwt").value.trim();
    if (!jwt) { mostrarAviso("Cole o JWT para continuar."); return; }
    autenticar({ jwt: jwt });
    return;
  }

  const uid = document.getElementById("uid").value.replace(/\D/g, "");
  const senha = document.getElementById("pass").value;
  if (uid.length < 5) { mostrarAviso("O UID precisa ter pelo menos 5 dígitos."); return; }
  if (!senha) { mostrarAviso("Informe a senha da conta."); return; }
  document.getElementById("uid").value = uid;
  autenticar({ uid: uid, pass: senha });
});

document.getElementById("uid").addEventListener("input", (evento) => {
  evento.target.value = evento.target.value.replace(/\D/g, "").slice(0, 15);
});

/* --- copiar --- */
document.addEventListener("click", async (evento) => {
  const alvo = evento.target.closest("[data-copiar], .botao-copy[data-alvo]");
  if (!alvo) return;
  const valor = alvo.dataset.copiar || (document.getElementById(alvo.dataset.alvo) || {}).textContent;
  if (!valor) return;
  try {
    await navigator.clipboard.writeText(valor);
    const texto = alvo.textContent;
    alvo.textContent = "copiado";
    setTimeout(() => { alvo.textContent = texto; }, 1300);
  } catch (erro) {
    alvo.textContent = "selecione e copie";
  }
});
