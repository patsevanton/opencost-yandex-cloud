# Получение детализации расходов по API Yandex Cloud

Документация и проверка доступа к детализации расходов (списаний) через Billing API Yandex Cloud.

**Официальная документация:** [Получение детализации через API](https://yandex.cloud/ru/docs/billing/operations/get-charges-via-api).

## 1. Обзор

Yandex Cloud предоставляет:

- **Billing API** — REST API для работы с биллингом: счета, бюджеты, привязки объектов.
- **Экспорт детализации** — выгрузка списаний в CSV (разовая или по расписанию в Object Storage).
- **Yandex Query** — анализ уже выгруженных данных в бакете через YQL и HTTP API.

Прямой REST-метод «список списаний за период» в публичной документации описан в рамках операции «Получение детализации через API» (настройка экспорта и/или доступ к данным). Ниже — как проверить доступ к API и к каким endpoint’ам обращаться.


## 2. Аутентификация

Все запросы к Billing API выполняются с **IAM-токеном** в заголовке:

```http
Authorization: Bearer <IAM_TOKEN>
```

### 2.1. Получение IAM-токена

IAM-токен нужен для любого запроса к Billing API (и к другим API Yandex Cloud). Его можно получить несколькими способами.

**Вариант 1: Команда `yc iam create-token` (самый простой способ)**

Да, IAM-токен можно получить командой:

```bash
yc iam create-token
```

Команда выводит в stdout готовый IAM-токен. Условия:

- Установлен [YC CLI](https://yandex.cloud/ru/docs/cli/) (`yc`).
- Выполнен вход в аккаунт: `yc init` (указан OAuth-токен или другой способ аутентификации).

Пример использования в скрипте:

```bash
export IAM_TOKEN=$(yc iam create-token)
```

**Важно:** токен, выданный `yc iam create-token`, живёт около 12 часов. Для долгоживущих скриптов и CI/CD предпочтительнее сервисный аккаунт и JWT (вариант 3).

**Вариант 2: OAuth-токен (пользовательский аккаунт)**

1. Получить OAuth-токен в [OAuth-сервисе Yandex](https://oauth.yandex.ru/).
2. Обменять его на IAM-токен:

```bash
curl -s -X POST "https://iam.api.cloud.yandex.net/iam/v1/tokens" \
  -H "Content-Type: application/json" \
  -d '{"yandexPassportOauthToken": "<OAuth-токен>"}'
```

В ответе — JSON с полями `iamToken` и `expiresAt`. Значение `iamToken` подставлять в `Authorization: Bearer ...`.

**Вариант 3: JWT сервисного аккаунта (для автоматизации и CI/CD)**

1. Создать сервисный аккаунт и ключ для JWT в консоли или через API.
2. Сформировать JWT и отправить запрос:

```bash
# IAM_TOKEN создаётся запросом с JWT (см. документацию IAM Token Create)
curl -s -X POST "https://iam.api.cloud.yandex.net/iam/v1/tokens" \
  -H "Content-Type: application/json" \
  -d '{"jwt": "<JWT>"}'
```

Ответ содержит `iamToken` и `expiresAt`. Подробности: [IAM Token Create](https://yandex.cloud/en/docs/iam/api-ref/IamToken/create).


## 3. Billing API: базовый URL и роли

- **Base URL:** `https://billing.api.cloud.yandex.net/billing/v1`
- **Роли для доступа к биллингу:**  
  `billing.accounts.owner`, `billing.accounts.admin` или `billing.accounts.editor` (см. [документацию](https://yandex.cloud/ru/docs/billing/operations/get-charges-via-api)).


## 4. Проверка через curl

### 4.1. Список биллинг-аккаунтов (BillingAccount.List)

Проверяет, что токен и права доступа к Billing API работают:

```bash
export IAM_TOKEN="<подставьте_ваш_IAM_токен>"

curl -s -X GET "https://billing.api.cloud.yandex.net/billing/v1/billingAccounts" \
  -H "Authorization: Bearer $IAM_TOKEN" \
  -H "Content-Type: application/json"
```

**Ожидаемый ответ при успехе:** JSON со списком `billingAccounts` (id, name, balance, currency и т.д.) и при пагинации — `nextPageToken`.

**Типичные ошибки:**

- `401 Unauthorized` — неверный или просроченный IAM-токен.
- `403 Forbidden` — нет прав на биллинг (нужны роли выше).

**Результат проверки endpoint (без валидного токена):**

```bash
$ curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "https://billing.api.cloud.yandex.net/billing/v1/billingAccounts" \
  -H "Authorization: Bearer invalid_token" -H "Content-Type: application/json"
```
→ HTTP 401, тело в формате JSON (code 16 — UNAUTHENTICATED). Endpoint доступен; для успешного ответа нужен валидный IAM-токен.

### 4.2. Пагинация

```bash
curl -s -X GET "https://billing.api.cloud.yandex.net/billing/v1/billingAccounts?pageSize=10&pageToken=<nextPageToken>" \
  -H "Authorization: Bearer $IAM_TOKEN" \
  -H "Content-Type: application/json"
```

### 4.3. Другие методы Billing API

В [справочнике Billing API](https://yandex.cloud/ru/docs/billing/api-ref/) описаны, в том числе:

- **BillingAccount.Get** — данные по одному счёту.
- **Budget.List** — бюджеты.
- **ListBillableObjectBindings** — привязки биллингуемых объектов.

Детализация расходов (списания за период) в публичной документации чаще всего связана с **экспортом в CSV** (разовым или в Object Storage), а не с отдельным REST-методом «список списаний». После настройки экспорта данные можно забирать из бакета или анализировать через Yandex Query.


## 5. Экспорт детализации (CSV)

Источник: [Экспортировать расширенную детализацию](https://yandex.cloud/ru/docs/billing/operations/get-folder-report).

- **Разовый экспорт:** в консоли биллинга выбранный период выгружается в CSV (общая или поресурсная детализация).
- **Регулярный экспорт:** в настройках биллинга задаётся бакет Object Storage; туда по расписанию выгружаются CSV (ежедневно, обновление раз в час).

Требования к бакету: без политик доступа, без шифрования, без публичного доступа.

Для программного доступа к детализации:

1. Настроить экспорт в бакет.
2. Читать CSV из бакета по S3-совместимому API или через Yandex Query.


## 6. Yandex Query (анализ выгруженных данных)

Если детализация уже выгружается в бакет, можно использовать [Yandex Query](https://yandex.cloud/ru-kz/docs/billing/operations/query-integration): готовые запросы (топ ресурсов, расход по сервисам и т.д.) и свой YQL. Результаты доступны через HTTP API Query — удобно для интеграций и дашбордов.


## 7. Чек-лист проверки

| Шаг | Действие | Команда/ссылка |
|--|-|-|
| 1 | Получить IAM-токен | `yc iam create-token` или POST на `iam.api.cloud.yandex.net/iam/v1/tokens` |
| 2 | Проверить доступ к Billing API | `curl ... billing.api.cloud.yandex.net/billing/v1/billingAccounts` с заголовком `Authorization: Bearer $IAM_TOKEN` |
| 3 | Убедиться в правах на биллинг | Роли `billing.accounts.owner` / `admin` / `editor` |
| 4 | Настроить детализацию (если нужно) | Консоль биллинга → экспорт в CSV / в бакет; при необходимости — Yandex Query |

## 8. Связь с OpenCost

В этом репозитории использование Billing API и детализации Yandex Cloud рассматривается для:

- проверки фактических расходов (сверка с расчётом OpenCost по тарифам);
- возможной будущей интеграции «Cloud Costs» или кастомного экспорта в OpenCost (Yandex Cloud пока не в списке официально поддерживаемых провайдеров Cloud Costs).

См. [cloud-costs.md](cloud-costs.md) и [README.md](README.md).

## Ссылки

- [Получение детализации через API](https://yandex.cloud/ru/docs/billing/operations/get-charges-via-api)
- [Billing API, BillingAccount.List](https://yandex.cloud/en/docs/billing/api-ref/BillingAccount/list)
- [Экспортировать расширенную детализацию (get-folder-report)](https://yandex.cloud/ru/docs/billing/operations/get-folder-report)
- [Yandex Query — запросы к данным детализации](https://yandex.cloud/ru-kz/docs/billing/operations/query-integration)
- [IAM Token Create](https://yandex.cloud/en/docs/iam/api-ref/IamToken/create)
