// Cloudflare Worker: Telegram Webhook → GitHub Actions dispatch
// BEM-932-D: routes operator messages through provider-router by default.
// Feature flag: ROUTER_WORKFLOW_ID (default: provider-router.yml).
// Legacy codex-local.yml remains supported when ROUTER_WORKFLOW_ID explicitly points to it.

const ALLOWED_CHAT_ID = "601442777";
const DEFAULT_ROUTER_WORKFLOW_ID = "provider-router.yml";

async function sendTelegram(env, chatId, text) {
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

function routerWorkflowId(env) {
  const configured = String(env.ROUTER_WORKFLOW_ID || "").trim();
  return configured || DEFAULT_ROUTER_WORKFLOW_ID;
}

function makeTraceId(updateId) {
  const now = new Date().toISOString().replace(/[-:.]/g, "").slice(0, 15) + "Z";
  return `tg_${updateId}_${now}`;
}

function workflowInputsFor(workflowId, msg, text, traceId) {
  const chatId = String(msg.chat.id);
  const messageId = String(msg.message_id || "");
  const taskWithTelegramMeta = [
    text,
    "",
    `telegram_chat_id=${chatId}`,
    `telegram_message_id=${messageId}`,
  ].join("\n");

  const common = {
    role: "curator",
    trace_id: traceId,
    cycle_id: "telegram_operator_message",
    task_type: "telegram_operator_message",
    task: taskWithTelegramMeta,
  };

  if (workflowId === "provider-router.yml" || workflowId === "provider-router.yaml") {
    return {
      ...common,
      chat_id: chatId,
      message_id: messageId,
      task: text,
    };
  }

  return {
    ...common,
    provider: "gpt_codex",
  };
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("bad json", { status: 400 });
    }

    const msg = update?.message;
    if (!msg) {
      return new Response("no message", { status: 200 });
    }

    const chatId = String(msg.chat?.id || "");
    if (chatId !== ALLOWED_CHAT_ID) {
      return new Response("not allowed", { status: 200 });
    }

    const text = msg.text || "";
    const updateId = String(update.update_id || "missing");
    const traceId = makeTraceId(updateId);
    const workflowId = routerWorkflowId(env);

    const dispatchUrl = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/${workflowId}/dispatches`;
    const dispatchBody = JSON.stringify({
      ref: "main",
      inputs: workflowInputsFor(workflowId, msg, text, traceId),
    });

    const dispatchResp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_PAT}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-devops-system-cloudflare-worker",
      },
      body: dispatchBody,
    });

    if (dispatchResp.ok) {
      await sendTelegram(env, chatId, `⚙️ Получено. Передано в ${workflowId} (trace: ${traceId})`);
      return new Response("ok", { status: 200 });
    }

    let details = "";
    try {
      details = await dispatchResp.text();
    } catch {}

    const safeDetails = details ? `\n${details.slice(0, 500)}` : "";
    await sendTelegram(env, chatId, `⚠️ Ошибка dispatch ${workflowId}: ${dispatchResp.status}${safeDetails}`);
    return new Response(`dispatch failed: ${dispatchResp.status}`, { status: 200 });
  },
};
