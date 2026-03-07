# TODO

- [ ] **Добавить лейбл `team` для всех подов, кроме namespace kube-system**  
  Чтобы при агрегации по `label:team` в __unallocated__ не попадали vmks (grafana, vmalert, vmalertmanager, node-exporter, operator, kube-state-metrics), ingress-nginx и прочие не‑kube-system workload'ы.
