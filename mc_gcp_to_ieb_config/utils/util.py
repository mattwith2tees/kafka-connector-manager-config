SWIMLANE_TO_VARIANT = {
    "mailchimp": "msc",
    "gbsg": "gbsc",
    "aifabric": "aifabric",
    "gtm": "gtm",
}


def get_variant(swimlane: str) -> str:
    """Get mc-gcp-to-ieb variant based on Event Bus Swimlane."""
    if swimlane not in SWIMLANE_TO_VARIANT:
        raise ValueError(
            f"Unknown swimlane: {swimlane}. Expected one of: {list(SWIMLANE_TO_VARIANT.keys())}"
        )
    return SWIMLANE_TO_VARIANT[swimlane]
