"""Component discovery utilities for reading/writing component maps."""

import json
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

from lib.manifest_parser import ComponentInfo


def write_component_map(
    platform: str,
    components: Dict[str, ComponentInfo],
    metadata: Dict[str, Any],
    architecture_dir: str = "architecture"
) -> Path:
    """
    Write component map to architecture/<platform>/component-map.json.

    Args:
        platform: Platform name (e.g., "aap", "rhoai", "odh")
        components: Dict of component key -> ComponentInfo
        metadata: Discovery metadata (method, entry_point, stats, etc.)
        architecture_dir: Base architecture directory

    Returns:
        Path to written component-map.json
    """
    output_dir = Path(architecture_dir) / platform
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "component-map.json"

    # Build component map structure
    component_data = {}
    for key, comp in components.items():
        component_data[key] = {
            "key": comp.key,
            "repo_org": comp.repo_org,
            "repo_name": comp.repo_name,
            "ref": comp.ref,
            "source_folder": comp.source_folder,
            "checkout_path": str(comp.checkout_path) if comp.checkout_path else None,
            "has_architecture": comp.has_architecture,
        }

    # Add timestamp if not present
    if "discovered_at" not in metadata:
        metadata["discovered_at"] = datetime.now().isoformat()

    # Build full map
    component_map = {
        "metadata": metadata,
        "components": component_data
    }

    # Write to file
    output_file.write_text(json.dumps(component_map, indent=2))

    return output_file


def read_component_map(
    platform: str,
    architecture_dir: str = "architecture"
) -> Optional[Dict[str, ComponentInfo]]:
    """
    Read component map from architecture/<platform>/component-map.json.

    Args:
        platform: Platform name (e.g., "aap", "rhoai", "odh")
        architecture_dir: Base architecture directory

    Returns:
        Dict of component key -> ComponentInfo, or None if not found
    """
    map_file = Path(architecture_dir) / platform / "component-map.json"

    if not map_file.exists():
        return None

    data = json.loads(map_file.read_text())

    # Convert back to ComponentInfo objects
    components = {}
    for key, comp_data in data.get("components", {}).items():
        components[key] = ComponentInfo(
            key=comp_data["key"],
            repo_org=comp_data["repo_org"],
            repo_name=comp_data["repo_name"],
            ref=comp_data["ref"],
            source_folder=comp_data["source_folder"],
            checkout_path=Path(comp_data["checkout_path"]) if comp_data.get("checkout_path") else None,
            has_architecture=comp_data.get("has_architecture", False)
        )

    return components


def get_component_map_metadata(
    platform: str,
    architecture_dir: str = "architecture"
) -> Optional[Dict[str, Any]]:
    """
    Read only the metadata from component-map.json.

    Args:
        platform: Platform name
        architecture_dir: Base architecture directory

    Returns:
        Metadata dict, or None if not found
    """
    map_file = Path(architecture_dir) / platform / "component-map.json"

    if not map_file.exists():
        return None

    data = json.loads(map_file.read_text())
    return data.get("metadata", {})
