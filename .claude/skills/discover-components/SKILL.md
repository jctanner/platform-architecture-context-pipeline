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

### Step 2a: Probe for Release Payload Signals

Before breadcrumb exploration, check whether the platform has **formal release inclusion signals** — annotations, manifests, or metadata that explicitly declare which repos ship in the product. Large platforms (OpenShift, OKD, etc.) often have these; small platforms typically don't.

**Why this matters:** Without payload signals, the skill must infer "is this shipped?" from heuristics (has Dockerfile? has operator structure?). On a platform with 800+ repos where 179 are operators, heuristics produce a useless component map. Payload signals give a definitive answer.

**Probe procedure — sample 5-10 repos** (prefer repos named `cluster-*-operator` or `*-controller`) and scan their `manifests/` directories for known signal patterns:

#### Signal 1: Release Inclusion Annotations
```bash
grep -r "include.release.openshift.io\|release.openshift.io\|operator.openshift.io/managed" {sample_repo}/manifests/ 2>/dev/null
```
These annotations declare that a component ships in a specific release profile (self-managed, single-node, hypershift, etc.).

#### Signal 2: Capability/Optional Annotations
```bash
grep -r "capability.openshift.io/name\|operator.openshift.io/capability" {sample_repo}/manifests/ 2>/dev/null
```
These mark a payload component as **optional** — it ships by default but can be disabled. Components WITHOUT this annotation (but WITH release inclusion) are **core**.

#### Signal 3: Image Reference Manifests
```bash
ls {sample_repo}/manifests/image-references {sample_repo}/install/image-references 2>/dev/null
```
A structured file listing container images the repo contributes to the release payload.

#### Signal 4: OLM Catalog Membership
```bash
ls {sample_repo}/bundle/manifests/*.clusterserviceversion.yaml 2>/dev/null
```
If a central catalog repo exists (e.g., `certified-operators`, `redhat-operators`), check whether this repo's CSV is listed there.

#### Signal 5: Helm Chart Index / Kustomize Catalog
```bash
ls {sample_repo}/charts/ {sample_repo}/Chart.yaml 2>/dev/null
```
For Helm-based platforms, check if a central chart index references this repo.

**If signals are found in 3+ sampled repos**, this platform has formal payload signals. Set `discovery_method: "release_payload_signals"` and proceed with a **full signal scan**:

#### Full Signal Scan

Scan ALL repos in the checkouts directory for the detected signal type(s). Classify each repo into a tier:

| Tier | Criteria | Example |
|------|----------|---------|
| `core_platform` | Has release inclusion annotations but NO capability/optional annotation | `cluster-etcd-operator` |
| `optional_platform` | Has release inclusion annotations AND a capability/optional annotation | `cluster-samples-operator` |
| `payload_component` | Has `image-references` but no release/capability annotations | Supporting images shipped in payload |
| `ecosystem` | No release signals at all | `aws-account-operator` |

**Record the tier for each repo.** This tiering drives the rest of the discovery process:
- `core_platform` + `optional_platform` → full breadcrumb exploration in Steps 3-5
- `payload_component` → include as component, lighter exploration
- `ecosystem` → skip breadcrumb exploration, go directly to excluded (can be pulled back in by dependency analysis in Step 5a/5b)

**If signals are NOT found** (fewer than 3 sampled repos match), this platform doesn't have formal payload signals. Set `discovery_method: "breadcrumb"` and proceed to Step 3 with the full candidate list as before.

### Step 3: Find Entry Points

**If release payload signals were found (Step 2a):** Limit candidate repos to those in the `core_platform`, `optional_platform`, and `payload_component` tiers. Do NOT treat every operator-shaped repo as an entry point — only those with release signals.

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

### Step 5b: Identify Architecturally Significant External APIs

Some third-party repos aren't utilities you *use* — they're contracts you *implement*. These define the CRDs, APIs, or interface specifications that shape your platform's architecture. Excluding them loses critical architectural context.

**After shared library detection, scan excluded third-party repos for API contract significance:**

