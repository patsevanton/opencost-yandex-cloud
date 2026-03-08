# Биллинг Yandex Cloud и интеграция с OpenCost

Документация по работе с Billing API Yandex Cloud, получению детализации расходов и возможным путям интеграции с OpenCost.

**Официальная документация:** [Получение детализации через API](https://yandex.cloud/ru/docs/billing/operations/get-charges-via-api).


## 1. Cloud Costs и External Costs в OpenCost

OpenCost предоставляет два механизма учёта затрат помимо стандартного расчёта стоимости Kubernetes (Allocation API):

- **Cloud Costs** (с 1.108.0) — фактические данные из billing/pricing API облачного провайдера. Подтягивает отчёты о потреблении и стоимости из самого облака (в отличие от расчёта по list price).
- **External Costs** (с 1.110.0) — затраты на сторонние сервисы вне Kubernetes и облачного биллинга: мониторинг (Datadog), SaaS (MongoDB Atlas), AI/API (OpenAI) и т.п.

Оба дополняют Allocation API и дают единое место для мониторинга всех затрат.

**Yandex Cloud** в списке официально поддерживаемых провайдеров Cloud Costs не фигурирует; для него потребуется либо кастомная интеграция, либо использование только [Custom Pricing](https://www.opencost.io/docs/configuration/#custom-pricing) и расчёта по метрикам без Cloud Costs.

Нас интересуют затраты именно на само Яндекс Облако, а не на сторонние сервисы — поэтому External Costs здесь не применим.


## 2. Что предоставляет Yandex Cloud Billing API

Billing API v1 (gRPC/REST) содержит 4 сервиса:

| Сервис | Методы | Назначение |
|---|---|---|
| `BillingAccountService` | Get, List, ListBillableObjectBindings | Управление аккаунтами и привязками |
| `SkuService` | Get, List | Каталог SKU и тарифы (list price) |
| `ServiceService` | Get, List | Справочник сервисов |
| `BudgetService` | Get, List, Create | Управление бюджетами |

**Ни один из этих сервисов не предоставляет эндпоинта для получения фактического потребления или списаний** — API позволяет узнать баланс аккаунта, тарифы SKU, список сервисов и бюджеты, но нельзя запросить «сколько потрачено за период X на сервис Y».

Детализация расходов (списания за период) в публичной документации чаще всего связана с **экспортом в CSV** (разовым или в Object Storage), а не с отдельным REST-методом.

- **Base URL:** `https://billing.api.cloud.yandex.net/billing/v1`
- **Роли для доступа к биллингу:**
  `billing.accounts.owner`, `billing.accounts.admin` или `billing.accounts.editor` (см. [документацию](https://yandex.cloud/ru/docs/billing/operations/get-charges-via-api)).


## 3. Аутентификация

Все запросы к Billing API выполняются с **IAM-токеном** в заголовке:

```http
Authorization: Bearer <IAM_TOKEN>
```

IAM-токен нужен для любого запроса к Billing API (и к другим API Yandex Cloud). Самый простой способ — команда `yc iam create-token`:

```bash
export IAM_TOKEN=$(yc iam create-token)
```

Условия: установлен [YC CLI](https://yandex.cloud/ru/docs/cli/) (`yc`), выполнен вход в аккаунт (`yc init`).

**Важно:** токен живёт около 12 часов. Для долгоживущих скриптов и CI/CD предпочтительнее сервисный аккаунт и JWT.


## 4. Проверка через curl

### 4.1. Список биллинг-аккаунтов (BillingAccount.List)

Проверяет, что токен и права доступа к Billing API работают:

```bash
curl -s -X GET "https://billing.api.cloud.yandex.net/billing/v1/billingAccounts" \
  -H "Authorization: Bearer $IAM_TOKEN" \
  -H "Content-Type: application/json"
```

**Ожидаемый ответ при успехе:** JSON со списком `billingAccounts` (id, name, balance, currency и т.д.).

**Типичные ошибки:**

- `401 Unauthorized` — неверный или просроченный IAM-токен.
- `403 Forbidden` — нет прав на биллинг (нужны роли выше).

### 4.2. Другие методы Billing API

В [справочнике Billing API](https://yandex.cloud/ru/docs/billing/api-ref/) описаны, в том числе:

- **BillingAccount.Get** — данные по одному счёту.
- **Budget.List** — бюджеты.
- **ListBillableObjectBindings** — привязки биллингуемых объектов.


## 5. Доступные способы получения фактических расходов

### 5.1. CSV-экспорт детализации в Object Storage

Источник: [Экспортировать расширенную детализацию](https://yandex.cloud/ru/docs/billing/operations/get-folder-report).

- **Разовый экспорт:** в консоли биллинга выбранный период выгружается в CSV (общая или поресурсная детализация).
- **Регулярный экспорт:** в настройках биллинга задаётся бакет Object Storage; туда по расписанию выгружаются CSV (ежедневно, обновление раз в час).

Требования к бакету: без политик доступа, без шифрования, без публичного доступа. Поресурсная детализация включает `resource_id`, `sku_id`, идентификаторы каталогов, лейблы.

Для программного доступа к детализации:

1. Настроить экспорт в бакет.
2. Читать CSV из бакета по S3-совместимому API или через Yandex Query.

### 5.2. Yandex Query (анализ выгруженных данных)

Если детализация уже выгружается в бакет, можно использовать [Yandex Query](https://yandex.cloud/ru-kz/docs/billing/operations/query-integration): готовые запросы (топ ресурсов, расход по сервисам и т.д.) и свой YQL. Результаты доступны через HTTP API Query — удобно для интеграций и дашбордов.


## 6. Возможные пути интеграции с OpenCost

| Путь | Тип в OpenCost | Описание |
|---|---|---|
| Кастомный Cloud Costs провайдер | Cloud Costs (`/cloudCost`) | Go-код в ядро OpenCost, читающий CSV из Object Storage (S3-совместимый API). Аналогично тому, как AWS использует CUR из S3, а Azure — Cost Exports. |
| OpenCost Plugin (с 1.110.0) | External Costs (`/customCost/*`) | Плагин, читающий CSV из Object Storage или вызывающий Yandex Query HTTP API. Данные попадают в `customCost/total` и `customCost/timeseries`. Не требует модификации ядра OpenCost. |

Прямого API для получения списаний у Yandex Cloud нет — фактические расходы доступны только через CSV-экспорт в Object Storage и Yandex Query. Для интеграции с OpenCost наиболее реалистичен **OpenCost Plugin**, читающий CSV-детализацию из Object Storage через S3-совместимый API.

Возможно, в будущем найдутся люди, которые напишут полноценную интеграцию Yandex Cloud с OpenCost — как кастомный Cloud Costs провайдер или плагин. Это открытый проект, и вклад от сообщества приветствуется через [opencost-plugins](https://github.com/opencost/opencost-plugins).


## 7. Чек-лист проверки

| Шаг | Действие | Команда/ссылка |
|--|--|--|
| 1 | Получить IAM-токен | `yc iam create-token` или POST на `iam.api.cloud.yandex.net/iam/v1/tokens` |
| 2 | Проверить доступ к Billing API | `curl ... billing.api.cloud.yandex.net/billing/v1/billingAccounts` с заголовком `Authorization: Bearer $IAM_TOKEN` |
| 3 | Убедиться в правах на биллинг | Роли `billing.accounts.owner` / `admin` / `editor` |
| 4 | Настроить детализацию (если нужно) | Консоль биллинга → экспорт в CSV / в бакет; при необходимости — Yandex Query |

## 8. Связь с OpenCost

В этом репозитории использование Billing API и детализации Yandex Cloud рассматривается для:

- проверки фактических расходов (сверка с расчётом OpenCost по тарифам);
- возможной будущей интеграции Cloud Costs или кастомного экспорта в OpenCost (Yandex Cloud пока не в списке официально поддерживаемых провайдеров Cloud Costs).

См. [README.md](README.md).

## Ссылки

- [Получение детализации через API](https://yandex.cloud/ru/docs/billing/operations/get-charges-via-api)
- [Billing API, BillingAccount.List](https://yandex.cloud/en/docs/billing/api-ref/BillingAccount/list)
- [Экспортировать расширенную детализацию (get-folder-report)](https://yandex.cloud/ru/docs/billing/operations/get-folder-report)
- [Yandex Query — запросы к данным детализации](https://yandex.cloud/ru-kz/docs/billing/operations/query-integration)
- [IAM Token Create](https://yandex.cloud/en/docs/iam/api-ref/IamToken/create)
- [opencost-plugins](https://github.com/opencost/opencost-plugins)
