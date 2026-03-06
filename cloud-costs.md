# Cloud Costs в OpenCost

**Cloud Costs** — функция OpenCost (начиная с версии 1.108.0), которая подтягивает **фактические данные о расходах** из billing/pricing API облачного провайдера. В отличие от расчёта по list price (on-demand), Cloud Costs использует отчёты о потреблении и стоимости из самого облака.

## Зачем это нужно

- **Точность**: учёт скидок, резервных экземпляров, spot, negotiated rates.
- **Сверка**: сравнение расчёта OpenCost по тарифам с реальными счетами.
- **Несколько облаков**: можно подключить несколько аккаунтов и провайдеров (AWS, Azure, GCP, OCI) независимо от того, где запущен OpenCost (в т.ч. on-prem).

## Поддерживаемые провайдеры

В документации описаны:

- Amazon Web Services (AWS)
- Microsoft Azure
- Google Cloud Platform (GCP)
- Oracle Cloud Infrastructure (OCI)
- Open Telekom Cloud (OTC)
- Scaleway, Alibaba — документация помечена как нуждающаяся в доработке

**Yandex Cloud** в списке официально не фигурирует; для него потребуется либо кастомная интеграция, либо использование только [Custom Pricing](https://www.opencost.io/docs/configuration/#custom-pricing) и расчёта по метрикам без Cloud Costs.

## Настройка

### 1. Файл `cloud-integration.json`

Формат — один JSON-объект с ключами по провайдерам (только те, что нужны):

```json
{
  "aws": {},
  "azure": {},
  "gcp": {},
  "oci": {}
}
```

Содержимое каждого блока задаётся в документации по провайдеру:

- [AWS Cloud Costs](https://www.opencost.io/docs/configuration/aws#aws-cloud-costs)
- [Azure Cloud Costs](https://www.opencost.io/docs/configuration/azure#azure-cloud-costs)
- [GCP Cloud Costs](https://www.opencost.io/docs/configuration/gcp#gcp-cloud-costs)
- [OCI Cloud Costs](https://www.opencost.io/docs/configuration/oracle#oci-cloud-costs)

Обычно туда входят: идентификаторы аккаунта/проекта, пути к отчётам (Cost and Usage Report, Export и т.п.), при необходимости — ключи/секреты для доступа к хранилищу отчётов.

### 2. Секрет в Kubernetes

Файл загружается в секрет в namespace `opencost`:

```bash
kubectl create secret generic cloud-costs \
  --from-file=./cloud-integration.json \
  --namespace opencost
```

Имя секрета можно выбрать другое — его нужно указать в Helm values.

### 3. Включение в Helm

В `values` для чарта OpenCost:

```yaml
opencost:
  cloudIntegrationSecret: cloud-costs   # имя секрета с cloud-integration.json
  cloudCost:
    enabled: true
```

После `helm upgrade` OpenCost начнёт использовать секрет и опрашивать billing-данные провайдера.

## API

Данные Cloud Costs доступны через [Cloud Costs API](https://www.opencost.io/docs/integrations/api/#cloud-costs-api):

- **GET `/cloudCost`** — расходы по облаку за период. Параметры: `window`, `aggregate` (например `provider`, `service`, `accountID`, `category`), `accumulate` (all/hour/day/week/month/quarter), `filter`.

## Важные ограничения

1. **Задержка данных**  
   Стоимость появляется по мере появления данных в billing провайдера — обычно задержка **несколько часов до суток**. Real-time от Cloud Costs нет.

2. **Нет сверки с on-demand**  
   OpenCost не делает автоматическую реконсиляцию: сравнение «расчёт по list price» и «факт из Cloud Costs» нужно строить самим (дашборды, отчёты).

3. **Только перечисленные CSP**  
   Для провайдеров без готовой интеграции (в т.ч. Yandex Cloud) Cloud Costs в текущем виде недоступен; остаётся Custom Pricing и при необходимости свой экспорт/агрегация счетов снаружи OpenCost.

## TODO

- [ ] Исследовать возможность использования [API получения списаний Yandex Cloud](https://yandex.cloud/ru/docs/billing/operations/get-charges-via-api) для интеграции фактических расходов (Cloud Costs или кастомный экспорт).

## Ссылки

- [Cloud Service Provider Configuration — Cloud Costs](https://www.opencost.io/docs/configuration/#cloud-costs)
- [API — Cloud Costs API](https://www.opencost.io/docs/integrations/api/#cloud-costs-api)
