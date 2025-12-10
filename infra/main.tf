terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "google" {
  credentials = file(var.credentials_file)
  project     = var.project_id
  region      = var.region
}

# Random suffix for unique names
resource "random_id" "suffix" {
  byte_length = 3
}

# VPC Network
resource "google_compute_network" "vpc_network" {
  name                    = "${var.environment}-openopteng-vpc-${random_id.suffix.hex}"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  lifecycle {
    prevent_destroy = true
  }
}

# Subnet
resource "google_compute_subnetwork" "subnet" {
  name                     = "${var.environment}-openopteng-subnet-${random_id.suffix.hex}"
  ip_cidr_range            = "10.0.1.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc_network.id
  private_ip_google_access = true
}

# Firewall rules
resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.environment}-allow-ssh-${random_id.suffix.hex}"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0", "35.235.240.0/20"]
  target_tags   = ["openopteng-vm"]
  description   = "Allow SSH from anywhere and IAP"
}

resource "google_compute_firewall" "allow_http" {
  name    = "${var.environment}-allow-http-${random_id.suffix.hex}"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8501", "3000", "8080"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["openopteng-vm"]
  description   = "Allow web traffic and Streamlit port"
}

resource "google_compute_firewall" "allow_internal" {
  name    = "${var.environment}-allow-internal-mid-${random_id.suffix.hex}"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.1.0/24"]
  target_tags   = ["openopteng-vm"]
  description   = "Allow all internal traffic within subnet"
}

# Cloud Storage Bucket
resource "google_storage_bucket" "data_bucket" {
  name                        = "${var.project_id}-openopteng-data-${random_id.suffix.hex}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# Static IP Address
resource "google_compute_address" "static_ip" {
  name   = "${var.environment}-openopteng-vm-ip-${random_id.suffix.hex}"
  region = var.region
}

# Service Account
resource "google_service_account" "vm_service_account" {
  account_id   = "${var.environment}-openopteng-vm-sa-${random_id.suffix.hex}"
  display_name = "OpenOpt Backtesting VM Service Account"
  description  = "Service account for OpenOpt Risk Engine backtesting VM"
}

# VM Instance
resource "google_compute_instance" "backtesting_vm" {
  name         = "${var.environment}-openopteng-vm-${random_id.suffix.hex}"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["openopteng-vm"]

  labels = {
    environment = var.environment
    managed-by  = "terraform"
    purpose     = "backtesting"
  }

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 30
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id

    access_config {
      nat_ip = google_compute_address.static_ip.address
    }
  }

  metadata = {
    ssh-keys               = "${var.ssh_user}:${file(var.ssh_public_key_path)}"
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/scripts/startup.sh", {
    project_id  = var.project_id
    environment = var.environment
    region      = var.region
  })

  service_account {
    email  = google_service_account.vm_service_account.email
    scopes = ["cloud-platform"]
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    preemptible         = false
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
}

# IAM roles for Service Account
resource "google_project_iam_member" "vm_log_writer_mid" {
  project    = var.project_id
  role       = "roles/logging.logWriter"
  member     = "serviceAccount:${google_service_account.vm_service_account.email}"
  depends_on = [google_service_account.vm_service_account]
}

resource "google_project_iam_member" "vm_metric_writer_mid" {
  project    = var.project_id
  role       = "roles/monitoring.metricWriter"
  member     = "serviceAccount:${google_service_account.vm_service_account.email}"
  depends_on = [google_service_account.vm_service_account]
}

resource "google_project_iam_member" "vm_monitoring_viewer_mid" {
  project    = var.project_id
  role       = "roles/monitoring.viewer"
  member     = "serviceAccount:${google_service_account.vm_service_account.email}"
  depends_on = [google_service_account.vm_service_account]
}

resource "google_storage_bucket_iam_member" "vm_bucket_access" {
  bucket     = google_storage_bucket.data_bucket.name
  role       = "roles/storage.objectAdmin"
  member     = "serviceAccount:${google_service_account.vm_service_account.email}"
  depends_on = [google_service_account.vm_service_account]
}

resource "google_project_iam_member" "project_storage_admin_mid" {
  project    = var.project_id
  role       = "roles/storage.admin"
  member     = "serviceAccount:${google_service_account.vm_service_account.email}"
  depends_on = [google_service_account.vm_service_account]
}

# Outputs
output "vm_static_ip" {
  value       = google_compute_address.static_ip.address
  description = "Static IP address of the VM"
}

output "vm_ssh_command" {
  value       = "ssh ${var.ssh_user}@${google_compute_address.static_ip.address}"
  description = "SSH command to connect to the VM"
}

output "storage_bucket_name" {
  value       = google_storage_bucket.data_bucket.name
  description = "Name of the storage bucket"
}

output "vm_service_account_email" {
  value       = google_service_account.vm_service_account.email
  description = "Service account email for the VM"
}

output "streamlit_url" {
  value       = "http://${google_compute_address.static_ip.address}:8501"
  description = "Streamlit app URL"
}

output "vpc_network_name" {
  value       = google_compute_network.vpc_network.name
  description = "VPC network name"
}

output "subnet_name" {
  value       = google_compute_subnetwork.subnet.name
  description = "Subnet name"
}
