resource "yandex_iam_service_account_static_access_key" "filestore_bucket_key" {
  service_account_id = yandex_iam_service_account.sa-s3.id
  description        = "static access key for object storage"
}

resource "yandex_storage_bucket" "filestore" {
  bucket     = local.filestore_bucket
  lifecycle_rule {
    id      = "delete-after-30-days"
    enabled = true
    expiration {
      days = 30
    }
  }
  access_key = yandex_iam_service_account_static_access_key.filestore_bucket_key.access_key
  secret_key = yandex_iam_service_account_static_access_key.filestore_bucket_key.secret_key
  folder_id = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  depends_on = [
    yandex_resourcemanager_folder_iam_member.sa-admin-s3,
  ]
}

output "access_key_for_filestore_bucket" {
  description = "access_key filestore_bucket"
  value       = yandex_storage_bucket.filestore.access_key
  sensitive   = true
}

output "secret_key_for_filestore_bucket" {
  description = "secret_key filestore_bucket"
  value       = yandex_storage_bucket.filestore.secret_key
  sensitive   = true
}
