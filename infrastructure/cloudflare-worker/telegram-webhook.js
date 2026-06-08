// Cloudflare Worker: Telegram Webhook → GitHub Actions dispatch
// Деплой: https://dash.cloudflare.com → Workers → Create Worker → вставить этот код
// После деплоя зарегистрировать webhook:
// curl "https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://{worker}.workers.dev/webhook"

const ALLOWED_CHAT_ID = "601442777";

export default {
  async fetch(request, env) {
    // Только POST на /webhook
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
    if (!msg) return new Response("no message", { status: 200 });

    // Только от оператора
    if (String(msg.chat?.id) !== ALLOWED_CHAT_ID) {
      return new Response("not allowed", { status: 200 });
    }

    const text = msg.text || "";
    const updateId = String(update.update_id);
    const now = new Date().toISOString().replace(/[-:.]/g, "").slice(0, 15) + "Z";
    const traceId = `tg_${updateId}_${now}`;

    // Dispatch GitHub Actions workflow (codex-local.yml с role=curator)
    const dispatchUrl = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/codex-local.yml/dispatches`;
    const dispatchBody = JSON.stringify({
      ref: "main",
      inputs: {
        role: "curator",
        provider: "gpt_codex",
        trace_id: traceId,
        cycle_id: "telegram_operator_message",
        task_type: "telegram_operator_message",
        task: text,
        chat_id: String(msg.chat.id),
        message_id: String(msg.message_id),
      },
    });

    const dispatchResp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_PAT}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: dispatchBody,
    });

    // Подтверждение оператору в Telegram
    const replyText = dispatchResp.ok
      ? `⚡ Получено. Передано куратору (trace: ${traceId})`
      : `⚠️ Ошибка dispatch: ${dispatchResp.status}`;

    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: msg.chat.id, text: replyText }),
    });

    return new Response("ok", { status: 200 });
  },
};
