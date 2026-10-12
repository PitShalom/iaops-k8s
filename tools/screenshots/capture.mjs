// Gera as capturas de tela do laboratório, na ordem de um troubleshooting real.
//
// UIs reais (Grafana, Prometheus, Alertmanager) são capturadas diretamente.
// Saídas de terminal são o texto REAL dos comandos, renderizado em uma janela de terminal.
//
// Uso: node capture.mjs <diretorio-de-saida>
import { chromium } from "playwright";
import { execSync, spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { marked } from "marked";

const OUT = process.argv[2] || "./screenshots";
mkdirSync(OUT, { recursive: true });

const GRAFANA = "http://localhost:3000";
const AGENT = "http://localhost:8080";
const PROM = "http://localhost:9090";
const AM = "http://localhost:9093";
const GRAFANA_AUTH = "Basic " + Buffer.from("admin:iaops-lab").toString("base64");

const sh = (cmd) => {
  try {
    return execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 60000 });
  } catch (e) {
    return (e.stdout || "") + (e.stderr || "");
  }
};

// ---------- estilo ----------
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const hot = (s) =>
  esc(s).replace(
    /\b(CrashLoopBackOff|OOMKilled|Error|FATAL|ERROR|BackOff|Failed|137|Back-off)\b/g,
    '<span class="hot">$1</span>'
  );

const BASE_CSS = `
  * { box-sizing: border-box; }
  body { margin: 0; padding: 36px; background: #0d1117; font-family: 'Ubuntu', 'Cantarell', 'DejaVu Sans', sans-serif; }
`;

// Estilo GNOME Terminal do Ubuntu: fundo berinjela, Ubuntu Mono, controles à direita.
const PROMPT_USER = "sre@iaops-lab";
const PROMPT_DIR = "~/IAops-1";

function terminalHtml(title, blocks) {
  const body = blocks
    .map(
      (b) => `<div class="cmd"><span class="u">${PROMPT_USER}</span><span class="w">:</span><span class="d">${PROMPT_DIR}</span><span class="w">$</span> ${esc(b.cmd)}</div>` +
        `<pre>${hot(b.out.replace(/\s+$/, ""))}</pre>`
    )
    .join("");
  return `<html><head><style>
    * { box-sizing: border-box; }
    body { margin: 0; padding: 36px; background: #1e1e1e; }
    .term { width: 1280px; background: #300a24; border-radius: 9px 9px 0 0; overflow: hidden;
            box-shadow: 0 18px 44px rgba(0,0,0,.55), 0 0 0 1px #00000066; }
    .bar { background: #2b2b2b; height: 38px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px;
           border-bottom: 1px solid #00000055; font-family: 'Ubuntu', 'Cantarell', 'DejaVu Sans', sans-serif; }
    .t { color: #e8e8e8; font-size: 14px; font-weight: 500; flex: 1; text-align: center; padding-left: 90px; }
    .ctl { display: flex; gap: 10px; width: 90px; justify-content: flex-end; }
    .b { width: 22px; height: 22px; border-radius: 50%; background: #444; color: #ddd; font-size: 13px; line-height: 22px; text-align: center; }
    .b.x { background: #e95420; color: #fff; }
    .body { padding: 14px 18px 18px; font-family: 'Ubuntu Mono', 'DejaVu Sans Mono', 'Liberation Mono', monospace;
            font-size: 17px; line-height: 1.42; color: #eeeeec; }
    .cmd { margin-top: 8px; color: #ffffff; }
    .u { color: #8ae234; font-weight: 700; } .d { color: #729fcf; font-weight: 700; } .w { color: #ffffff; font-weight: 700; }
    pre { margin: 4px 0 8px; white-space: pre-wrap; word-break: break-word; font: inherit; color: #eeeeec; }
    .hot { color: #ef2929; font-weight: 700; }
  </style></head><body>
  <div class="term"><div class="bar">
    <span class="ctl"></span><span class="t">${esc(PROMPT_USER)}: ${esc(PROMPT_DIR)}</span>
    <span class="ctl"><span class="b">&#8211;</span><span class="b">&#9633;</span><span class="b x">&#215;</span></span></div>
  <div class="body">${body}</div></div></body></html>`;
}

