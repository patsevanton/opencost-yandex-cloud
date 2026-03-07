# Cloud Costs и External Costs в OpenCost

OpenCost предоставляет два механизма учёта затрат помимо стандартного расчёта стоимости Kubernetes (Allocation API):

- **Cloud Costs** — фактические данные из billing/pricing API облачного провайдера.
- **External Costs** — затраты на сторонние сервисы (мониторинг, SaaS, AI/API), подтягиваемые через плагины.

Оба дополняют Allocation API и дают единое место для мониторинга всех затрат.


## Cloud Costs

**Cloud Costs** (начиная с версии 1.108.0) подтягивает фактические данные о расходах из billing-отчётов облачного провайдера. В отличие от расчёта по list price (on-demand), Cloud Costs использует отчёты о потреблении и стоимости из самого облака.

**Yandex Cloud** в списке официально не фигурирует; для него потребуется либо кастомная интеграция, либо использование только [Custom Pricing](https://www.opencost.io/docs/configuration/#custom-pricing) и расчёта по метрикам без Cloud Costs. Подробности настройки для AWS, Azure, GCP, OCI — в [официальной документации](https://www.opencost.io/docs/configuration/#cloud-costs).


## External Costs

**External Costs** (с 1.110.0) — учёт затрат на сторонние сервисы вне Kubernetes и облачного биллинга: мониторинг (Datadog), SaaS (MongoDB Atlas), AI/API (OpenAI) и т.п. Данные подтягиваются через **плагины** (init-контейнер чарта скачивает выбранные плагины), приводятся к единому формату и отдаются через API `/customCost/total` и `/customCost/timeseries`. Документация и список плагинов: [opencost.io/docs/integrations/plugins](https://www.opencost.io/docs/integrations/plugins), [opencost-plugins](https://github.com/opencost/opencost-plugins).

**Yandex Cloud:** использовать External Costs **можно** — это не привязано к облачному провайдеру. Если у вас OpenCost крутится в Yandex Cloud (или где угодно), вы включаете нужные плагины (Datadog, OpenAI, MongoDB и т.д.) и получаете их расходы в одном месте с allocation/cloud. Готового плагина для подтягивания **самого биллинга Yandex Cloud** в External Costs нет — для фактических расходов Яндекса нужен свой плагин (например, читающий CSV из Object Storage), см. раздел «Yandex Cloud: анализ возможности интеграции» ниже.


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

В таблице выше различаются **Cloud Costs** (API `/cloudCost`) и **External Costs** (API `/customCost/*`). Ниже — какой путь к какому типу относится:

1. **Кастомный Cloud Costs провайдер** — это путь в **Cloud Costs**: Go-код в ядро OpenCost, читающий CSV из Object Storage (S3-совместимый API). Данные шли бы в `/cloudCost`. Аналогично тому, как AWS использует CUR из S3, а Azure — Cost Exports.

2. **OpenCost Plugin** (с версии 1.110.0) — это путь в **External Costs**: плагин, читающий CSV из Object Storage или вызывающий Yandex Query HTTP API. Данные попадают в `customCost/total` и `customCost/timeseries`. Не требует модификации ядра OpenCost.

3. **Внешний агрегатор** — не Cloud и не External Costs: CronJob забирает CSV из Object Storage, агрегирует и экспортирует данные как метрики в Prometheus/VictoriaMetrics для визуализации в Grafana отдельно от OpenCost.

### Вывод

Прямого API для получения списаний у Yandex Cloud нет — фактические расходы доступны только через CSV-экспорт в Object Storage и Yandex Query. Для интеграции с OpenCost наиболее реалистичен **OpenCost Plugin**, читающий CSV-детализацию из Object Storage через S3-совместимый API.

Возможно, в будущем найдутся люди, которые напишут полноценную интеграцию Yandex Cloud с OpenCost — как кастомный Cloud Costs провайдер или плагин. Это открытый проект, и вклад от сообщества приветствуется через [opencost-plugins](https://github.com/opencost/opencost-plugins).

