// Cloudflare Worker — Telegram Bot Webhook
// BEM-285 | Версия: v1.0 | Дата: 2026-05-02
//
// Деплой:
// 1. Зайди на workers.cloudflare.com
// 2. Создай новый Worker
// 3. Вставь этот код
// 4. Добавь переменные окружения:
//    TELEGRAM_BOT_TOKEN = твой токен
//    GITHUB_PAT = AI_SYSTEM_GITHUB_PAT (токен с repo+workflow правами)
//    GITHUB_REPO = bereznyi-aleksandr/ai-devops-system
//    ALLOWED_CHAT_ID = 601442777
// 5. Скопируй URL воркера (вида https://xxx.workers.dev)
// 6. Зарегистрируй webhook:
//    https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://xxx.workers.dev

const COMMANDS = {
  'статус': 'status',
  'status': 'status',
  'что': 'status',
  'как': 'status',
  'аналитик': 'analyst',
  'analyst': 'analyst',
  'запусти': 'analyst',
  'стоп': 'stop',
  'stop': 'stop',
  'помощь': 'help',
  'help': 'help',
};

async function sendTelegram(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: 'Markdown'
    })
  });
}

async function triggerGitHubAction(pat, repo, workflow, inputs) {
  const response = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${pat}`,
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: inputs
      })
    }
  );
  return response.status;
}

export default {
  async fetch(request, env) {
    if (request.method !== 'POST') {
      return new Response('OK', { status: 200 });
    }

    const body = await request.json();
    const message = body?.message;
    if (!message) return new Response('OK');

    const chatId = String(message.chat?.id);
    const text = (message.text || '').toLowerCase().trim();

    // Проверить что это разрешённый чат
    if (chatId !== String(env.ALLOWED_CHAT_ID)) {
      return new Response('Forbidden', { status: 403 });
    }

    const now = new Date().toLocaleTimeString('uk-UA', {
      timeZone: 'Europe/Kiev',
      hour: '2-digit',
      minute: '2-digit'
    });

    // Определить команду
    let command = null;
    for (const [keyword, cmd] of Object.entries(COMMANDS)) {
      if (text.includes(keyword)) {
        command = cmd;
        break;
      }
    }

    if (command === 'status') {
      // Запросить статус через GitHub Actions
      await triggerGitHubAction(
        env.GITHUB_PAT,
        env.GITHUB_REPO,
        'telegram-webhook.yml',
        { message: 'статус', chat_id: chatId }
      );
      await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId,
        `⏳ *${now} UA* | Запрашиваю статус системы...`);

    } else if (command === 'analyst') {
      await triggerGitHubAction(
        env.GITHUB_PAT,
        env.GITHUB_REPO,
        'telegram-webhook.yml',
        { message: 'запусти аналитика', chat_id: chatId }
      );
      await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId,
        `🔍 *${now} UA* | Запускаю @analyst...`);

    } else if (command === 'stop') {
      await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId,
        `⏸ *${now} UA* | Получена команда СТОП.`);

    } else if (command === 'help') {
      await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId,
        `*Команды куратора:*\n\n📊 *статус* — состояние системы\n🔍 *запусти аналитика* — запустить @analyst\n⏸ *стоп* — пауза\n❓ *помощь* — этот список`);

    } else {
      await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId,
        `💬 *${now} UA* | Не распознал: _${text}_\n\nНапиши *помощь* для списка команд.`);
    }

    return new Response('OK');
  }
};
