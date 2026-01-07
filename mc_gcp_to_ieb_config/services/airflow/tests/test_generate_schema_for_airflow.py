from mc_gcp_to_ieb_config.services.airflow.generate_schema_for_airflow import (
    get_airflow_directory_to_write_schema,
    get_filename,
    guess_iedm_schema_file,
    AIRFLOW_SCHEMA_ROOT,
)

import pytest

guess_iedm_schema_test_data = [
    (
        "crmandmarketing",
        "unifiedcontactprofiles",
        "prd-crmandmarketing-unifiedcontactprofiles-c2profile-enriched-product-viewed-event-v1",
        "enriched_product_viewed_event",
        "crmandmarketing/unifiedcontactprofiles/c2profile/entities/EnrichedProductViewedEvent.schema.json",
    ),
    (
        "crmandmarketing",
        "unifiedcontactprofiles",
        "prd-crmandmarketing-unifiedcontactprofiles-c2profile-acquired-contact-v1",
        "acquired_contact",
        "crmandmarketing/unifiedcontactprofiles/c2profile/entities/AcquiredContact.schema.json",
    ),
    (
        "crmandmarketing",
        "unifiedcontactprofiles",
        "prd-crmandmarketing-unifiedcontactprofiles-c2profile-enriched-booking-v1",
        "enriched_booking",
        "crmandmarketing/unifiedcontactprofiles/c2profile/entities/EnrichedBooking.schema.json",
    ),
]


def test_get_airflow_directory_to_write_schema():
    assert (
        get_airflow_directory_to_write_schema("foo/bar/Baz.schema.json")
        == f"{AIRFLOW_SCHEMA_ROOT}/foo/bar"
    )


def test_get_filename():
    assert get_filename("foo/bar/Baz.schema.json") == "Baz.json"


@pytest.mark.parametrize(
    "level_0,level_1,kafka_topic,kafka_topic_entity_name,expected", guess_iedm_schema_test_data
)
def test_guess_iedm_schema_file(level_0, level_1, kafka_topic, kafka_topic_entity_name, expected):
    entity_version = "v1"
    assert (
        guess_iedm_schema_file(
            level_0, level_1, kafka_topic, kafka_topic_entity_name, entity_version
        )
        == expected
    )
