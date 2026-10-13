"""Fixed schema projection and ID ordering."""


def build(schema):
    catalog, seen_services, seen_ids = [], set(), set()
    for service in schema:
        name, description = service.get("service_name"), service.get("description")
        if not isinstance(name, str) or not isinstance(description, str) or name in seen_services:
            raise ValueError("Invalid or duplicate schema service")
        seen_services.add(name)
        intents = service.get("intents")
        if not isinstance(intents, list):
            raise ValueError(f"Invalid schema intents: {name}")
        projected = []
        for intent in intents:
            if not isinstance(intent.get("name"), str) or not isinstance(intent.get("description"), str):
                raise ValueError(f"Invalid schema intent: {name}")
            identifier = f"{name}/{intent['name']}"
            if identifier in seen_ids:
                raise ValueError(f"Duplicate catalog ID: {identifier}")
            seen_ids.add(identifier)
            projected.append({"id": identifier, "description": intent["description"]})
        catalog.append({"service": name, "description": description, "intents": projected})
    if len(seen_ids) != 38:
        raise ValueError("Expected 38 catalog IDs")
    return catalog


def intent_order(catalog):
    return {intent["id"]: rank for rank, intent in enumerate(
        intent for service in catalog for intent in service["intents"])}
