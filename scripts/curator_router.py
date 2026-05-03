#!/usr/bin/env python3
"""
Curator Router — CURATOR_PROVIDER_FAILOVER_V1
Версия: v1.0 | Дата: 2026-05-03

Детерминированный роутер куратора.
Читает routing.json и provider_status.json.
Классифицирует ошибки провайдеров.
Выбирает активный backend.
"""

import json
import os
import sys
from datetime import datetime, timezone


ROUTING_FILE = "governance/state/routing.json"
PROVIDER_STATUS_FILE = "governance/state/provider_status.json"
PROVIDER_FAILURES_FILE = "governance/events/provider_failures.jsonl"
ROUTING_DECISIONS_FILE = "governance/events/routing_decisions.jsonl"

# Классификация ошибок
PROVIDER_LIMIT_PATTERNS = [
    "you've hit your limit",
    "resets at",
    "http 429",
    "rate limit",
    "usage limit",
    "quota exceeded",
]

API_ERROR_PATTERNS = [
    "http 5",
    "internal server error",
    "service unavailable",
    "bad gateway",
]

CONFIG_ERROR_PATTERNS = [
    "missing secret",
    "invalid workflow",
    "yaml syntax",
    "not found",
    "permission denied",
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_jsonl(path, entry):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def classify_error(error_text):
    """Классифицирует тип ошибки провайдера."""
    text = (error_text or "").lower()

    for pattern in PROVIDER_LIMIT_PATTERNS:
        if pattern in text:
            return "provider_limit"

    for pattern in API_ERROR_PATTERNS:
        if pattern in text:
            return "api_error"

    for pattern in CONFIG_ERROR_PATTERNS:
        if pattern in text:
            return "config_error"

    if "timeout" in text:
        return "timeout"

    if "permission" in text or "forbidden" in text:
        return "permission_error"

    return "unknown"


def should_switch(failure_type, failure_count, switch_after):
    """Определяет нужно ли переключить провайдера."""
    # provider_limit — переключаем немедленно
    if failure_type == "provider_limit":
        return True
    # api_error — переключаем после N ошибок подряд
    if failure_type == "api_error" and failure_count >= switch_after:
        return True
    # config_error, permission_error, timeout — не переключаем, это ремонтная ошибка
    return False


def record_failure(provider, failure_type, error_excerpt, provider_status, routing):
    """Записывает ошибку провайдера и обновляет статус."""
    ts = now_iso()
    providers = provider_status.get("providers", {})
    p = providers.get(provider, {})

    p["last_failure_at"] = ts
    p["last_failure_type"] = failure_type
    p["last_error_excerpt"] = error_excerpt[:200] if error_excerpt else None
    p["failure_count"] = p.get("failure_count", 0) + 1

    switch_after = routing.get("policy", {}).get("switch_after_failures", 2)
    current_failure_count = p["failure_count"]

    if should_switch(failure_type, current_failure_count, switch_after):
        p["status"] = "limited"
    else:
        p["status"] = "error"

    providers[provider] = p
    provider_status["providers"] = providers
    provider_status["updated_at"] = ts

    append_jsonl(PROVIDER_FAILURES_FILE, {
        "timestamp": ts,
        "provider": provider,
        "failure_type": failure_type,
        "failure_count": current_failure_count,
        "error_excerpt": error_excerpt[:200] if error_excerpt else None
    })

    return p["status"], current_failure_count


def record_success(provider, provider_status):
    """Записывает успех провайдера."""
    ts = now_iso()
    providers = provider_status.get("providers", {})
    p = providers.get(provider, {})
    p["status"] = "ok"
    p["last_success_at"] = ts
    p["failure_count"] = 0
    p["last_failure_type"] = None
    providers[provider] = p
    provider_status["providers"] = providers
    provider_status["updated_at"] = ts


def decide_backend(routing, provider_status):
    """
    Главная функция: выбирает активный backend для куратора.
    Возвращает: (backend_name, reason)
    """
    roles = routing.get("roles", {})
    curator_config = roles.get("curator", {})
    current_active = curator_config.get("active", "claude")
    primary = curator_config.get("primary", "claude")
    reserve = curator_config.get("reserve", "gpt_hosted_fallback")
    policy = routing.get("policy", {})
    switch_after = policy.get("switch_after_failures", 2)

    providers = provider_status.get("providers", {})

    # Проверить статус текущего активного провайдера
    # Нормализуем имя провайдера для provider_status
    primary_key = "claude" if "claude" in primary else "gpt"
    reserve_key = "gpt" if "gpt" in reserve else "claude"

    primary_status = providers.get(primary_key, {}).get("status", "unknown")
    primary_failures = providers.get(primary_key, {}).get("failure_count", 0)
    primary_failure_type = providers.get(primary_key, {}).get("last_failure_type")

    # Если primary OK или неизвестен — использовать primary
    if primary_status in ("ok", "unknown"):
        return primary, f"primary provider {primary_key} is {primary_status}"

    # Если primary ограничен — переключить на reserve
    if primary_status == "limited" or (
        primary_status == "error" and primary_failures >= switch_after
        and should_switch(primary_failure_type, primary_failures, switch_after)
    ):
        reserve_status = providers.get(reserve_key, {}).get("status", "unknown")
        if reserve_status not in ("limited", "error"):
            return reserve, f"primary {primary_key} is {primary_status}, switching to reserve {reserve_key}"
        else:
            return None, f"degraded mode: both {primary_key} and {reserve_key} are unavailable"

    return primary, f"using primary {primary_key} (status: {primary_status})"


def make_routing_decision(backend, reason, routing, provider_status):
    """Записывает решение о маршрутизации."""
    ts = now_iso()
    decision = {
        "timestamp": ts,
        "backend": backend,
        "reason": reason,
        "routing_snapshot": {
            "curator_active": routing.get("roles", {}).get("curator", {}).get("active"),
        },
        "provider_snapshot": {
            k: v.get("status") for k, v in provider_status.get("providers", {}).items()
        }
    }
    append_jsonl(ROUTING_DECISIONS_FILE, decision)
    return decision


def update_routing_active(routing, role, new_active):
    """Обновляет активный провайдер для роли в routing.json."""
    roles = routing.get("roles", {})
    if role in roles:
        roles[role]["active"] = new_active
        routing["roles"] = roles
        routing["updated_at"] = now_iso()


def route(role="curator", error_text=None, success=False):
    """
    Основная точка входа роутера.

    role: логическая роль (curator, analyst, auditor, executor)
    error_text: текст ошибки если был failure
    success: True если предыдущий запуск был успешным
    """
    # Загрузить состояние
    try:
        routing = load_json(ROUTING_FILE)
    except FileNotFoundError:
        print(f"ERROR: {ROUTING_FILE} not found")
        sys.exit(1)

    try:
        provider_status = load_json(PROVIDER_STATUS_FILE)
    except FileNotFoundError:
        provider_status = {"version": 1, "updated_at": now_iso(), "providers": {}}

    # Получить текущий активный провайдер для роли
    roles = routing.get("roles", {})
    role_config = roles.get(role, {})
    current_active = role_config.get("active", "claude")

    # Нормализовать имя провайдера
    provider_key = "claude" if "claude" in current_active else "gpt"

    # Обработать success/failure
    if success:
        record_success(provider_key, provider_status)
        print(f"SUCCESS recorded for {provider_key}")
    elif error_text:
        failure_type = classify_error(error_text)
        status, count = record_failure(
            provider_key, failure_type, error_text, provider_status, routing
        )
        print(f"FAILURE recorded: {provider_key} → {failure_type} (count={count}, status={status})")

        # Проверить нужно ли переключить
        if should_switch(failure_type, count, routing.get("policy", {}).get("switch_after_failures", 2)):
            # Определить reserve
            reserve = role_config.get("reserve", "gpt_hosted_fallback")
            old_active = current_active
            update_routing_active(routing, role, reserve)
            print(f"SWITCHING {role}: {old_active} → {reserve}")

    # Принять решение о backend
    backend, reason = decide_backend(routing, provider_status)
    decision = make_routing_decision(backend, reason, routing, provider_status)

    # Сохранить обновлённое состояние
    save_json(PROVIDER_STATUS_FILE, provider_status)
    save_json(ROUTING_FILE, routing)

    print(f"ROUTE DECISION: backend={backend}, reason={reason}")
    return backend, reason


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="curator")
    parser.add_argument("--error", default=None, help="Error text from failed run")
    parser.add_argument("--success", action="store_true")
    args = parser.parse_args()

    backend, reason = route(
        role=args.role,
        error_text=args.error,
        success=args.success
    )
    print(f"\nFINAL: use backend={backend}")
    if backend is None:
        print("DEGRADED MODE: no available backend")
        sys.exit(2)
