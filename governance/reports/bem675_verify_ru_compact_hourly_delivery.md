# BEM-675 | Verify RU Compact Hourly Delivery | RU_COMPACT_HOURLY_NOT_CONFIRMED

Дата: 2026-05-18 | 19:04 (UTC+3)

## Checks

- dispatch_status_204: PASS
- queue_archived: FAIL
- active_queue_empty: PASS
- telegram_delivery_sent: PASS
- russian_text: PASS
- english_labels_removed: PASS
- compact_width: PASS
- state_layout_ru_compact: PASS

## Blocker
{
  "code": "RU_COMPACT_HOURLY_NOT_CONFIRMED",
  "failed": [
    {
      "name": "queue_archived",
      "pass": false,
      "evidence": "governance/workflow_dispatch_processed/"
    }
  ],
  "status_file": "204\n",
  "active_queue": [],
  "processed": [],
  "hourly_state": {
    "schema_version": "curator_hourly_report_state.v3_ru_compact",
    "status": "sent",
    "report_hour": "2026-05-18 | 19:00 (UTC+3)",
    "stage_done": 6,
    "stage_total": 6,
    "stage_percent": 100,
    "roadmap_done": 6,
    "roadmap_total": 6,
    "roadmap_percent": 100,
    "telegram_delivery": "sent",
    "language": "ru",
    "layout": "compact_table",
    "rows": [
      {
        "number": 1,
        "name": "Канал",
        "essence": "восстановлен",
        "status": "✅"
      },
      {
        "number": 2,
        "name": "Роли",
        "essence": "проверены",
        "status": "✅"
      },
      {
        "number": 3,
        "name": "Провайдер",
        "essence": "маршрут ясен",
        "status": "✅"
      },
      {
        "number": 4,
        "name": "ТГ-тест",
        "essence": "отправка есть",
        "status": "✅"
      },
      {
        "number": 5,
        "name": "Часовой",
        "essence": "доставка есть",
        "status": "✅"
      },
      {
        "number": 6,
        "name": "Готовность",
        "essence": "принята",
        "status": "✅"
      }
    ],
    "blocker": null
  },
  "runtime_preview": "# Curator Hourly Report Runtime\n\nBEM-HOURLY | ЧАСОВОЙ ОТЧЁТ\nДата: 2026-05-18 | 19:00 (UTC+3)\n\nЭтап: 6/6 (100%)\nДорожная карта: 6/6 (100%)\n\n```\n№ | Наименование | Краткая суть     | Ст\n--+--------------+------------------+---\n1 | Канал        | восстановлен     | ✅\n2 | Роли         | проверены        | ✅\n3 | Провайдер    | маршрут ясен     | ✅\n4 | ТГ-тест      | отправка есть    | ✅\n5 | Часовой      | доставка есть    | ✅\n6 | Готовность   | принята          | ✅\n```\n",
  "delivery_report": "# Curator Hourly Delivery\n\nTelegram delivery: sent\n"
}
