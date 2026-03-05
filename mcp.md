# Подключение MCP OpenCost

В OpenCost встроен MCP-сервер (Model Context Protocol). Он предоставляет инструменты для запроса данных о стоимости кластера: AI-ассистенты (например, Cursor) могут через MCP получать cost-метрики и отвечать на вопросы о расходах.

## Возможности MCP

Через MCP доступны четыре инструмента:

| Инструмент | Назначение |
|------------|------------|
| **get_allocation_costs** | Стоимость по аллокациям (namespace, deployment, pod, container и др.). Агрегация, фильтры, учёт idle/LB, накопление по времени. |
| **get_asset_costs** | Стоимость по активам (ноды, диски и т.п.) за заданное окно времени. |
| **get_cloud_costs** | Облачные расходы: по провайдеру, региону, сервису, аккаунту, категории. Агрегация и фильтрация. |
| **get_efficiency** | Эффективность ресурсов: CPU/память (usage/request), рекомендации по rightsizing и оценка потенциальной экономии. |

Общие параметры: `window` (временное окно), `aggregate` (по чему группировать), `filter` (фильтр по меткам). Для аллокаций можно включать idle, share load balancer, настраивать шаг и разрешение.

## Настройка

MCP доступен по отдельному поддомену. Добавьте сервер в настройки MCP:

```json
{
  "mcpServers": {
    "opencost": {
      "type": "http",
      "url": "http://mcp-opencost.apatsev.org.ru"
    }
  }
}
```

Документация: [OpenCost MCP](https://opencost.io/docs/integrations/mcp/).

## Пример: стоимость по командам

Запрос стоимости по лейблу `team` через MCP:

```
get_allocation_costs(window="7d", aggregate="label:team", accumulate=true)
```
