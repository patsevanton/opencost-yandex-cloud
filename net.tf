resource "yandex_vpc_network" "opencost" {
  name      = "vpc"
  folder_id = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
}

resource "yandex_vpc_subnet" "opencost-a" {
  folder_id      = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  v4_cidr_blocks = ["10.0.1.0/24"]
  zone           = "ru-central1-a"
  network_id     = yandex_vpc_network.opencost.id
}

resource "yandex_vpc_subnet" "opencost-b" {
  folder_id      = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  v4_cidr_blocks = ["10.0.2.0/24"]
  zone           = "ru-central1-b"
  network_id     = yandex_vpc_network.opencost.id
}

resource "yandex_vpc_subnet" "opencost-d" {
  folder_id      = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  v4_cidr_blocks = ["10.0.3.0/24"]
  zone           = "ru-central1-d"
  network_id     = yandex_vpc_network.opencost.id
}
