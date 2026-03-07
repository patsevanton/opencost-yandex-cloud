# Поды в __unallocated__ (agg=label:team, window=7d, idle=off)

Поды без лейбла `team` — при агрегации по `label:team` попадают в __unallocated__.

**Рекомендация:** добавить лейбл `team` для всех подов вне namespace `kube-system`. Тогда в __unallocated__ не будут попадать поды vmks (grafana, vmalert, vmalertmanager, node-exporter, operator, kube-state-metrics), ingress-nginx и прочие не‑kube-system workload'ы — в unallocated останутся только системные поды kube-system.

## Где проверять label `team` на подах

| Источник | Файл | Лейбл на подах |
|----------|------|-----------------|
| OpenCost | `opencost-values.yaml` → `podLabels.team` | `team: finops` |
| VMKS vmsingle, vmagent | `vmks-values.yaml` → `*.spec.podMetadata.labels` | `team: metrics` |
| VMKS vmalert | `vmks-values.yaml` → `vmalert.spec.podMetadata.labels` | `team: metrics` |
| VMKS alertmanager, grafana, node-exporter, kube-state-metrics, operator | `vmks-values.yaml` → см. ниже | `team: metrics` |
| ingress-nginx | — | в репозитории не задан; добавить при установке/апгрейде (напр. `controller.podLabels.team: platform`) |
| kube-system | — | не добавляем; системные поды остаются в unallocated по замыслу |

### Проверка в кластере (kubectl, без namespace ingress-nginx и kube-system)

Поды **с** лейблом `team`:
| Namespace | Pod | team |
|-----------|-----|------|
| opencost | opencost-* | finops |
| vmks | vmagent-vmks-* | metrics |
| vmks | vmalert-vmks-* | metrics |
| vmks | vmsingle-vmks-* | metrics |

Поды **без** лейбла `team` (попадают в unallocated):
| Namespace | Pod |
|-----------|-----|
| vmks | vmalertmanager-vmks-* |
| vmks | vmks-grafana-* |
| vmks | vmks-kube-state-metrics-* |
| vmks | vmks-prometheus-node-exporter-* |
| vmks | vmks-victoria-metrics-operator-* |

**Ключи в vmks-values.yaml для лейбла team:** vmsingle/vmagent/vmalert — `spec.podMetadata.labels`; alertmanager — `alertmanager.spec.podMetadata.labels`; grafana — `grafana.podLabels`; node-exporter — `prometheus-node-exporter.podLabels`; kube-state-metrics — `kube-state-metrics.podLabels`; operator — `victoria-metrics-operator.podLabels`. После правки выполнить `helm upgrade vmks ... --values vmks-values.yaml`.

---

| Namespace     | Pod | CPU cost (USD) | RAM cost (USD) | PV cost (USD) | Total (USD) |
|---------------|-----|----------------|----------------|---------------|-------------|
| vmks          | vmks-unmounted-pvcs | 0 | 0 | 0.7813 | **0.7813** |
| kube-system   | coredns-768847b69f-8w77g | 0.1178 | 0.0384 | 0 | 0.1562 |
| kube-system   | coredns-768847b69f-2xrvr | 0.1178 | 0.0384 | 0 | 0.1562 |
| kube-system   | metrics-server-8689cb9795-sb6wc | 0.1178 | 0.0384 | 0 | 0.1562 |
| kube-system   | metrics-server-8689cb9795-6rq5d | 0.1178 | 0.0384 | 0 | 0.1562 |
| kube-system   | kube-proxy-gzz2q | 0.1178 | 0.0052 | 0 | 0.1230 |
| kube-system   | kube-proxy-xlp5d | 0.1178 | 0.0052 | 0 | 0.1230 |
| kube-system   | kube-proxy-2wk8z | 0.1178 | 0.0053 | 0 | 0.1231 |
| ingress-nginx | ingress-nginx-controller-6c894bc4f6-4qt5h | 0.1178 | 0.0270 | 0 | 0.1448 |
| vmks          | vmalert-vmks-victoria-metrics-k8s-stack-7d9c755957-jw9dr | 0.0707 | 0.0674 | 0 | 0.1381 |
| kube-system   | yc-disk-csi-node-v2-nshwx | 0.0353 | 0.0288 | 0 | 0.0641 |
| kube-system   | yc-disk-csi-node-v2-hq6fv | 0.0353 | 0.0288 | 0 | 0.0641 |
| kube-system   | yc-disk-csi-node-v2-vpnvq | 0.0353 | 0.0288 | 0 | 0.0641 |
| vmks          | vmalertmanager-vmks-victoria-metrics-k8s-stack-0 | 0.0471 | 0.0243 | 0 | 0.0714 |
| kube-system   | npd-v0.8.0-vcj5h | 0.0236 | 0.0240 | 0 | 0.0475 |
| kube-system   | npd-v0.8.0-862gt | 0.0236 | 0.0240 | 0 | 0.0475 |
| kube-system   | npd-v0.8.0-7xh5d | 0.0236 | 0.0240 | 0 | 0.0475 |
| kube-system   | kube-dns-autoscaler-66b55897-cbkbp | 0.0236 | 0.0030 | 0 | 0.0266 |
| vmks          | vmks-grafana-757f9cf5f9-trdzm | 0.0051 | 0.0439 | 0 | 0.0490 |
| vmks          | vmks-grafana-767fb95589-l8w7n | 0.0051 | 0.0286 | 0 | 0.0338 |
| vmks          | vmks-victoria-metrics-operator-7df9bc9569-n8522 | 0.0049 | 0.0131 | 0 | 0.0180 |
| kube-system   | ip-masq-agent-zvhvl | 0.0118 | 0.0048 | 0 | 0.0166 |
| kube-system   | ip-masq-agent-8brg9 | 0.0118 | 0.0048 | 0 | 0.0166 |
| kube-system   | ip-masq-agent-5j668 | 0.0118 | 0.0048 | 0 | 0.0166 |
| vmks          | vmks-kube-state-metrics-699cd7ddf-zkz85 | 0.0028 | 0.0051 | 0 | 0.0079 |
| vmks          | vmks-prometheus-node-exporter-j9dwc | 0.0045 | 0.0028 | 0 | 0.0073 |
| vmks          | vmks-prometheus-node-exporter-vjdf9 | 0.0015 | 0.0027 | 0 | 0.0042 |
| vmks          | vmks-prometheus-node-exporter-2lnpr | 0.0014 | 0.0027 | 0 | 0.0041 |

**Исключены из таблицы** (имеют лейбл `team` в кластере, в __unallocated__ не входят):
- `opencost/*` → `team: finops`
- `vmsingle-vmks-*`, `vmagent-vmks-*`, `vmalert-vmks-*` → `team: metrics`

После применения исправленного `vmks-values.yaml` (правильные ключи и podLabels для подчартов) все перечисленные vmks-поды должны получить лейбл `team: metrics`. Проверка: `kubectl get pod -n vmks -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.team}{"\n"}{end}'`.

Данные: OpenCost allocation API, 7d, accumulate=true, include_idle=false.
