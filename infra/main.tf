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


# =====================================
# BigQuery Resources
# =====================================

# BigQuery Dataset
resource "google_bigquery_dataset" "backtesting_dataset" {
  dataset_id                  = "${var.environment}_openopteng_data"
  friendly_name               = "OpenOpt Risk Engine - Backtesting Data"
  description                 = "Storage for stock historical data and backtest results"
  location                    = var.region
  default_table_expiration_ms = null

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "backtesting"
  }

  access {
    role          = "OWNER"
    user_by_email = google_service_account.cloud_function_sa.email
  }

  access {
    role          = "OWNER"
    user_by_email = google_service_account.vm_service_account.email
  }
}

# BigQuery Table - Stock Prices
resource "google_bigquery_table" "stock_prices" {
  dataset_id = google_bigquery_dataset.backtesting_dataset.dataset_id
  table_id   = "stock_prices"

  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "date"
  }

  clustering = ["symbol"]

  schema = jsonencode([
    {
      name        = "symbol"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Stock ticker symbol"
    },
    {
      name        = "date"
      type        = "DATE"
      mode        = "REQUIRED"
      description = "Trading date"
    },
    {
      name        = "open"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "Opening price"
    },
    {
      name        = "high"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "High price"
    },
    {
      name        = "low"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "Low price"
    },
    {
      name        = "close"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "Closing price"
    },
    {
      name        = "adj_close"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "Adjusted closing price"
    },
    {
      name        = "volume"
      type        = "INTEGER"
      mode        = "NULLABLE"
      description = "Trading volume"
    },
    {
      name        = "inserted_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "When the record was inserted"
    }
  ])
}

# BigQuery Table - Backtest Results
resource "google_bigquery_table" "backtest_results" {
  dataset_id = google_bigquery_dataset.backtesting_dataset.dataset_id
  table_id   = "backtest_results"

  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "backtest_date"
  }

  clustering = ["strategy_name", "symbol"]

  schema = jsonencode([
    {
      name        = "backtest_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Unique backtest identifier"
    },
    {
      name        = "strategy_name"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Name of the strategy"
    },
    {
      name        = "symbol"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Stock symbol"
    },
    {
      name        = "backtest_date"
      type        = "DATE"
      mode        = "REQUIRED"
      description = "Date of backtest run"
    },
    {
      name        = "start_date"
      type        = "DATE"
      mode        = "REQUIRED"
      description = "Backtest period start"
    },
    {
      name        = "end_date"
      type        = "DATE"
      mode        = "REQUIRED"
      description = "Backtest period end"
    },
    {
      name        = "total_return"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "Total return percentage"
    },
    {
      name        = "sharpe_ratio"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "Sharpe ratio"
    },
    {
      name        = "max_drawdown"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "Maximum drawdown"
    },
    {
      name        = "win_rate"
      type        = "FLOAT64"
      mode        = "NULLABLE"
      description = "Win rate percentage"
    },
    {
      name        = "num_trades"
      type        = "INTEGER"
      mode        = "NULLABLE"
      description = "Number of trades"
    },
    {
      name        = "parameters"
      type        = "JSON"
      mode        = "NULLABLE"
      description = "Strategy parameters as JSON"
    },
    {
      name        = "inserted_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "When the record was inserted"
    }
  ])
}

# =====================================
# Cloud Function Resources
# =====================================

# Service Account for Cloud Functions
resource "google_service_account" "cloud_function_sa" {
  account_id   = "${var.environment}-cf-ingestion-${random_id.suffix.hex}"
  display_name = "Cloud Function Data Ingestion SA"
  description  = "Service account for data ingestion cloud function"
}

# Grant BigQuery permissions to Cloud Function SA
resource "google_project_iam_member" "cf_bigquery_data_editor" {
  project    = var.project_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.cloud_function_sa.email}"
  depends_on = [google_service_account.cloud_function_sa]
}

resource "google_project_iam_member" "cf_bigquery_job_user" {
  project    = var.project_id
  role       = "roles/bigquery.jobUser"
  member     = "serviceAccount:${google_service_account.cloud_function_sa.email}"
  depends_on = [google_service_account.cloud_function_sa]
}

