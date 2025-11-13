def get_variant(swimlane: str):
    """Get mc-gcp-to-ieb variant based on Event Bus Swimlane."""
    if swimlane == "mailchimp":
        variant = "msc"
    elif swimlane == "gbsg":
        variant = "gbsc"
    elif swimlane == "aifabric":
        variant = "aifabric"

    return variant
