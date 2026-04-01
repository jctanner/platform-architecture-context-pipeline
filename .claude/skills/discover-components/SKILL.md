---
name: discover-components
description: Discover platform components by exploring breadcrumbs (installers, operators, dependencies) in checkouts directory. Outputs component-map.json for platforms without manifest scripts.
allowed-tools: Read, Glob, Grep, Write, Bash(ls *), Bash(find *), Bash(cat *), Bash(grep *)
---

# Discover Components

Discover which repositories in a checkouts directory are actual platform components (shipped in the product) vs. side projects, tools, or helpers.

This is used for platforms that don't have a central manifest script (like ODH/RHOAI's `get_all_manifests.sh`). Instead, we explore "breadcrumbs" to build a component map:

## Breadcrumb Types

1. **Operators** - Kubernetes operators with OLM bundles
2. **Container Images** - Referenced in manifests, Dockerfiles, CI configs
3. **Dependencies** - Listed in requirements files, go.mod, package.json
4. **Installers** - Ansible playbooks, Helm charts, deployment scripts
5. **Build Artifacts** - What gets built in CI/CD pipelines

## Arguments

Required:
- `--platform=<name>` - Platform identifier (e.g., "aap", "ansible")
- `--checkouts-dir=<path>` - Directory containing cloned repos

Optional:
- `--entry-repo=<name>` - Starting point repo (e.g., "installer", "operator")
- `--architecture-dir=<path>` - Output directory (default: architecture)
- `--exclude=<pattern>` - Additional repos to exclude (comma-separated)

## Instructions

### Step 1: Scan Checkouts Directory

List all subdirectories in the checkouts directory:

```bash
ls -1 {checkouts_dir}/
```

This gives you the universe of possible components.

### Step 2: Initial Filtering

Exclude obvious non-components:
- Directories starting with `.` (hidden)
- Common patterns:
  - `*-docs`, `*-documentation`
  - `*-ci`, `*-tools`, `*-testing`, `*-test`
  - `must-gather`, `cli`, `additional-images`
  - Build/release infrastructure repos

Create an initial list of candidate repos.

### Step 3: Find Entry Points

If `--entry-repo` specified, start there. Otherwise, search for common entry points:

**Operator repos** (high-value entry points):
- Directories containing `bundle/`, `config/manager/`, `operator.yaml`
- Typically named: `*-operator`, `operator`

**Installer repos**:
- Directories containing: `install.yml`, `site.yml`, `playbooks/`
- Typically named: `installer`, `*-installer`, `deployment`

**Platform repos**:
- Directories with platform-wide configs
- Names like: `platform`, `automation-platform`, `*-platform`

List discovered entry points and pick the best one (or use all).

### Step 4: Explore Breadcrumbs from Entry Points

For each entry point, look for references to other repos:

#### 4a. Kubernetes Manifests
Search for container image references:

```bash
grep -r "image:" {entry_repo}/config/ {entry_repo}/manifests/ {entry_repo}/bundle/
```

Extract repo names from image paths like:
- `quay.io/ansible/awx-operator:latest` → `awx-operator`
- `registry.redhat.io/ansible/eda-server:1.0` → `eda-server`

#### 4b. Ansible Playbooks
Search for role/collection references:

```bash
grep -r "role:" {entry_repo}/
grep -r "collection:" {entry_repo}/
```

#### 4c. Dependency Files

**Python** (`requirements.txt`, `pyproject.toml`):
```bash
find {entry_repo} -name "requirements*.txt" -o -name "pyproject.toml"
cat {found_files}
```

**Go** (`go.mod`):
```bash
find {entry_repo} -name "go.mod"
cat {found_files}
```

Look for local/relative dependencies that might be other repos.

#### 4d. Git Submodules
```bash
cat {entry_repo}/.gitmodules
```

#### 4e. CI/CD Pipelines
```bash
find {entry_repo} -path "*/.github/workflows/*.yml" -o -path "*/.gitlab-ci.yml"
cat {found_files}
```

Look for:
- Build jobs
- Image build steps
- Deployment steps
- References to other repos

### Step 5: Build Component Graph

