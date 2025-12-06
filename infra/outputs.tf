output "vm_external_ip" {
  description = "External IP of the VM"
  value       = google_compute_instance.backtesting_vm.network_interface[0].access_config[0].nat_ip
}

output "vm_name" {
  description = "Name of the VM"
  value       = google_compute_instance.backtesting_vm.name
}

output "bucket_name" {
  description = "Name of the storage bucket"
  value       = google_storage_bucket.data_bucket.name
}

output "ssh_command" {
  description = "SSH command to connect to VM"
  value       = "gcloud compute ssh ${google_compute_instance.backtesting_vm.name} --zone=${var.zone}"
}