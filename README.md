# mc-gcp-to-ieb-config

## Overview

This repository serves as the single source of truth for defining domain event streams. Users declare their stream configurations in YAML files, and this tool automatically generates all required infrastructure configs for:

| Generator | Output | Purpose |
|-----------|--------|---------|
| **Terraform** | Pantropy module blocks | Provisions GCP resources (Pub/Sub topics, subscriptions, BigQuery tables) |
| **Kafka** | Connector configs | Configures Kafka Connect source/sink connectors in `mc-gcp-to-ieb` |
| **Materialization** | Airflow DAG Configuration | Configures an airflow DAG to run periodically to materialize your data into a native BigQuery table |


## Quick Start

### 1. Setup

```bash
cd path/to/mc-gcp-to-ieb-config
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Local Paths

Create a `user_config.yaml` file in the repo root with your local paths to Pantropy, mc-gcp-to-ieb, airflow, and iedm-schema:

```yaml
# user_config.yaml (gitignored)
pantropy_path: /your/path/to/pantropy/terraform/data/business-intelligence/mc-domain-events/{env}/table_streams_domain_events.tf
mc_gcp_to_ieb_path: /your/path/to/mc-gcp-to-ieb/app/mc_gcp_to_ieb/configs/{environment}/{direction}-{variant}/
airflow_path: /your/path/to/airflow
iedm_path: /your/path/to/iedm-schema
```

> **Note:** The `{env}`, `{environment}`, `{direction}`, and `{variant}` placeholders are replaced at runtime. No need to update those values.

### 3. Define Your Stream

Create or update a YAML file in the appropriate swimlane/environment directory:

```
mc_gcp_to_ieb_config/configs/<swimlane>/<env>/ingest.yaml   # Kafka → BigQuery
mc_gcp_to_ieb_config/configs/<swimlane>/<env>/publish.yaml  # BigQuery → Kafka
```

### 4. Generate Configs

```bash
source .venv/bin/activate

# Generate Terraform modules
python cli.py terraform sync

# Generate Kafka connector configs
python cli.py kafka sync

# Generate airflow DAG configs for materialization
python cli.py materialization sync
```

## Directory Structure

```
mc_gcp_to_ieb_config/
├── configs/                    # Stream definitions (your source of truth)
│   ├── aifabric/
│   │   ├── e2e/
│   │   │   ├── ingest.yaml
│   │   │   └── publish.yaml
│   │   └── prd/
│   ├── gbsg/
│   │   ├── e2e/
│   │   └── prd/
│   └── mailchimp/
│       ├── e2e/
│       ├── stg/
│       └── prd/
├── services/                   # Generation logic
│   ├── gcp/                    # Terraform module generation
│   └── kafka/                  # Kafka connector config generation
├── templates/                  # Jinja2 templates
│   ├── kafka/
│   │   └── connector_config.yaml.j2
│   └── terraform/
│       └── terraform_module.j2
└── utils/                      # Shared utilities
```

### Swimlanes

| Swimlane | Variant | Description |
|----------|---------|-------------|
| `mailchimp` | `msc` | Mailchimp swimlane cluster |
| `gbsg` | `gbsc` | GBSG swimlane cluster |
| `aifabric` | `aifabric` | AI Fabric swimlane cluster |

### Environments

| Environment | Terraform Target |
|-------------|------------------|
| `stg` | staging |
| `e2e` | staging |
| `prd` | prod |

### Direction

| File | Data Flow | Connector Type |
|------|-----------|----------------|
| `ingest.yaml` | Kafka → GCP (BigQuery) | Sink connector |
| `publish.yaml` | GCP (BigQuery) → Kafka | Source connector |

## Stream Configuration Reference

```yaml
streams:
  - name: my-event-stream                    # Required: Unique stream identifier
    kafka_topic: e2e-domain-entity-v1        # Required: Full Kafka topic name
    kafka_topic_entity_name: my-entity       # Required: Entity name portion of topic
    entity_version: v1                       # Required: Schema version (v1, v2, etc.)
    level_0: crmandmarketing                 # Required: Domain Event level 0 classification
    level_1: marketingchannelmanagement      # Required: Domain Event level 1 classification
    max_tasks: 3                             # Required: Kafka Connect parallelism
    schemas_enable: true                     # Required: Enable schema registry

    # Optional: Override auto-generated Pub/Sub names
    pub_sub_topic: custom-topic-name         # For ingest (sink) connectors
    pub_sub_subscription: custom-sub-name    # For publish (source) connectors

    # Optional: Grant roles/pubsub.Publisher to service accounts on the topic
    publishers:
      - serviceAccount:123456-compute@developer.gserviceaccount.com
      - serviceAccount:another-sa@project.iam.gserviceaccount.com

    # Optional: Skip sync for legacy configs (see "Legacy Configurations" section)
    skip_terraform_sync: true                # Skip Terraform module generation
    skip_kafka_sync: true                    # Skip Kafka connector generation

    # Optional: GCP labels for cost attribution
    labels:
      intuit-billing-capability: my-capability
      intuit-billing-service: my-service

    # Optional: Materialization Config
    materializtion:
      enabled: true                          # materialize the table?
      iedm_schema_location_override: custom/path/to/entity.schema.json  # Optional: If your IEDM schema path does not match the kafka topic name, you can override it here.
      timestamp_format: your_custom_format   # Optional: if your timestamp format is not ISO 8601, you can enter a custom one here
      materialization_schedule: 1d           # Optional: one of (1h, 3h, 1d): specifies how frequently you want the materialized table to merge in new data

