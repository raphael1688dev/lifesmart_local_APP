#!/usr/bin/env python3
"""Does any Home Assistant function this integration calls report a deprecation?

    python3 tools/ha_api_audit.py 2026.11.1 dev

For each ref (a core tag, or `dev` for the next release) the script downloads
the Home Assistant modules listed in USED, finds each function by name, and
looks for a `report_usage(...)`-style call inside its body. Three times a
deprecated call was shipped because nobody looked (R25: button event types,
R25: device registry lookups, found in R27 / R28); this makes looking one
command.

It prints every hit. Hits listed in NOT_APPLICABLE are conditions this
integration does not meet (checked when they were added). Anything else
exits 1: read the message, then either change the code or add the hit to
NOT_APPLICABLE with the reason.

Keep USED in step with the code: when a new Home Assistant function is
called, add it here. The script fails if a listed name no longer appears in
the integration, so the list cannot quietly rot. It cannot see deprecated
*attributes* or constants (e.g. `DeviceEntry.config_entries`, enum members);
for those, grep the module for `deprecat` by hand.
"""
from __future__ import annotations

import ast
import pathlib
import sys
import urllib.request

RAW = "https://raw.githubusercontent.com/home-assistant/core/{ref}/homeassistant/{path}"
PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "lifesmart"

# module -> functions / methods the integration calls
USED: dict[str, list[str]] = {
    "helpers/device_registry.py": [
        "async_get", "async_get_or_create", "async_update_device",
        "async_get_device_by_identifier", "async_entries_for_config_entry",
    ],
    "helpers/entity_registry.py": ["async_get", "async_update_entity", "async_get_entity_id"],
    "helpers/issue_registry.py": ["async_create_issue", "async_delete_issue", "async_get_or_create"],
    "helpers/event.py": ["async_track_time_interval", "async_call_later"],
    "helpers/update_coordinator.py": [
        "__init__", "async_add_listener", "async_set_updated_data", "async_request_refresh",
    ],
    "helpers/config_validation.py": ["config_entry_only_config_schema"],
    "config_entries.py": [
        "async_forward_entry_setups", "async_unload_platforms_or_raise", "async_update_entry",
        "async_schedule_reload", "async_get_entry", "async_loaded_entries",
        "async_create_background_task", "async_start_reauth", "_get_reauth_entry",
        "async_set_unique_id", "_abort_if_unique_id_configured", "async_update_reload_and_abort",
        "async_create_entry", "async_show_form",
        # R42 (missed then) and R43
        "_get_reconfigure_entry", "async_entry_for_domain_unique_id",
        "_async_abort_entries_match", "_async_current_entries",
    ],
    # R43: discovery.py
    "helpers/discovery_flow.py": ["async_create_flow"],
    "components/network/__init__.py": ["async_get_ipv4_broadcast_addresses"],
    "data_entry_flow.py": ["async_show_form", "async_create_entry", "add_suggested_values_to_schema"],
    "core.py": ["async_add_executor_job", "async_register", "async_create_background_task"],
}

# Names in USED that the integration reaches only through Home Assistant
# (e.g. `ir.async_create_issue` calls `async_get_or_create`), or that are
# spelled differently at the call site. Exempt from the "still used" check.
INDIRECT = {"async_get_or_create", "__init__", "async_get"}

# (function, fragment of the message) -> why it does not apply here
NOT_APPLICABLE: dict[tuple[str, str], str] = {
    ("async_update_device", "add_config_entry_id"):
        "only with add_/remove_config_entry_id arguments; we pass new_identifiers / model / sw_version",
    ("async_update_device", "merge_connections"):
        "only with merge_connections / merge_identifiers; not used",
    ("__init__", "relies on ContextVar"):
        "only when config_entry is not passed; both coordinators pass it explicitly since R30 (tested)",
    ("_abort_if_unique_id_configured", "has an update listener"):
        "only for entries with an update listener; this integration has none",
    ("async_update_reload_and_abort", "has an update listener"):
        "only for entries with an update listener; this integration has none",
    ("async_get_or_create", "different config"):
        "issue registry: fires when an issue id moves to another config entry; our ids contain the entry id",
}

REPORTERS = ("report_usage", "_report_deprecated", "report_issue")


def fetch(ref: str, path: str) -> str:
    request = urllib.request.Request(RAW.format(ref=ref, path=path), headers={"User-Agent": "ha-api-audit"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed https host)
        return response.read().decode()


def reports_in(node: ast.AST) -> list[tuple[str, str | None, str]]:
    """(reporter, breaks_in_ha_version, message) for each report call in node."""
    found = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        label = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if not any(reporter in label for reporter in REPORTERS):
            continue
        message = ""
        for arg in [*sub.args, *(keyword.value for keyword in sub.keywords)]:
            if isinstance(arg, ast.JoinedStr):  # f-string: keep its literal parts
                message = "".join(part.value for part in arg.values if isinstance(part, ast.Constant))
            elif isinstance(arg, ast.Constant) and isinstance(arg.value, str) and len(arg.value) > 12:
                message = arg.value
            if message:
                break
        breaks = next(
            (keyword.value.value for keyword in sub.keywords
             if keyword.arg == "breaks_in_ha_version" and isinstance(keyword.value, ast.Constant)),
            None,
        )
        found.append((label, breaks, message))
    return found


def audit(ref: str) -> int:
    unexplained = 0
    print(f"== {ref}")
    for path, names in USED.items():
        tree = ast.parse(fetch(ref, path))
        seen = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in names:
                continue
            seen.add(node.name)
            for label, breaks, message in reports_in(node):
                reason = next(
                    (why for (name, fragment), why in NOT_APPLICABLE.items()
                     if name == node.name and fragment in message),
                    None,
                )
                status = f"not applicable: {reason}" if reason else "UNEXPLAINED"
                unexplained += reason is None
                print(f"  {path}:{node.lineno} {node.name}() {label} breaks={breaks}\n      {message[:150]}\n      -> {status}")
        for missing in sorted(set(names) - seen):
            unexplained += 1
            print(f"  {path}: {missing}() not found in this ref -> UNEXPLAINED (removed or renamed?)")
    return unexplained


def stale_names() -> list[str]:
    source = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py"))
    return sorted(
        name for names in USED.values() for name in names
        if name not in INDIRECT and name not in source
    )


def main(refs: list[str]) -> int:
    if not refs:
        print(__doc__)
        return 2
    stale = stale_names()
    if stale:
        print(f"USED lists functions the integration no longer calls: {stale}")
    unexplained = sum(audit(ref) for ref in refs)
    print(f"\n{unexplained} unexplained hit(s)" if unexplained else "\nno unexplained hits")
    return 1 if unexplained or stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