function reportHtml(md, badge) {
  return `<html><head><style>${BASE_CSS}
    .card { width: 1100px; background: #161b22; border: 1px solid #30363d; border-radius: 14px; padding: 36px 44px;
            box-shadow: 0 20px 50px rgba(0,0,0,.5); color: #c9d1d9; line-height: 1.6; font-size: 16px; }
    .badge { display: inline-block; background: #1f6feb22; color: #58a6ff; border: 1px solid #1f6feb66; border-radius: 999px;
             padding: 4px 12px; font-size: 13px; font-weight: 600; margin-bottom: 14px; }
    h1 { font-size: 24px; color: #f0f6fc; margin: 0 0 6px; border: 0; }
    h2 { font-size: 15px; text-transform: uppercase; letter-spacing: .08em; color: #8b949e; margin: 26px 0 8px;
         border-top: 1px solid #30363d; padding-top: 18px; }
    ul { padding-left: 20px; } li { margin: 6px 0; }
    code { background: #0d1117; padding: 2px 6px; border-radius: 6px; font-size: 14px; }
    em { color: #8b949e; font-size: 13px; }
    hr { border: 0; border-top: 1px solid #30363d; margin: 24px 0 10px; }
  </style></head><body><div class="card"><span class="badge">${esc(badge)}</span>${marked.parse(md)}</div></body></html>`;
}

// ---------- captura ----------
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const done = [];

async function shotElement(name, html, selector) {
  await page.setContent(html, { waitUntil: "load" });
  await page.locator(selector).screenshot({ path: `${OUT}/${name}.png` });
  done.push(name);
}
async function shotPage(name, url, { ctx: c = ctx, wait = 3000, viewport, full = false, clip, mustNotContain } = {}) {
  const p = await c.newPage();
  if (viewport) await p.setViewportSize(viewport);
  for (let attempt = 1; attempt <= 3; attempt++) {
    await p.goto(url, { waitUntil: "networkidle", timeout: 60000 }).catch(() => {});
    await p.waitForTimeout(wait);
    // recusa páginas quebradas em vez de salvar uma captura inútil
    const broken = mustNotContain && (await p.content()).includes(mustNotContain);
    if (!broken) break;
    if (attempt === 3) {
      console.error(`AVISO: ${name} continua quebrada após 3 tentativas; captura descartada`);
      await p.close();
      return;
    }
  }
  await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: full, ...(clip ? { clip } : {}) });
  await p.close();
  done.push(name);
}

// port-forwards (Prometheus e Alertmanager não estão expostos no host)
const pf = [
  spawn("kubectl", ["-n", "monitoring", "port-forward", "svc/kps-prometheus", "9090:9090"], { stdio: "ignore" }),
  spawn("kubectl", ["-n", "monitoring", "port-forward", "svc/kps-alertmanager", "9093:9093"], { stdio: "ignore" }),
];
await new Promise((r) => setTimeout(r, 4000));