1. Repo exists in the checkouts directory (the platform team chose to mirror/fork it)
2. Primarily defines APIs, CRDs, or interface contracts — look for:
   - `apis/`, `config/crd/`, protobuf definitions (`.proto` files)
   - Module is mostly types/interfaces (Go: types, structs, interfaces; Python: abstract base classes, schemas)
   - Kubernetes API machinery (`GroupVersionResource`, `runtime.Object` implementations)
3. Platform components import its types as **direct** (not indirect/transitive) dependencies
4. High reference count in core control-plane or reconciliation code — the platform's controllers are **structured around** these types, not just calling utility functions

**How to measure architectural impact:**
```bash
# Count references to the repo's types in core platform code
grep -r "Gateway\|HTTPRoute\|GRPCRoute" {platform_repo}/pilot/ | wc -l
# If this is in the hundreds across core packages, it's architectural
```

**The key distinction: tool vs. contract**
- `django` is a **tool** — you call its functions, but your architecture doesn't revolve around Django types
- `gateway-api` is a **contract** — your controllers exist to reconcile its CRDs, your entire ingress model is defined by its types

**For detected API specifications:**
- Mark as `type: "api_specification"`
- Set `shipped: false` (not your code)
- Set `architecturally_significant: true`
- Add `upstream_org` field to clarify ownership (e.g., `"kubernetes-sigs"`)
- Add `consumer_count` and `consumers: [...]`
- Include in component map (don't exclude!)
- Add a note clarifying it is upstream-owned but architecturally foundational

**Examples:**
- ✅ `gateway-api` - Kubernetes Gateway API (defines CRDs that Istio's control plane reconciles)
- ✅ `operator-framework/api` - OLM API types (if platform operators are built around them)
- ✅ `open-cluster-management/api` - OCM API types (if platform implements OCM contracts)
- ❌ `envoy` - Upstream runtime dependency (you embed it, but don't implement its API spec)
- ❌ `go-control-plane` - Utility library (you call it, architecture doesn't revolve around its types)
- ❌ `client-go` - Kubernetes client library (tool, not contract)

### Step 6: Classify Remaining Repos

**If release payload signals were found (Step 2a):** The default is inverted. Repos without release signals are `ecosystem` tier and should be excluded unless they were pulled in as a shared library (Step 5a) or API specification (Step 5b). Do NOT apply the "possible shipped components" heuristics below to ecosystem-tier repos — the release signals are the authoritative source.

**If NO release payload signals were found:** Use the heuristics below for repos not discovered via breadcrumbs:

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
    "discovery_method": "breadcrumb|release_payload_signals",
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
      "type": "operator|service|shared_library|api_specification",
      "tier": "core_platform|optional_platform|payload_component|ecosystem",
      "discovered_via": "release_payload_signal|operator_bundle|container_image|dependency|installer",
      "referenced_by": ["installer"],
      "shipped": true,
      "architecturally_significant": true,
      "consumer_count": 3,
      "consumers": ["awx-operator", "eda-operator", "hub-operator"],
      "capability": "optional-capability-name-if-applicable"
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
Discovery method: {Breadcrumb exploration | Release payload signals}

Results:
  Total repositories scanned: {total}
  Components discovered: {discovered}
  Components excluded: {excluded}

--- If release payload signals were found: ---

Release payload signals detected: {signal_types}

Core platform ({count}):
  ✓ cluster-etcd-operator (type: operator, tier: core_platform)
  ✓ cluster-kube-apiserver-operator (type: operator, tier: core_platform)
  ✓ machine-config-operator (type: operator, tier: core_platform)
  ...

Optional platform ({count}):
  ✓ cluster-samples-operator (type: operator, tier: optional_platform, capability: openshift-samples)
  ✓ console-operator (type: operator, tier: optional_platform, capability: Console)
  ...

Shared libraries / API specs:
  ✓ library-go (type: shared_library, used by: N components) [ARCHITECTURALLY SIGNIFICANT]
  ✓ gateway-api (type: api_specification, upstream: kubernetes-sigs) [ARCHITECTURALLY SIGNIFICANT]
  ...

Ecosystem (excluded — no release payload signals):
  ✗ aws-account-operator (ecosystem)
  ✗ addon-operator (ecosystem)
  ... and {N} more

--- If NO release payload signals found (breadcrumb mode): ---

Entry points used:
  - {entry1}
  - {entry2}

Discovered components:
  ✓ awx-operator (type: operator, via: operator_bundle, ref by: installer)
  ✓ eda-operator (type: operator, via: operator_bundle, ref by: installer)
  ✓ awx-api (type: service, via: container_image, ref by: awx-operator)
  ✓ django-ansible-base (type: shared_library, used by: 3 components) [ARCHITECTURALLY SIGNIFICANT]
  ✓ gateway-api (type: api_specification, upstream: kubernetes-sigs) [ARCHITECTURALLY SIGNIFICANT]
  ...

Excluded repositories:
  ✗ ansible-docs (documentation_only)
  ✗ ansible-ci-tools (development_tooling)
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

**Definitive (release payload signals — Step 2a):**
- Has `include.release.openshift.io/*` or equivalent release inclusion annotation → definitely in payload
- No `capability.openshift.io/name` → `tier: core_platform` (always installed)
- Has `capability.openshift.io/name` → `tier: optional_platform` (can be disabled)
- Has `image-references` manifest → ships container images in the release

When payload signals are available, they override all heuristic confidence levels below.

**High confidence (definitely deployed) — breadcrumb mode fallback:**
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
- Third-party utility dependencies (django, flask, postgres, redis)
- Docs/wiki repos (no code, just markdown)
- CI/CD tooling repos
- Test frameworks and utilities
- Development helpers
- Archived/stale repos (no commits in 12+ months)

**Exception — do NOT exclude external API specifications:**
- If a third-party repo defines CRDs/APIs that your platform *implements* (not just *uses*), include it as `type: "api_specification"` per Step 5b
- The test: do your controllers/reconcilers exist to serve this repo's types? If yes, it's a contract, not a utility

**How to distinguish first-party from third-party:**
- First-party: In the same GitHub org as platform
- Third-party: External dependencies (PyPI, npm, Go modules)
- Third-party API spec: External org, but defines contracts your platform implements (see Step 5b)

**Special cases:**
- One-off dependencies (only used by 1 component): Exclude unless deployed
- Internal tools (used by developers, not shipped): Exclude
- Vendored third-party code: Exclude (treat as third-party)
- Mirrored/forked API spec repos: Include if they meet Step 5b criteria

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

### Critical: Don't Exclude Shared Libraries or API Contracts!

**Common mistake #1:** Excluding repos because they're "just dependencies"

**Why this is wrong:**
- First-party shared libraries (like django-ansible-base) are architecturally critical
- They're YOUR code, not third-party packages
- Security vulnerabilities in shared libraries impact ALL consumers
- Understanding the platform requires understanding shared foundations
- Architecture reviews need to see the full dependency picture

**Common mistake #2:** Excluding external repos because they're "third-party upstream"

**Why this is wrong for API specs:**
- Some external repos define the API contracts your platform implements
- Your controllers/reconcilers are structured around their types
- Excluding them makes your architecture diagrams incomplete — the CRDs your control plane reconciles just vanish
- Understanding *what* your platform implements is as important as understanding *how*

**Rule of thumb:**
- If it's in the same GitHub org AND used by 2+ components → INCLUDE as `type: "shared_library"`
- If it's external BUT defines CRDs/APIs your platform implements → INCLUDE as `type: "api_specification"`
- If it's external AND just a utility you call → EXCLUDE (django, postgres, redis)

**Example distinction:**
- ✅ Include: `ansible/django-ansible-base` (first-party, used by AWX + EDA + Hub)
- ✅ Include: `kubernetes-sigs/gateway-api` (external, but Istio's control plane implements its CRDs)
- ❌ Exclude: `django/django` (third-party utility, not in ansible org)
- ❌ Exclude: `postgres` (infrastructure, third-party)
- ❌ Exclude: `envoyproxy/go-control-plane` (third-party library you call, not a contract you implement)
