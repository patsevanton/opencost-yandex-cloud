resource "yandex_iam_service_account" "sa-s3" {
  name = "sa-test-apatsev"
}

resource "yandex_resourcemanager_folder_iam_member" "sa-admin-s3" {
  folder_id = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  role      = "storage.admin"
  member    = "serviceAccount:${yandex_iam_service_account.sa-s3.id}"
}
