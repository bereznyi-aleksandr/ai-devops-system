#!/usr/bin/env python3
"""
Provider Live Limit Probe — E5-002
Проверяет доступность провайдеров и обновляет provider_status.json
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_STATUS = ROOT / 'governance/state/provider_status.json'
PROVIDER_FAILURES = ROOT / 'governance/events/provider_failures.jsonl'

UNHEALTHY = {'limited', 'error', 'runner_unavailable', 'disabled', 'disabled_until_runner_ready', 'cooldown'}


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load_status():
    if PROVIDER_STATUS.exists():
        return json.loads(PROVIDER_STATUS.read_text(encoding='utf-8'))
    return {'version': 1, 'updated_at': now_iso(), 'providers': {}}


def save_status(data):
    data['updated_at'] = now_iso()
    PROVIDER_STATUS.parent.mkdir(parents=True, exist_ok=True)
    PROVIDER_STATUS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def append_failure(provider, failure_type, note):
    PROVIDER_FAILURES.parent.mkdir(parents=True, exist_ok=True)
    entry = {'timestamp': now_iso(), 'provider': provider,
             'failure_type': failure_type, 'note': note}
    with PROVIDER_FAILURES.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def probe_claude():
    """
    Probe Claude через наличие CLAUDE_CODE_OAUTH_TOKEN и базовую проверку.
    В production: проверить через claude-code-action или API-токен.
    """
    token = os.environ.get('CLAUDE_CODE_OAUTH_TOKEN') or os.environ.get('ANTHROPIC_API_KEY')
    if not token:
        return 'unknown', 'no_token_available'

    # Проверяем через Anthropic API (минимальный запрос)
    try:
        data = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 1,
            'messages': [{'role': 'user', 'content': 'ping'}]
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=data,
            headers={
                'x-api-key': token,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return 'ok', 'probe_success'
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return 'limited', f'http_429_rate_limit'
        if e.code in (529, 503, 500):
            return 'error', f'http_{e.code}_api_error'
        return 'error', f'http_{e.code}'
    except Exception as ex:
        return 'unknown', str(ex)[:200]

    return 'ok', 'probe_success'


def probe_gpt():
    """Probe GPT через OpenAI API."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return 'unknown', 'no_openai_api_key'

    try:
        data = json.dumps({
            'model': 'gpt-4o-mini',
            'input': [{'role': 'user', 'content': 'ping'}],
            'max_output_tokens': 1
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.openai.com/v1/responses',
            data=data,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return 'ok', 'probe_success'
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return 'limited', 'http_429_rate_limit'
        if e.code in (503, 500):
            return 'error', f'http_{e.code}_api_error'
        return 'error', f'http_{e.code}'
    except Exception as ex:
        return 'unknown', str(ex)[:200]

    return 'ok', 'probe_success'


def probe_gpt_codex():
    """GPT Codex — проверяем статус runner через наличие self-hosted runner."""
    # Нет прямого способа проверить self-hosted runner без GitHub API
    # Возвращаем текущий статус из файла — runner unavailable пока не восстановлен
    status_data = load_status()
    current = status_data.get('providers', {}).get('gpt_codex', {})
    current_status = current.get('status', 'unknown')
    if current_status in ('disabled_until_runner_ready', 'runner_unavailable', 'error'):
        return current_status, 'runner_not_available_no_self_hosted'
    return 'unknown', 'cannot_probe_without_runner'


def run_probes(providers_to_probe=None):
    """Run probes and update provider_status.json."""
    status_data = load_status()
    providers = status_data.setdefault('providers', {})

    probers = {
        'claude': probe_claude,
        'gpt': probe_gpt,
        'gpt_codex': probe_gpt_codex,
    }

    if providers_to_probe:
        probers = {k: v for k, v in probers.items() if k in providers_to_probe}

    results = {}
    for provider, probe_fn in probers.items():
        print(f'Probing {provider}...')
        try:
            new_status, reason = probe_fn()
        except Exception as ex:
            new_status, reason = 'unknown', str(ex)[:200]

        p = providers.setdefault(provider, {})
        old_status = p.get('status', 'unknown')
        p['status'] = new_status
        p['last_probe_at'] = now_iso()
        p['probe_reason'] = reason

        if new_status != 'ok':
            p['last_failure_at'] = now_iso()
            p['last_failure_type'] = reason
            if new_status not in UNHEALTHY or old_status != new_status:
                append_failure(provider, reason, f'probe: {new_status}')
        else:
            p['failure_count'] = 0
            p['last_failure_type'] = None

        results[provider] = new_status
        print(f'  {provider}: {old_status} → {new_status} ({reason})')

    save_status(status_data)
    return results


if __name__ == '__main__':
    import sys
    providers = sys.argv[1:] if len(sys.argv) > 1 else None
    results = run_probes(providers)
    print(f'PROBE RESULTS: {results}')
    # Exit 1 if all unhealthy
    if all(s in UNHEALTHY or s == 'unknown' for s in results.values()):
        print('ALL_PROVIDERS_UNHEALTHY')
        sys.exit(1)
    sys.exit(0)
