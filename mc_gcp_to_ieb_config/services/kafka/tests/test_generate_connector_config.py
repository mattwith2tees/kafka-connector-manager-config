"""Tests for generate_connector_config.py - specifically sync_connector_configs."""

import os
import tempfile
import yaml
import pytest

from mc_gcp_to_ieb_config.services.kafka.generate_connector_config import (
    sync_connector_configs,
    get_config_key,
)


class TestGetConfigKey:
    """Tests for get_config_key function."""

    def test_returns_tuple_of_key_fields(self):
        config = {
            "name": "mtlc2metrics",
            "level_0": "crmandmarketing",
            "level_1": "mailchimp",
            "entity_version": "v3",
            "max_tasks": 12,
        }
        key = get_config_key(config)
        assert key == ("mtlc2metrics", "crmandmarketing", "mailchimp", "v3")

    def test_handles_missing_fields(self):
        config = {"name": "test"}
        key = get_config_key(config)
        assert key == ("test", None, None, None)


class TestSyncConnectorConfigs:
    """Tests for sync_connector_configs function."""

    def test_adds_new_config_to_empty_file(self):
        """New configs should be added when file is empty."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            source_configs = [
                {
                    "name": "mtlc2metrics",
                    "level_0": "crmandmarketing",
                    "level_1": "mailchimp",
                    "entity_version": "v3",
                    "max_tasks": 12,
                }
            ]

            sync_connector_configs(source_configs, temp_path)

            with open(temp_path, "r") as f:
                result = yaml.safe_load(f)

            assert len(result) == 1
            assert result[0]["name"] == "mtlc2metrics"
            assert result[0]["max_tasks"] == 12
        finally:
            os.unlink(temp_path)

    def test_adds_new_config_to_existing_file(self):
        """New configs should be added alongside existing ones."""
        existing = [
            {
                "name": "existing",
                "level_0": "level0",
                "level_1": "level1",
                "entity_version": "v1",
                "max_tasks": 3,
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(existing, f)
            temp_path = f.name

        try:
            source_configs = [
                {
                    "name": "existing",
                    "level_0": "level0",
                    "level_1": "level1",
                    "entity_version": "v1",
                    "max_tasks": 3,
                },
                {
                    "name": "new_connector",
                    "level_0": "level0",
                    "level_1": "level1",
                    "entity_version": "v2",
                    "max_tasks": 6,
                },
            ]

            sync_connector_configs(source_configs, temp_path)

            with open(temp_path, "r") as f:
                result = yaml.safe_load(f)

            assert len(result) == 2
            names = [c["name"] for c in result]
            assert "existing" in names
            assert "new_connector" in names
        finally:
            os.unlink(temp_path)

    def test_removes_deleted_config(self):
        """Configs not in source should be removed."""
        existing = [
            {
                "name": "keep_me",
                "level_0": "level0",
                "level_1": "level1",
                "entity_version": "v1",
                "max_tasks": 3,
            },
            {
                "name": "delete_me",
                "level_0": "level0",
                "level_1": "level1",
                "entity_version": "v2",
                "max_tasks": 3,
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(existing, f)
            temp_path = f.name

        try:
            # Source only has one config - the other should be removed
            source_configs = [
                {
                    "name": "keep_me",
                    "level_0": "level0",
                    "level_1": "level1",
                    "entity_version": "v1",
                    "max_tasks": 3,
                }
            ]

            sync_connector_configs(source_configs, temp_path)

            with open(temp_path, "r") as f:
                result = yaml.safe_load(f)

            assert len(result) == 1
            assert result[0]["name"] == "keep_me"
        finally:
            os.unlink(temp_path)

    def test_updates_max_tasks(self):
        """Changes to max_tasks should be propagated."""
        existing = [
            {
                "name": "mtlc2metrics",
                "level_0": "crmandmarketing",
                "level_1": "mailchimp",
                "entity_version": "v3",
                "max_tasks": 3,  # Old value
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(existing, f)
            temp_path = f.name

        try:
            # Source has updated max_tasks
            source_configs = [
                {
                    "name": "mtlc2metrics",
                    "level_0": "crmandmarketing",
                    "level_1": "mailchimp",
                    "entity_version": "v3",
                    "max_tasks": 12,  # New value
                }
            ]

            sync_connector_configs(source_configs, temp_path)

            with open(temp_path, "r") as f:
                result = yaml.safe_load(f)

            assert len(result) == 1
            assert result[0]["max_tasks"] == 12  # Should be updated!
        finally:
            os.unlink(temp_path)

    def test_updates_any_field_change(self):
        """Any field change should trigger an update."""
        existing = [
            {
                "name": "connector",
                "level_0": "level0",
                "level_1": "level1",
                "entity_version": "v1",
                "max_tasks": 3,
                "schemas_enable": False,
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(existing, f)
            temp_path = f.name

        try:
            source_configs = [
                {
                    "name": "connector",
                    "level_0": "level0",
                    "level_1": "level1",
                    "entity_version": "v1",
                    "max_tasks": 3,
                    "schemas_enable": True,  # Changed!
                }
            ]

            sync_connector_configs(source_configs, temp_path)

            with open(temp_path, "r") as f:
                result = yaml.safe_load(f)

            assert result[0]["schemas_enable"] == True
        finally:
            os.unlink(temp_path)

    def test_no_changes_when_identical(self, capsys):
        """No file write when configs are identical."""
        existing = [
            {
                "name": "connector",
                "level_0": "level0",
                "level_1": "level1",
                "entity_version": "v1",
                "max_tasks": 3,
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(existing, f)
            temp_path = f.name

        try:
            # Identical source
            source_configs = [
                {
                    "name": "connector",
                    "level_0": "level0",
                    "level_1": "level1",
                    "entity_version": "v1",
                    "max_tasks": 3,
                }
            ]

            sync_connector_configs(source_configs, temp_path)

            captured = capsys.readouterr()
            assert "No changes needed" in captured.out
        finally:
            os.unlink(temp_path)

    def test_handles_nonexistent_file(self):
        """Should create file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "new_connectors.yaml")

            source_configs = [
                {
                    "name": "new_connector",
                    "level_0": "level0",
                    "level_1": "level1",
                    "entity_version": "v1",
                    "max_tasks": 3,
                }
            ]

            sync_connector_configs(source_configs, temp_path)

            assert os.path.exists(temp_path)
            with open(temp_path, "r") as f:
                result = yaml.safe_load(f)

            assert len(result) == 1
            assert result[0]["name"] == "new_connector"

    def test_complex_scenario_add_update_remove(self):
        """Test adding, updating, and removing in one sync."""
        existing = [
            {
                "name": "keep_unchanged",
                "level_0": "l0",
                "level_1": "l1",
                "entity_version": "v1",
                "max_tasks": 3,
            },
            {
                "name": "to_update",
                "level_0": "l0",
                "level_1": "l1",
                "entity_version": "v2",
                "max_tasks": 3,  # Will change to 6
            },
            {
                "name": "to_remove",
                "level_0": "l0",
                "level_1": "l1",
                "entity_version": "v3",
                "max_tasks": 3,
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(existing, f)
            temp_path = f.name

        try:
            source_configs = [
                {
                    "name": "keep_unchanged",
                    "level_0": "l0",
                    "level_1": "l1",
                    "entity_version": "v1",
                    "max_tasks": 3,
                },
                {
                    "name": "to_update",
                    "level_0": "l0",
                    "level_1": "l1",
                    "entity_version": "v2",
                    "max_tasks": 6,  # Updated!
                },
                {
                    "name": "new_connector",
                    "level_0": "l0",
                    "level_1": "l1",
                    "entity_version": "v4",
                    "max_tasks": 12,
                },
                # Note: "to_remove" is NOT in source - should be deleted
            ]

            sync_connector_configs(source_configs, temp_path)

            with open(temp_path, "r") as f:
                result = yaml.safe_load(f)

            assert len(result) == 3

            result_by_name = {c["name"]: c for c in result}

            # Unchanged
            assert result_by_name["keep_unchanged"]["max_tasks"] == 3

            # Updated
            assert result_by_name["to_update"]["max_tasks"] == 6

            # Added
            assert "new_connector" in result_by_name
            assert result_by_name["new_connector"]["max_tasks"] == 12

            # Removed
            assert "to_remove" not in result_by_name
        finally:
            os.unlink(temp_path)


