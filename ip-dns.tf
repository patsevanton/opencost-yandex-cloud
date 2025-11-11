resource "yandex_vpc_address" "addr" {
  name = "opencost-pip"

  external_ipv4_address {
    zone_id = yandex_vpc_subnet.opencost-a.zone
  }
}

resource "yandex_dns_zone" "apatsev-org-ru" {
  name  = "apatsev-org-ru-zone"

  zone  = "apatsev.org.ru."
  public = true

  private_networks = [yandex_vpc_network.opencost.id]
}

resource "yandex_dns_recordset" "victoriametrics" {
  zone_id = yandex_dns_zone.apatsev-org-ru.id
  name    = "victoriametrics.apatsev.org.ru."
  type    = "A"
  ttl     = 200
  data    = [yandex_vpc_address.addr.external_ipv4_address[0].address]
}

resource "yandex_dns_recordset" "opencost" {
  zone_id = yandex_dns_zone.apatsev-org-ru.id
  name    = "opencost.apatsev.org.ru."
  type    = "A"
  ttl     = 200
  data    = [yandex_vpc_address.addr.external_ipv4_address[0].address]
}