```

### Field Details

| Field | Required | Description |
|-------|----------|-------------|
| `name` | YES | Unique identifier for the stream |
| `kafka_topic` | YES | Full Kafka topic name as it appears in Event Bus |
| `kafka_topic_entity_name` | YES | Short entity name used in naming conventions |
| `entity_version` | YES | Version string (e.g., `v1`, `v2`) |
| `level_0` | YES | Level 0 Domain classification |
| `level_1` | YES | Level 1 Domain classification |
| `max_tasks` | YES | Number of Kafka Connect tasks for parallelism |
| `schemas_enable` | YES | Whether to use Schema Registry (`true`/`false`) Default=true |
| `pub_sub_topic` | NO | Custom Pub/Sub topic name (auto-generated if omitted) |
| `pub_sub_subscription` | NO | Custom Pub/Sub subscription name (auto-generated if omitted) |
| `publishers` | NO | List of service accounts to grant `roles/pubsub.Publisher` on the topic |
| `skip_terraform_sync` | NO | If `true`, skip Terraform generation (for legacy configs) |
| `skip_kafka_sync` | NO | If `true`, skip Kafka connector generation (for legacy configs) |
| `labels` | NO | Key-value pairs for GCP resource labeling |
| `materialization` | NO | Key-value pairs for materialization |


## CLI Commands

```bash
# Show all available commands
python cli.py --help

# Terraform commands
python cli.py terraform --help
python cli.py terraform sync          # Generate Terraform modules

# Kafka commands
python cli.py kafka --help
python cli.py kafka sync              # Generate Kafka connector configs

# Materialization commands
python cli.py materialization --help
python cli.py materialization sync    # Generate Materialization DAG configs
```

## Generated Output

### Terraform Module

The `terraform sync` command appends module blocks to Pantropy's Terraform files:

```hcl
module "crmandmarketing_marketingchannelmanagement_my-entity_v1__stream" {
  source                  = "./table-stream"
  direction               = "ingest"
  swimlane                = "mailchimp"
  environment             = "e2e"
  kafka_topic_entity_name = "my-entity"
  entity_version          = "v1"
  level_0                 = "crmandmarketing"
  level_1                 = "marketingchannelmanagement"
  gcp_labels              = local.gcp_labels
}
```

### IAM Binding (when `publishers` specified)

If you specify `publishers` in your stream config, the tool generates IAM bindings to grant `roles/pubsub.publisher`. These are written to `iam.tf` in the same directory as the other IAM Terraform modules (e.g., `pantropy/.../mc-domain-events/staging/iam.tf`):

```hcl
resource "google_pubsub_topic_iam_member" "crmandmarketing_marketingchannelmanagement_my-entity_v1__publisher_0" {
  project = var.project_id
  topic   = "publish-mailchimp-crmandmarketing_marketingchannelmanagement_my-entity_v1"
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:123456-compute@developer.gserviceaccount.com"
}
```

### Kafka Connector Config

The `kafka sync` command appends connector entries to `mc-gcp-to-ieb`:

```yaml
name: my-entity
level_0: crmandmarketing
level_1: marketingchannelmanagement
entity_version: v1
kafka_topic: e2e-domain-entity-v1
pub_sub_topic: ingest-mailchimp-crmandmarketing_marketingchannelmanagement_my-entity_v1
max_tasks: 3
schemas_enable: true
```

### Materialization Config

The `materialization sync` command adds config to airflow, along with an iedm schema file. This tells the airflow DAG how to materialize the event log table into a native bigquery table, and at what frequency (default is 3h)

```
tables_to_materialize:
- materialized_table_name: acquired_contact
  events_table_id: mc-domain-events-prod.mailchimp.crmandmarketing_unifiedcontactprofiles_acquired_contact_v1
  schema_path: crmandmarketing/unifiedcontactprofiles/c2profile/entities/AcquiredContact.json
  primary_keys:
  - id
  ...
```

## Adding a New Stream

1. **Identify your swimlane**: `mailchimp`, `gbsg`, or `aifabric` (more to come)
2. **Choose the direction**: `ingest.yaml` (Kafka→BQ) or `publish.yaml` (BQ→Kafka)
3. **Add your stream config** to the appropriate YAML file
4. **Run the generators**:
   ```bash
   python cli.py terraform sync
   python cli.py kafka sync
   ```

   Optional:
   ```bash
   python cli.py materialization sync
   ```

5. **Commit changes** to both this repo and the generated output repos
6. **Request approval** from the `data-movement` (#mc-l2-data-movement?) team:
   - First, get your `Pantropy` PR approved and merged.
   - Then, request review and merge for your `mc-gcp-to-ieb` PR.
   - Last (optional) If you specified materialization, review and merge the `airflow` PR

## Legacy Configurations

Some streams that were deployed before this repo was created have non-standard naming in Terraform or Kafka. These configs are documented here as the source of truth but use skip flags to prevent generating duplicate infrastructure:

| Flag | Purpose |
|------|---------|
| `skip_terraform_sync: true` | Terraform module already exists with different naming convention |
| `skip_kafka_sync: true` | Kafka connector already exists or is test data |

**When to use skip flags:**
- The stream was deployed manually before this tool existed
- The Terraform module name doesn't match the standard pattern: `{level_0}_{level_1}_{entity}_{version}__stream`
- The config is test/sample data not intended for deployment

**Example:**

```yaml
- name: aisle_beacons
  kafka_topic: aisle_beacons
  kafka_topic_entity_name: aisle_beacons
  entity_version: v1
  level_0: aifabric
  level_1: crmandmarketing
  max_tasks: 3
  schemas_enable: true
  skip_terraform_sync: true  # Legacy module: aifabric_aisle_beacons__stream (non-standard)
```

> **Note:** New streams should NOT use skip flags. Only use them for documenting pre-existing legacy deployments.
