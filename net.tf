resource "yandex_vpc_network" "sentry" {
  name      = "vpc"
  folder_id = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
}

resource "yandex_vpc_subnet" "sentry-a" {
  folder_id      = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  v4_cidr_blocks = ["10.0.1.0/24"]
  zone           = "ru-central1-a"
  network_id     = yandex_vpc_network.sentry.id
}

resource "yandex_vpc_subnet" "sentry-b" {
  folder_id      = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  v4_cidr_blocks = ["10.0.2.0/24"]
  zone           = "ru-central1-b"
  network_id     = yandex_vpc_network.sentry.id
}

resource "yandex_vpc_subnet" "sentry-d" {
  folder_id      = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  v4_cidr_blocks = ["10.0.3.0/24"]
  zone           = "ru-central1-d"
  network_id     = yandex_vpc_network.sentry.id
}
