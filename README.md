# mc-gcp-to-ieb-config

## Overview

This repository serves as the single source of truth for defining domain event streams. Users declare their stream configurations in YAML files, and this tool automatically generates all required infrastructure configs for:

| Generator | Output | Purpose |
|-----------|--------|---------|
| **Terraform** | Pantropy module blocks | Provisions GCP resources (Pub/Sub topics, subscriptions, BigQuery tables) |
| **Kafka** | Connector configs | Configures Kafka Connect source/sink connectors in `mc-gcp-to-ieb` |


## Quick Start

### 1. Setup

```bash
cd path/to/mc-gcp-to-ieb-config
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Define Your Stream

Create or update a YAML file in the appropriate swimlane/environment directory:

```
mc_gcp_to_ieb_config/configs/<swimlane>/<env>/ingest.yaml   # Kafka → BigQuery
mc_gcp_to_ieb_config/configs/<swimlane>/<env>/publish.yaml  # BigQuery → Kafka
```

### 3. Generate Configs

```bash
source .venv/bin/activate

# Generate Terraform modules
python cli.py terraform sync

# Generate Kafka connector configs
python cli.py kafka sync

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

    # Optional: GCP labels for cost attribution
    labels:
      intuit-billing-capability: my-capability
      intuit-billing-service: my-service
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
| `labels` | NO | Key-value pairs for GCP resource labeling |

## CLI Commands

```bash
# Show all available commands
python cli.py --help

# Terraform commands
python cli.py terraform --help
python cli.py terraform sync    # Generate Terraform modules

# Kafka commands
python cli.py kafka --help
python cli.py kafka sync        # Generate Kafka connector configs
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

## Adding a New Stream

1. **Identify your swimlane**: `mailchimp`, `gbsg`, or `aifabric` (more to come)
2. **Choose the direction**: `ingest.yaml` (Kafka→BQ) or `publish.yaml` (BQ→Kafka)
3. **Add your stream config** to the appropriate YAML file
4. **Run the generators**:
   ```bash
   python cli.py terraform sync
   python cli.py kafka sync
   ```
5. **Commit changes** to both this repo and the generated output repos
6. **Request approval** from the `#data-movement` team:
   - First, get your `Pantropy` PR approved and merged.
   - Then, request review and merge for your `mc-gcp-to-ieb` PR.


