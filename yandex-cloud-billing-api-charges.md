# Биллинг Yandex Cloud и интеграция с OpenCost

## Cloud Costs и External Costs в OpenCost

OpenCost помимо расчёта стоимости Kubernetes (Allocation API) предоставляет два дополнительных механизма:

| Механизм | Появился | Что учитывает |
|----------|----------|---------------|
| **Cloud Costs** | 1.108.0 | Фактические расходы из billing API облачного провайдера (AWS, GCP, Azure). Показывает реальные списания, а не расчёт по list price. |
| **External Costs** | 1.110.0 | Затраты на сторонние сервисы вне облака: мониторинг (Datadog), SaaS (MongoDB Atlas), AI/API (OpenAI) и т.п. |

**Yandex Cloud** не входит в список поддерживаемых провайдеров Cloud Costs. External Costs не подходит, так как нас интересуют расходы на само облако, а не на сторонние сервисы.

## Yandex Cloud Billing API: почему не поможет с детализацией

Billing API v1 (gRPC/REST) содержит три сервиса:

| Сервис | Что даёт |
|--------|----------|
| `BillingAccountService` | Список аккаунтов, баланс, привязки |
| `SkuService` | Каталог SKU и тарифы (list price) |
| `ServiceService` | Справочник сервисов |

**Ни один из них не предоставляет фактического потребления или списаний.** Нельзя запросить «сколько потрачено за период X на сервис Y» — API отдаёт только баланс, тарифы и список сервисов. Детализация расходов доступна только через экспорт в CSV.

## Доступные способы получения фактических расходов Yandex Cloud

### CSV-экспорт в Object Storage

Источник: [Экспортировать расширенную детализацию](https://yandex.cloud/ru/docs/billing/operations/get-folder-report).

- **Разовый экспорт** — в консоли биллинга выгрузка за выбранный период в CSV.
- **Регулярный экспорт** — в настройках биллинга задаётся бакет Object Storage, куда ежедневно выгружаются CSV (обновление раз в час). Поресурсная детализация включает `resource_id`, `sku_id`, идентификаторы каталогов, лейблы.

Для программного доступа: настроить экспорт в бакет и читать CSV через S3-совместимый API.

### Yandex Query

Если детализация уже выгружается в бакет, можно анализировать данные через [Yandex Query](https://yandex.cloud/ru-kz/docs/billing/operations/query-integration): готовые запросы (топ ресурсов, расход по сервисам) и произвольный YQL. Результаты доступны через HTTP API.

## Возможные пути интеграции с OpenCost

| Путь | Тип в OpenCost | Описание |
|------|----------------|----------|
| Кастомный Cloud Costs провайдер | Cloud Costs (`/cloudCost`) | Go-код в ядро OpenCost, читающий CSV из Object Storage (S3-совместимый API). Аналог интеграций AWS (CUR из S3) и Azure (Cost Exports). Требует модификации ядра. |
| OpenCost Plugin | External Costs (`/customCost/*`) | Плагин, читающий CSV из Object Storage или вызывающий Yandex Query HTTP API. Не требует модификации ядра OpenCost. Репозиторий: [opencost-plugins](https://github.com/opencost/opencost-plugins). |

**Итог:** прямого API для получения списаний у Yandex Cloud нет — фактические расходы доступны только через CSV-экспорт в Object Storage. Наиболее реалистичный путь интеграции — **OpenCost Plugin**, читающий CSV-детализацию из Object Storage через S3-совместимый API.
