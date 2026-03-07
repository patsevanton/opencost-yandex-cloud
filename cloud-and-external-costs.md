# Cloud Costs и External Costs в OpenCost

OpenCost предоставляет два механизма учёта затрат помимо стандартного расчёта стоимости Kubernetes (Allocation API):

- **Cloud Costs** — фактические данные из billing/pricing API облачного провайдера.
- **External Costs** — затраты на сторонние сервисы (мониторинг, SaaS, AI/API), подтягиваемые через плагины.

Оба дополняют Allocation API и дают единое место для мониторинга всех затрат.


## Cloud Costs

**Cloud Costs** (начиная с версии 1.108.0) подтягивает фактические данные о расходах из billing-отчётов облачного провайдера. В отличие от расчёта по list price (on-demand), Cloud Costs использует отчёты о потреблении и стоимости из самого облака.

### Зачем это нужно

- **Точность**: учёт скидок, резервных экземпляров, spot, negotiated rates.
- **Сверка**: сравнение расчёта OpenCost по тарифам с реальными счетами.
- **Несколько облаков**: можно подключить несколько аккаунтов и провайдеров (AWS, Azure, GCP, OCI) независимо от того, где запущен OpenCost (в т.ч. on-prem).

**Yandex Cloud** в списке официально не фигурирует; для него потребуется либо кастомная интеграция, либо использование только [Custom Pricing](https://www.opencost.io/docs/configuration/#custom-pricing) и расчёта по метрикам без Cloud Costs. Подробности настройки для AWS, Azure, GCP, OCI — в [официальной документации](https://www.opencost.io/docs/configuration/#cloud-costs).


## External Costs

**External Costs** (внешние расходы, начиная с версии 1.110.0) — учёт затрат вне Kubernetes и стандартных облачных billing-отчётов: мониторинг (Datadog), SaaS (MongoDB Atlas), AI/API (OpenAI) и т.п. Данные подтягиваются через **плагины** и отдаются единым API.

### Зачем это нужно

- **Единая картина**: Kubernetes, облако и сторонние сервисы в одном месте.
- **FinOps**: один инструмент для отчётов по инфраструктуре, данным и внешним подпискам.
- **Агрегация и фильтрация**: те же окна, агрегации и фильтры, что и для allocation/cloud costs.

### Плагины

Поддержка External Costs реализована через архитектуру плагинов:

- Плагины **не вшиты** в образ OpenCost: их скачивает init-контейнер чарта и кладёт в общий для пода volume.
- В основном контейнере OpenCost подгружает и запускает только включённые плагины — размер образа не раздувается.
- Данные от плагинов приводятся к единому формату (в духе [FOCUS](https://www.finops.org/focus/)) и отдаются через **External Costs API**.

Готовые плагины:

- [Datadog](https://www.opencost.io/docs/integrations/plugins/datadog)
- [OpenAI](https://www.opencost.io/docs/integrations/plugins/openai)
- [MongoDB Atlas](https://www.opencost.io/docs/integrations/plugins/mongo)

Новые плагины разрабатываются в репозитории [opencost/opencost-plugins](https://github.com/opencost/opencost-plugins).

### Настройка External Costs

1. **Версия OpenCost** — не ниже **1.110.0**.
2. **Включение плагинов в Helm** — в values для чарта OpenCost указываются нужные плагины (имена и при необходимости конфигурация/секреты). Точный формат смотрите в [документации по плагинам](https://www.opencost.io/docs/integrations/plugins/) и в гайдах по каждому плагину.
3. **Учёт в отчётах и дашбордах** — после включения плагинов данные появляются в `/customCost/total` и `/customCost/timeseries`. Их можно смотреть в UI OpenCost, скрейпить из скриптов/Grafana, объединять с allocation и cloud costs в своих отчётах.

### API External Costs

Два эндпоинта:

| Эндпоинт | Назначение |
|----------|------------|
| **`/customCost/total`** | Суммарные внешние расходы за период |
| **`/customCost/timeseries`** | Те же расходы с разбивкой по времени |

Общие параметры:

- **`window`** — период (например `7d`, `month`, RFC3339 или unix timestamps).
- **`aggregate`** — группировка: `domain`, `accountID`, `provider`, `providerID`, `category`, `service`, `invoiceEntityID` и др.
- **`accumulate`** — шаг накопления: `all`, `hour`, `day`, `week`, `month`, `quarter`.
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


## Сравнение Cloud Costs и External Costs

| | Cloud Costs | External Costs |
|---|-------------|-----------------|
| Источник | Billing/cost & usage отчёты облака (AWS, Azure, GCP, OCI и т.д.) | Сторонние сервисы через плагины (Datadog, OpenAI, MongoDB и др.) |
| Мин. версия | 1.108.0 | 1.110.0 |
| Настройка | Секрет `cloud-integration.json` + `cloudCost.enabled` | Плагины в Helm (init container скачивает выбранные плагины) |
| API | `/cloudCost` | `/customCost/total`, `/customCost/timeseries` |


## Yandex Cloud: анализ возможности интеграции фактических расходов

### Что предоставляет Yandex Cloud Billing API

Billing API v1 (gRPC/REST) содержит 4 сервиса:

| Сервис | Методы | Назначение |
|---|---|---|
| `BillingAccountService` | Get, List, ListBillableObjectBindings | Управление аккаунтами и привязками |
| `SkuService` | Get, List | Каталог SKU и тарифы (list price) |
| `ServiceService` | Get, List | Справочник сервисов |
| `BudgetService` | Get, List, Create | Управление бюджетами |

**Ни один из этих сервисов не предоставляет эндпоинта для получения фактического потребления или списаний.** API позволяет узнать баланс аккаунта, тарифы SKU, список сервисов и бюджеты, но нельзя запросить «сколько потрачено за период X на сервис Y».

### Доступные способы получения фактических расходов

1. **CSV-экспорт детализации в Object Storage** — регулярный (ежедневный) автоматический экспорт в бакет Yandex Object Storage. Поресурсная детализация включает `resource_id`, `sku_id`, идентификаторы каталогов, лейблы. Файлы обновляются каждый час.

2. **Yandex Query** — SQL-запросы к данным биллинга с готовыми шаблонами (расходы по сервисам, топ ресурсов, потребление по папкам). Результаты доступны через HTTP API.

### Возможные пути интеграции с OpenCost

1. **Кастомный Cloud Costs провайдер** — Go-код в ядро OpenCost, читающий CSV из Object Storage (S3-совместимый API). Аналогично тому, как AWS использует CUR из S3, а Azure — Cost Exports.

2. **OpenCost Plugin** (с версии 1.110.0) — плагин, читающий CSV из Object Storage или вызывающий Yandex Query HTTP API. Данные попадают в `customCost/total` API. Не требует модификации ядра OpenCost.

3. **Внешний агрегатор** — CronJob, забирающий CSV из Object Storage, агрегирующий и экспортирующий данные как метрики в Prometheus/VictoriaMetrics для визуализации в Grafana отдельно от OpenCost.

### Вывод

Прямого API для получения списаний у Yandex Cloud нет — фактические расходы доступны только через CSV-экспорт в Object Storage и Yandex Query. Для интеграции с OpenCost наиболее реалистичен **OpenCost Plugin**, читающий CSV-детализацию из Object Storage через S3-совместимый API.

Возможно, в будущем найдутся люди, которые напишут полноценную интеграцию Yandex Cloud с OpenCost — как кастомный Cloud Costs провайдер или плагин. Это открытый проект, и вклад от сообщества приветствуется через [opencost-plugins](https://github.com/opencost/opencost-plugins).


## Ссылки

### Cloud Costs
- [Cloud Service Provider Configuration — Cloud Costs](https://www.opencost.io/docs/configuration/#cloud-costs)
- [API — Cloud Costs API](https://www.opencost.io/docs/integrations/api/#cloud-costs-api)

### External Costs
- [Plugins (обзор)](https://www.opencost.io/docs/integrations/plugins/)
- [API — External Costs API](https://www.opencost.io/docs/integrations/api/#external-costs-api)
- [Introducing OpenCost Plugins (блог)](https://www.opencost.io/blog/introducing-opencost-plugins/)

### Yandex Cloud
- [Yandex Cloud Billing API (cloudapi)](https://github.com/yandex-cloud/cloudapi/tree/master/yandex/cloud/billing/v1)
- [Экспорт детализации в Object Storage](https://yandex.cloud/ru/docs/billing/operations/get-folder-report)
- [OpenCost Plugins (GitHub)](https://github.com/opencost/opencost-plugins)
