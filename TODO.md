# TODO

- [ ] **Добавить лейбл `team` для всех подов, кроме namespace kube-system**  
  Чтобы при агрегации по `label:team` в __unallocated__ не попадали vmks (grafana, vmalert, vmalertmanager, node-exporter, operator, kube-state-metrics), ingress-nginx и прочие не‑kube-system workload'ы.

- [ ] **Починить или переделать раздел «Запросите стоимость через API»** (README, секция с curl-примером).

- [ ] **Разобраться с [Cloud Costs](https://www.opencost.io/docs/configuration/#cloud-costs)** — настройка доступа к billing/pricing API облака, `cloud-integration.json`, секрет, включение в Helm.

- [ ] **Разобраться с External Costs** — что это в OpenCost, как настраивать и учитывать.