As you discover references:
1. Check if referenced repo exists in checkouts directory
2. If yes, add to component list with `discovered_via` and `referenced_by`
3. Mark as `shipped: true` (since it's referenced by an entry point)

Track the dependency graph:
```
{
  "installer": ["awx-operator", "eda-operator"],
  "awx-operator": ["awx-api", "awx-ui"],
  ...
}
```

### Step 6: Classify Remaining Repos

For repos not discovered via breadcrumbs:

**Possible shipped components** (include with lower confidence):
- Has `Dockerfile` or `Containerfile`
- Has Kubernetes manifests (`config/`, `manifests/`)
- Has operator structure (`bundle/`, `config/manager/`)
- Has recent git activity (within last 6 months)
- Has releases/tags

**Definitely not shipped** (exclude):
- Documentation only (no code)
- CI/CD tooling repos
- Test utilities
- Development helpers
- Archived/stale (no commits in 12+ months)

### Step 7: Check for Existing Architectures

For each discovered component, check if `GENERATED_ARCHITECTURE.md` exists:

```bash
ls {checkouts_dir}/{repo_name}/GENERATED_ARCHITECTURE.md
```

Set `has_architecture: true/false` accordingly.

### Step 8: Build Output JSON

Create the component map structure:

```json
{
  "metadata": {
    "platform": "{platform}",
    "discovery_method": "breadcrumb",
    "entry_point": "{entry_repo or 'multiple'}",
    "discovered_at": "{ISO timestamp}",
    "checkouts_dir": "{checkouts_dir}",
    "total_repos_scanned": {count},
    "components_discovered": {count},
    "components_excluded": {count}
  },
  "components": {
    "{component-key}": {
      "key": "{component-key}",
      "repo_org": "{org}",
      "repo_name": "{repo-name}",
      "ref": "main",
      "source_folder": "config",
      "checkout_path": "{full-path}",
      "has_architecture": false,
      "discovered_via": "operator_bundle|container_image|dependency|installer",
      "referenced_by": ["installer"],
      "shipped": true
    }
  },
  "dependency_graph": {
    "{repo}": ["{dep1}", "{dep2}"]
  },
  "excluded": {
    "{repo-name}": "{reason}"
  }
}
```

### Step 9: Write Output

Write to `architecture/{platform}/component-map.json`:

```python
# Use Write tool
```

### Step 10: Report Summary

Output a summary to the user:

```
================================================================================
Component Discovery Complete
================================================================================

Platform: {platform}
Checkouts directory: {checkouts_dir}
Discovery method: Breadcrumb exploration

Results:
  Total repositories scanned: {total}
  Components discovered: {discovered}
  Components excluded: {excluded}

Entry points used:
  - {entry1}
  - {entry2}

Discovered components:
  ✓ awx-operator (via: operator_bundle, ref by: installer)
  ✓ eda-operator (via: operator_bundle, ref by: installer)
  ✓ awx-api (via: container_image, ref by: awx-operator)
  ✓ eda-server (via: container_image, ref by: eda-operator)
  ...

Excluded repositories:
  ✗ ansible-docs (documentation_only)
  ✗ ansible-ci-tools (development_tooling)
  ✗ test-helpers (test_utilities)
  ...

Output: architecture/{platform}/component-map.json

Next steps:
1. Review component-map.json (edit if needed)
2. Run: python main.py generate-architecture --platform={platform}
3. Run: python main.py collect-architectures --platform={platform}
================================================================================
```

## Heuristics for Shipped Components

High confidence (definitely shipped):
- Referenced in operator manifests
- Referenced in installer playbooks
- Container image built in CI and pushed to registry
- Listed in OLM bundle

Medium confidence (probably shipped):
- Has operator structure
- Has recent releases
- Has Kubernetes manifests
- Referenced by other high-confidence components

Low confidence (maybe shipped):
- Has Dockerfile
- Active development
- Matches naming pattern

Exclude:
- Docs/wiki repos
- CI/CD tooling
- Test frameworks
- Development utilities
- Archived/stale repos

## Error Handling

- If no entry point found, use operator detection heuristics
- If checkouts directory doesn't exist, error and exit
- If no components discovered, warn but output empty map
- If breadcrumb parsing fails, continue with next repo

## Notes

- This is heuristic-based, not perfect
- User can manually edit `component-map.json` after generation
- Designed for platforms without central manifest scripts
- Outputs same format as manifest parser for pipeline compatibility
