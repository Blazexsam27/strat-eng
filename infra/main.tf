terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  credentials = file(var.credentials_file)
  project     = var.project_id
  region      = var.region
}

# VPC Network
resource "google_compute_network" "vpc_network" {
  name                    = "${var.environment}-openopteng-vpc"
  auto_create_subnetworks = false
}

# Subnet
resource "google_compute_subnetwork" "subnet" {
  name          = "${var.environment}-openopteng-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.vpc_network.id
}

# Firewall rule - Allow SSH
resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.environment}-allow-ssh"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["openopteng-vm"]
}

# Firewall rule - Allow HTTP/HTTPS
resource "google_compute_firewall" "allow_http" {
  name    = "${var.environment}-allow-http"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8501"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["openopteng-vm"]
}

# Cloud Storage Bucket for data
resource "google_storage_bucket" "data_bucket" {
  name          = "${var.project_id}-openopteng-data"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# Compute Engine VM
resource "google_compute_instance" "backtesting_vm" {
  name         = "${var.environment}-openopteng-vm"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["openopteng-vm"]

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
      // Ephemeral public IP
    }
  }

  metadata = {
    ssh-keys = "${var.ssh_user}:${file(var.ssh_public_key_path)}"
  }

  metadata_startup_script = file("${path.module}/scripts/startup.sh")

  service_account {
    email  = google_service_account.vm_service_account.email
    scopes = ["cloud-platform"]
  }
}

# Service Account for VM
resource "google_service_account" "vm_service_account" {
  account_id   = "${var.environment}-openopteng-vm"
  display_name = "Backtesting VM Service Account"
}

# Grant storage access to VM
resource "google_storage_bucket_iam_member" "vm_bucket_access" {
  bucket = google_storage_bucket.data_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.vm_service_account.email}"
}