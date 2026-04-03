"""Command-line argument parsing for the architecture tool."""

import argparse


def resolve_script_path(platform: str, org: str = None, branch: str = None,
                        checkouts_dir: str = "checkouts", script_path: str = None) -> str:
    """
    Resolve the path to get_all_manifests.sh.

    Args:
        platform: Platform type (odh or rhoai)
        org: GitHub org (auto-detected if None)
        branch: Branch name (optional)
        checkouts_dir: Base checkouts directory
        script_path: Explicit override path (returned as-is if provided)

    Returns:
        Path string to get_all_manifests.sh
    """
    if script_path:
        return script_path

    if not org:
        org = "opendatahub-io" if platform == "odh" else "red-hat-data-services"

    operator_name = "opendatahub-operator" if platform == "odh" else "rhods-operator"

    if branch:
        org_dir = f"{org}.{branch}"
    else:
        org_dir = org

    return f"{checkouts_dir}/{org_dir}/{operator_name}/get_all_manifests.sh"


def parse_args():
    """Parse command line arguments with subcommands for each phase."""
    parser = argparse.ArgumentParser(
        description="Repository processing and analysis tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Phase to run")

    # Phase 1: Fetch repositories
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch/clone repositories using gh-org-clone"
    )
    fetch_parser.add_argument(
        "org",
        help="GitHub organization name to clone"
    )
    fetch_parser.add_argument(
        "--checkouts-dir",
        default="checkouts",
        help="Directory to clone repositories into (default: checkouts)"
    )
    fetch_parser.add_argument(
        "--branch",
        help="Specific branch to clone (skips repos without this branch)"
    )

    # Phase 2a: Parse manifests (for platforms with manifest scripts)
    manifest_parser = subparsers.add_parser(
        "parse-manifests",
        help="Parse get_all_manifests.sh to extract component info"
    )
    manifest_parser.add_argument(
        "--platform",
        choices=["odh", "rhoai"],
        required=True,
        help="Platform to parse (odh or rhoai)"
    )
    manifest_parser.add_argument(
        "--org",
        help="GitHub organization name (auto-detected if not provided)"
    )
    manifest_parser.add_argument(
        "--branch",
        help="Branch name if using versioned checkout (e.g., rhoai-2.14)"
    )
    manifest_parser.add_argument(
        "--checkouts-dir",
        default="checkouts",
        help="Base directory containing cloned repositories (default: checkouts)"
    )
    manifest_parser.add_argument(
        "--script-path",
        help="Override path to get_all_manifests.sh script (auto-detected if not provided)"
    )
    manifest_parser.add_argument(
        "--format",
        choices=["summary", "json"],
        default="summary",
        help="Output format: summary (human-readable) or json (structured data)"
    )
    manifest_parser.add_argument(
        "--write-map",
        action="store_true",
        help="Write component-map.json to architecture/{platform}/"
    )

    # Phase 2b: Discover components (for platforms without manifest scripts)
    discover_parser = subparsers.add_parser(
        "discover-components",
        help="Discover components by exploring breadcrumbs (installers, operators, dependencies)"
    )
    discover_parser.add_argument(
        "--platform",
        required=True,
        help="Platform identifier (e.g., 'aap', 'ansible')"
    )
    discover_parser.add_argument(
        "--checkouts-dir",
        required=True,
        help="Directory containing cloned repositories"
    )
    discover_parser.add_argument(
        "--entry-repo",
        help="Starting point repository (e.g., 'installer', 'operator')"
    )
    discover_parser.add_argument(
        "--architecture-dir",
        default="architecture",
        help="Output directory (default: architecture)"
    )
    discover_parser.add_argument(
        "--exclude",
        help="Additional repos to exclude (comma-separated patterns)"
    )
    discover_parser.add_argument(
        "--model",
        choices=["sonnet", "opus", "haiku"],
        default="sonnet",
        help="Claude model to use for discovery (default: sonnet)"
    )

    # Phase 3: Generate architecture
    generate_arch_parser = subparsers.add_parser(
        "generate-architecture",
        help="Check component repos for GENERATED_ARCHITECTURE.md files"
    )
    generate_arch_parser.add_argument(
        "--platform",
        help="Platform to process. Can be 'odh', 'rhoai', 'aap', or any custom platform name. "
             "If using a component-map.json, this should match the platform name used in discovery."
    )
    generate_arch_parser.add_argument(
        "--org",
        help="GitHub organization name (auto-detected if not provided)"
    )
    generate_arch_parser.add_argument(
        "--branch",
        help="Branch name if using versioned checkout (e.g., rhoai-2.14)"
    )
    generate_arch_parser.add_argument(
        "--checkouts-dir",
        default="checkouts",
        help="Base directory containing cloned repositories (default: checkouts)"
    )
    generate_arch_parser.add_argument(
        "--script-path",
        help="Override path to get_all_manifests.sh script (auto-detected if not provided)"
    )
    generate_arch_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of agents to run concurrently (default: 5)"
    )
    generate_arch_parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of components to process (for testing)"
    )
    generate_arch_parser.add_argument(
        "--component",
        action="append",
        dest="components",
        help="Only process specific component(s). Supports glob patterns (e.g., 'eda*', 'awx-*'). Can be specified multiple times."
    )
    generate_arch_parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing GENERATED_ARCHITECTURE.md and regenerate"
    )
    generate_arch_parser.add_argument(
        "--model",
        choices=["sonnet", "opus", "haiku"],
        default="opus",
        help="Claude model to use (default: opus)"
    )

    # Phase 4: Collect architectures
    collect_parser = subparsers.add_parser(
        "collect-architectures",
        help="Collect and organize GENERATED_ARCHITECTURE.md files into architecture/ directory"
    )
    collect_parser.add_argument(
        "--checkouts-dir",
        default="checkouts",
        help="Directory containing platform checkouts (default: checkouts)"
    )
    collect_parser.add_argument(
        "--output-dir",
        default="architecture",
        help="Output directory for organized architectures (default: architecture)"
    )
    collect_parser.add_argument(
        "--org",
        help="Collect from a specific org (e.g., 'ansible', 'opendatahub-io'). Takes precedence over --platform."
    )
    collect_parser.add_argument(
        "--platform",
        help="Which platform to collect (e.g., 'odh', 'rhoai', 'aap', or 'all' for all platforms). "
             "Ignored if --org is specified."
    )
    collect_parser.add_argument(
        "--version",
        help="Only collect this specific version (default: all versions)"
    )

    # Phase 5: Generate platform architectures
    platform_arch_parser = subparsers.add_parser(
        "generate-platform-architecture",
        help="Generate PLATFORM.md files for architecture directories that need them"
    )
    platform_arch_parser.add_argument(
        "--architecture-dir",
        default="architecture",
        help="Base architecture directory (default: architecture)"
    )
    platform_arch_parser.add_argument(
        "--checkouts-dir",
        default="checkouts",
        help="Base directory containing cloned repositories (default: checkouts)"
    )
    platform_arch_parser.add_argument(
        "--platform",
        help="Only process this platform (e.g., 'odh', 'rhoai', 'ansible'). Default: all platforms."
    )
    platform_arch_parser.add_argument(
        "--version",
        help="Only process this version (default: all)"
    )
    platform_arch_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of agents to run concurrently (default: 5)"
    )
    platform_arch_parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of platforms to process (for testing)"
    )
    platform_arch_parser.add_argument(
        "--model",
        choices=["sonnet", "opus", "haiku"],
        default="opus",
        help="Claude model to use (default: opus)"
    )
    platform_arch_parser.add_argument(
        "--entry-component",
        help="Primary component to start analysis from (e.g., 'awx-operator'). "
             "The skill will read this component first and organically discover related components."
    )

    # Phase 6: Generate diagrams
    diagrams_parser = subparsers.add_parser(
        "generate-diagrams",
        help="Generate diagrams for architecture files that need them"
    )
    diagrams_parser.add_argument(
        "--architecture-dir",
        default="architecture",
        help="Base architecture directory (default: architecture)"
    )
    diagrams_parser.add_argument(
        "--platform",
        help="Only process this platform (e.g., 'odh', 'rhoai', 'ansible'). Default: all platforms."
    )
    diagrams_parser.add_argument(
        "--version",
        help="Only process this version (default: all)"
    )
    diagrams_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of agents to run concurrently (default: 5)"
    )
    diagrams_parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of files to process (for testing)"
    )
    diagrams_parser.add_argument(
        "--component",
        action="append",
        dest="components",
        help="Only process specific component(s). Use 'platform' for PLATFORM.md. "
             "Supports glob patterns (e.g., 'awx-*'). Can be specified multiple times."
    )
    diagrams_parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Regenerate diagrams even if they already exist"
    )
    diagrams_parser.add_argument(
        "--model",
        choices=["sonnet", "opus", "haiku"],
        default="opus",
        help="Claude model to use (default: opus)"
    )

    # All phases
    all_parser = subparsers.add_parser(
        "all",
        help="Run all phases in sequence"
    )
    all_parser.add_argument(
        "--platform",
        choices=["odh", "rhoai"],
        default="odh",
        help="Platform to process (default: odh)"
    )
    all_parser.add_argument(
        "--org",
        help="GitHub organization to clone (auto-detected if not provided)"
    )
    all_parser.add_argument(
        "--branch",
        help="Specific branch to clone (e.g., rhoai-2.14 for RHOAI versions)"
    )
    all_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of agents to run concurrently (default: 5)"
    )
    all_parser.add_argument(
        "--model",
        choices=["sonnet", "opus", "haiku"],
        default="opus",
        help="Claude model to use for all agent tasks (default: opus)"
    )

    return parser.parse_args()