# Grant BigQuery permissions to VM SA (so your app can query BigQuery)
resource "google_project_iam_member" "vm_bigquery_data_viewer" {
  project    = var.project_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.vm_service_account.email}"
  depends_on = [google_service_account.vm_service_account]
}

resource "google_project_iam_member" "vm_bigquery_job_user" {
  project    = var.project_id
  role       = "roles/bigquery.jobUser"
  member     = "serviceAccount:${google_service_account.vm_service_account.email}"
  depends_on = [google_service_account.vm_service_account]
}

# Storage bucket for Cloud Function source code
resource "google_storage_bucket" "function_source" {
  name                        = "${var.project_id}-cf-source-${random_id.suffix.hex}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

# Archive function source code
data "archive_file" "function_source" {
  type        = "zip"
  source_dir  = "${path.module}/../cloud-functions/data-ingestion"
  output_path = "${path.module}/function-source.zip"
}

# Upload function source to GCS
resource "google_storage_bucket_object" "function_source_archive" {
  name   = "data-ingestion-${data.archive_file.function_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.function_source.output_path
}

# Cloud Function (Gen 2)
resource "google_cloudfunctions2_function" "data_ingestion" {
  name        = "${var.environment}-data-ingestion-${random_id.suffix.hex}"
  location    = var.region
  description = "Daily stock data ingestion from yfinance to BigQuery"

  build_config {
    runtime     = "python311"
    entry_point = "ingest_stock_data"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_source_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    min_instance_count = 0
    available_memory   = "512M"
    timeout_seconds    = 540

    environment_variables = {
      GCP_PROJECT      = var.project_id
      BIGQUERY_DATASET = google_bigquery_dataset.backtesting_dataset.dataset_id
    }

    service_account_email = google_service_account.cloud_function_sa.email
  }

  depends_on = [
    google_storage_bucket_object.function_source_archive,
    google_project_iam_member.cf_bigquery_data_editor,
    google_project_iam_member.cf_bigquery_job_user
  ]
}

# Allow Cloud Function to be invoked
resource "google_cloud_run_service_iam_member" "function_invoker" {
  location = google_cloudfunctions2_function.data_ingestion.location
  service  = google_cloudfunctions2_function.data_ingestion.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.cloud_function_sa.email}"
}

# =====================================
# Cloud Scheduler
# =====================================

# Cloud Scheduler Job
resource "google_cloud_scheduler_job" "daily_data_ingestion" {
  name             = "${var.environment}-daily-ingestion-${random_id.suffix.hex}"
  description      = "Trigger daily stock data ingestion"
  schedule         = "0 1 * * *" # Daily at 1 AM
  time_zone        = "America/New_York"
  attempt_deadline = "540s"
  region           = "europe-west3"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.data_ingestion.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.cloud_function_sa.email
    }

    body = base64encode(jsonencode({
      symbols       = ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]
      lookback_days = 7
    }))

    headers = {
      "Content-Type" = "application/json"
    }
  }

  depends_on = [
    google_cloudfunctions2_function.data_ingestion,
    google_cloud_run_service_iam_member.function_invoker
  ]
}

# =====================================
# Additional Outputs
# =====================================

output "bigquery_dataset_id" {
  value       = google_bigquery_dataset.backtesting_dataset.dataset_id
  description = "BigQuery dataset ID"
}

output "bigquery_stock_prices_table" {
  value       = "${var.project_id}.${google_bigquery_dataset.backtesting_dataset.dataset_id}.${google_bigquery_table.stock_prices.table_id}"
  description = "Fully qualified BigQuery stock prices table"
}

output "bigquery_backtest_results_table" {
  value       = "${var.project_id}.${google_bigquery_dataset.backtesting_dataset.dataset_id}.${google_bigquery_table.backtest_results.table_id}"
  description = "Fully qualified BigQuery backtest results table"
}

output "cloud_function_uri" {
  value       = google_cloudfunctions2_function.data_ingestion.service_config[0].uri
  description = "Cloud Function HTTP trigger URI"
}

output "cloud_function_name" {
  value       = google_cloudfunctions2_function.data_ingestion.name
  description = "Cloud Function name"
}

output "scheduler_job_name" {
  value       = google_cloud_scheduler_job.daily_data_ingestion.name
  description = "Cloud Scheduler job name"
}