try {
  const pod = (app) =>
    sh(`kubectl get pod -n demo -l app=${app} -o jsonpath='{.items[0].metadata.name}'`).trim();
  const oom = pod("payments-api");
  const crash = pod("orders-worker");

  // 01 — o alerta chega (Alertmanager)
  // filtra só os alertas do laboratório (sem o ruído do próprio monitoramento)
  const amFilter = encodeURIComponent('{alertname=~"Demo.*"}');
  await shotPage("01-alertmanager-alertas", `${AM}/#/alerts?silenced=false&inhibited=false&filter=${amFilter}`, {
    wait: 4000,
    viewport: { width: 1500, height: 760 },
  });

  // 02 — primeiro passo do SRE: o que está quebrado?
  await shotElement(
    "02-kubectl-get-pods",
    terminalHtml("sre@iaops — troubleshooting", [{ cmd: "kubectl get pods -n demo", out: sh("kubectl get pods -n demo") }]),
    ".term"
  );

  // 03 — por que o payments-api morre?
  await shotElement(
    "03-kubectl-describe-oom",
    terminalHtml("sre@iaops — troubleshooting", [
      {
        cmd: `kubectl describe pod ${oom} -n demo | grep -E -A5 "Last State|Limits"`,
        out: sh(`kubectl describe pod ${oom} -n demo | grep -E -A5 "Last State|Limits"`),
      },
    ]),
    ".term"
  );

  // 04 — e o orders-worker? a resposta está no log do container anterior
  await shotElement(
    "04-kubectl-logs-previous",
    terminalHtml("sre@iaops — troubleshooting", [
      { cmd: `kubectl logs ${crash} -n demo --previous`, out: sh(`kubectl logs ${crash} -n demo --previous`) },
    ]),
    ".term"
  );

  // 05 — linha do tempo do kubelet
  await shotElement(
    "05-kubectl-events",
    terminalHtml("sre@iaops — troubleshooting", [
      {
        cmd: "kubectl get events -n demo --sort-by=.lastTimestamp | tail -12",
        out: sh("kubectl get events -n demo --sort-by=.lastTimestamp | tail -12"),
      },
    ]),
    ".term"
  );

  // 06 — Grafana: consumo por pod
  const gctx = await browser.newContext({
    viewport: { width: 1600, height: 1100 },
    deviceScaleFactor: 2,
    extraHTTPHeaders: { Authorization: GRAFANA_AUTH },
  });
  const search = await (
    await fetch(`${GRAFANA}/api/search?query=${encodeURIComponent("Compute Resources / Namespace (Pods)")}`, {
      headers: { Authorization: GRAFANA_AUTH },
    })
  ).json();
  if (search.length) {
    await shotPage(
      "06-grafana-recursos-namespace",
      `${GRAFANA}${search[0].url}?orgId=1&from=now-30m&to=now&var-namespace=demo&refresh=`,
      {
        ctx: gctx,
        wait: 10000,
        viewport: { width: 1600, height: 1100 },
        mustNotContain: "failed to load its application files",
      }
    );
  }
  await gctx.close();

  // 07 — regras de alerta próprias disparando (Prometheus)
  await shotPage("07-prometheus-alertas", `${PROM}/alerts?search=Demo`, {
    wait: 3500,
    viewport: { width: 1500, height: 900 },
    clip: { x: 0, y: 0, width: 1500, height: 480 }, // só o grupo iaops.demo
  });

  // 08/09 — o diagnóstico do agente
  const incidents = await (await fetch(`${AGENT}/incidents`)).json();
  const pick = (wl) => incidents.find((i) => i.workload === wl && i.mode !== "rules") || incidents.find((i) => i.workload === wl);
  let n = 8;
  for (const wl of ["payments-api", "orders-worker"]) {
    const inc = pick(wl);
    if (!inc) continue;
    const md = await (await fetch(`${AGENT}/incidents/${inc.id}/report`)).text();
    await shotElement(
      `${String(n).padStart(2, "0")}-agente-diagnostico-${wl}`,
      reportHtml(md, `IAops-1 · diagnóstico automático · backend: ${inc.mode}`),
      ".card"
    );
    n++;
  }

  // 10 — o agente trabalhando (logs)
  await shotElement(
    "10-agente-logs",
    terminalHtml("sre@iaops — aiops-agent", [
      { cmd: "kubectl logs -n aiops deploy/aiops-agent | grep incidente", out: sh("kubectl logs -n aiops deploy/aiops-agent | grep incidente | tail -8") },
    ]),
    ".term"
  );
} finally {
  pf.forEach((p) => p.kill());
  await browser.close();
}

console.log("Capturas geradas:\n" + done.map((d) => "  " + d + ".png").join("\n"));
