# External Costs в OpenCost

**External Costs** (внешние расходы) в OpenCost — это учёт затрат **вне** Kubernetes и стандартных облачных billing-отчётов: мониторинг (Datadog), SaaS (MongoDB Atlas), AI/API (OpenAI) и т.п. Данные подтягиваются через **плагины** и отдаются единым API и, при поддержке, интерфейсом.

## Зачем это нужно

- **Единая картина**: Kubernetes, облако и сторонние сервисы в одном месте.
- **FinOps**: один инструмент для отчётов по инфраструктуре, данным и внешним подпискам.
- **Агрегация и фильтрация**: те же окна, агрегации и фильтры, что и для allocation/cloud costs.

## Плагины (с версии 1.110.0)

Поддержка External Costs реализована через **архитектуру плагинов**:

- Плагины **не вшиты** в образ OpenCost: их скачивает init-контейнер чарта и кладёт в общий для пода volume.
- В основном контейнере OpenCost подгружает и запускает только включённые плагины — размер образа не раздувается.
- Данные от плагинов приводятся к единому формату (в духе [FOCUS](https://www.finops.org/focus/)) и отдаются через **External Costs API**.

Готовые плагины (на момент документации):

- [Datadog](https://www.opencost.io/docs/integrations/plugins/datadog)
- [OpenAI](https://www.opencost.io/docs/integrations/plugins/openai)
- [MongoDB Atlas](https://www.opencost.io/docs/integrations/plugins/mongo)

Новые плагины разрабатываются в репозитории [opencost/opencost-plugins](https://github.com/opencost/opencost-plugins).

## API External Costs

Два эндпоинта:

| Эндпоинт | Назначение |
|----------|------------|
| **`/customCost/total`** | Суммарные внешние расходы за период (одним итогом за `window`) |
| **`/customCost/timeseries`** | Те же расходы с разбивкой по времени (по сути серия вызовов `/total` по шагам) |

Общие параметры:

- **`window`** — период (например `7d`, `month`, RFC3339 или unix timestamps).
- **`aggregate`** — группировка: `domain`, `accountID`, `provider`, `providerID`, `category`, `service`, `invoiceEntityID` и др., через запятую для нескольких осей.
- **`accumulate`** — шаг накопления: `all`, `hour`, `day`, `week`, `month`, `quarter` (по умолчанию для timeseries — `day`).
- **`filter`** — фильтрация в формате V2 (например `domain:"datadog"`, `resourceType:"infra_hosts"`, `zone:"us"`).

Примеры:

```bash
# Сумма внешних расходов за 7 дней по домену (источнику)
curl -G "http://localhost:9003/customCost/total" \
  -d "window=7d" \
  -d "aggregate=domain"

# Временной ряд по дням за последнюю неделю
curl -G "http://localhost:9003/customCost/timeseries" \
  -d "window=7d" \
  -d "aggregate=domain" \
  -d "accumulate=day"
```

Порт и хост замените на свой (например через ingress или port-forward к OpenCost).

## Как настраивать

1. **Версия OpenCost**  
   Не ниже **1.110.0** (проверьте `helm list` / образ в чарте).

2. **Включение плагинов в Helm**  
   В values для чарта OpenCost указываются нужные плагины (имена и при необходимости конфигурация/секреты). Точный формат смотрите в [документации по плагинам](https://www.opencost.io/docs/integrations/plugins/) и в гайдах по каждому плагину (Datadog, OpenAI, MongoDB Atlas).

3. **Учёт в отчётах и дашбордах**  
   После включения плагинов данные появляются в `/customCost/total` и `/customCost/timeseries`. Их можно:
   - смотреть в UI OpenCost (если в вашей версии есть экраны External/Custom Cost);
   - скрейпить или вызывать из скриптов/Grafana;
   - объединять с allocation и cloud costs в своих отчётах.

## Отличие от Cloud Costs

| | Cloud Costs | External Costs |
|---|-------------|-----------------|
| Источник | Billing/cost & usage отчёты облака (AWS, Azure, GCP, OCI и т.д.) | Сторонние сервисы через плагины (Datadog, OpenAI, MongoDB и др.) |
| Настройка | Секрет `cloud-integration.json` + `cloudCost.enabled` | Плагины в Helm (init container скачивает выбранные плагины) |
| API | `/cloudCost` | `/customCost/total`, `/customCost/timeseries` |

Оба механизма дополняют основной расчёт стоимости по Kubernetes (Allocation API) и дают единое место для мониторинга затрат.

## Ссылки

- [Plugins (обзор)](https://www.opencost.io/docs/integrations/plugins/)
- [API — External Costs API](https://www.opencost.io/docs/integrations/api/#external-costs-api)
- [Introducing OpenCost Plugins (блог)](https://www.opencost.io/blog/introducing-opencost-plugins/)
- [opencost-plugins (GitHub)](https://github.com/opencost/opencost-plugins)
