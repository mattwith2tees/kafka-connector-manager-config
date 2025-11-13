def get_variant(swimlane: str):
    if swimlane == "mailchimp":
        variant = "msc"
    elif swimlane == "gbsg":
        variant = "gbsc"
    elif swimlane == "aifabric":
        variant = "aifabric"

    return variant
