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

Look for patterns like:
- `django-ansible-base>=1.0.0` - First-party package (matches repo name)
- `-e git+https://github.com/ansible/django-ansible-base.git` - Editable install from git
- `file:///path/to/local/repo` - Local dependency

**Go** (`go.mod`):
```bash
find {entry_repo} -name "go.mod"
cat {found_files}
```

Look for:
- `github.com/ansible/common-lib v1.0.0` - First-party module
- `replace github.com/ansible/foo => ../foo` - Local replacement

**Key insight:** If a dependency name matches a repo in the checkouts directory, it's likely a first-party shared library!

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
3. Track what type of reference (deployed_component vs. dependency)
4. Mark as `shipped: true` if deployed directly

Track the dependency graph:
```
{
  "installer": ["awx-operator", "eda-operator"],
  "awx-operator": ["awx-api", "awx-ui", "django-ansible-base"],
  "eda-operator": ["eda-server", "django-ansible-base"],
  ...
}
```

### Step 5a: Identify Shared Libraries

After building the dependency graph, analyze it to find shared libraries:

**Reverse the dependency graph** to count consumers:
```
{
  "awx-operator": ["installer"],                          # 1 consumer
  "eda-operator": ["installer"],                          # 1 consumer
  "awx-api": ["awx-operator"],                           # 1 consumer
  "django-ansible-base": ["awx-operator", "eda-operator", "automation-hub-operator"]  # 3 consumers!
}
```

**Shared library detection criteria:**
1. Is a dependency (not deployed standalone)
2. Used by 2+ platform components
3. In the same organization (first-party, not third-party)
4. Contains actual code (not just config/docs)

**For detected shared libraries:**
- Mark as `type: "shared_library"`
- Set `shipped: false` (not deployed directly)
- Set `architecturally_significant: true`
- Add `consumer_count` and `consumers: [...]`
- Include in component map (don't exclude!)

**Examples:**
- ✅ `django-ansible-base` - Shared Django utilities used by AWX, EDA, Hub
- ✅ `ansible-common-auth` - Shared authentication library
- ✅ `platform-sdk` - SDK used by multiple operators
- ❌ `django` - Third-party (not in platform org)
- ❌ `postgres` - Third-party infrastructure
- ❌ `one-off-util` - Only used by one component

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
      "type": "operator|service|shared_library",
      "discovered_via": "operator_bundle|container_image|dependency|installer",
      "referenced_by": ["installer"],
      "shipped": true,
      "architecturally_significant": true,
      "consumer_count": 3,
      "consumers": ["awx-operator", "eda-operator", "hub-operator"]
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
  ✓ awx-operator (type: operator, via: operator_bundle, ref by: installer)
  ✓ eda-operator (type: operator, via: operator_bundle, ref by: installer)
  ✓ awx-api (type: service, via: container_image, ref by: awx-operator)
  ✓ eda-server (type: service, via: container_image, ref by: eda-operator)
  ✓ django-ansible-base (type: shared_library, used by: 3 components) [ARCHITECTURALLY SIGNIFICANT]
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

## Heuristics for Component Classification

### Include: Deployed Components (shipped: true)

**High confidence (definitely deployed):**
- Referenced in operator manifests
- Referenced in installer playbooks
- Container image built in CI and pushed to registry
- Listed in OLM bundle
- Has operator structure (bundle/, config/manager/)

**Medium confidence (probably deployed):**
- Has Kubernetes manifests
- Has recent releases
- Referenced by other high-confidence components

**Low confidence (maybe deployed):**
- Has Dockerfile
- Active development
- Matches naming pattern

### Include: Shared Libraries (shipped: false, architecturally_significant: true)

**Critical shared libraries:**
- First-party code (same GitHub org)
- Used by 2+ platform components
- Contains actual code (not just config/docs)
- Examples: django-ansible-base, shared authentication libraries, common SDKs

**Detection method:**
1. Found in requirements.txt, pyproject.toml, go.mod of multiple repos
2. Reverse dependency count ≥ 2
3. Repo exists in checkouts directory (first-party)
4. Has source code (not a meta-repo)

**Why include them:**
- Critical for understanding platform architecture
- Needed for security reviews (shared code paths)
- Dependency impact analysis (if library has vulnerability, which components affected?)
- Architecture dependencies (components share behavior through these)

### Exclude: Non-Components

**Always exclude:**
- Third-party dependencies (django, flask, postgres, redis)
- Docs/wiki repos (no code, just markdown)
- CI/CD tooling repos
- Test frameworks and utilities
- Development helpers
- Archived/stale repos (no commits in 12+ months)

**How to distinguish first-party from third-party:**
- First-party: In the same GitHub org as platform
- Third-party: External dependencies (PyPI, npm, Go modules)

**Special cases:**
- One-off dependencies (only used by 1 component): Exclude unless deployed
- Internal tools (used by developers, not shipped): Exclude
- Vendored third-party code: Exclude (treat as third-party)

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

### Critical: Don't Exclude Shared Libraries!

**Common mistake:** Excluding repos because they're "just dependencies"

**Why this is wrong:**
- First-party shared libraries (like django-ansible-base) are architecturally critical
- They're YOUR code, not third-party packages
- Security vulnerabilities in shared libraries impact ALL consumers
- Understanding the platform requires understanding shared foundations
- Architecture reviews need to see the full dependency picture

**Rule of thumb:**
- If it's in the same GitHub org AND used by 2+ components → INCLUDE IT
- Mark it as `type: "shared_library"` and `architecturally_significant: true`
- This is different from third-party deps like django, postgres, redis (exclude those)

**Example distinction:**
- ✅ Include: `ansible/django-ansible-base` (first-party, used by AWX + EDA + Hub)
- ❌ Exclude: `django/django` (third-party, not in ansible org)
- ❌ Exclude: `postgres` (infrastructure, third-party)
