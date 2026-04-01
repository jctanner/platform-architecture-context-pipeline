# Component Discovery

This pipeline supports two methods for discovering which repositories are part of a platform:

## Method 1: Manifest-Based (ODH/RHOAI)

For platforms with a central manifest script (like `get_all_manifests.sh`):

```bash
python main.py parse-manifests --platform=rhoai --write-map
```

This parses the manifest script and optionally writes a `component-map.json` file.

## Method 2: Breadcrumb-Based (Ansible/AAP)

For platforms without a manifest script, discover components by exploring breadcrumbs:

```bash
python main.py discover-components \
  --platform=aap \
  --checkouts-dir=./checkouts/ansible \
  --entry-repo=awx-operator
```

### How Breadcrumb Discovery Works

The discovery process:

1. **Scans checkouts directory** - Lists all cloned repositories
2. **Finds entry points** - Operators, installers, platform repos
3. **Explores breadcrumbs**:
   - Container image references in manifests
   - Dependencies in requirements files (Python, Go, JS)
   - Git submodules
   - CI/CD pipeline references
   - Ansible roles/collections
4. **Builds dependency graph** - Tracks which repos reference which
5. **Filters components**:
   - High confidence: Referenced in operators/installers
   - Medium confidence: Has operator structure, recent releases
   - Excluded: Docs, CI tools, test utilities, archived repos
6. **Writes component map** - `architecture/<platform>/component-map.json`

### Breadcrumb Types

- **Operators**: OLM bundles, `config/manager/`, `operator.yaml`
- **Container Images**: Image references in YAML manifests
- **Dependencies**: `requirements.txt`, `go.mod`, `package.json`
- **Installers**: Ansible playbooks, Helm charts
- **Build Artifacts**: CI/CD workflow definitions

## Component Map Format

Both methods output the same format:

```json
{
  "metadata": {
    "platform": "aap",
    "discovery_method": "breadcrumb|manifest_script",
    "discovered_at": "2026-04-01T10:30:00Z",
    "total_repos_scanned": 237,
    "components_discovered": 42,
    "components_excluded": 195
  },
  "components": {
    "awx-operator": {
      "key": "awx-operator",
      "repo_org": "ansible",
      "repo_name": "awx-operator",
      "ref": "main",
      "source_folder": "config",
      "checkout_path": "checkouts/ansible/awx-operator",
      "has_architecture": false,
      "discovered_via": "operator_bundle",
      "referenced_by": ["installer"],
      "shipped": true
    }
  },
  "dependency_graph": {
    "installer": ["awx-operator", "eda-operator"]
  },
  "excluded": {
    "ansible-docs": "documentation_only"
  }
}
```

## Using Component Maps

Later phases automatically read from `component-map.json`:

```bash
# Generate architecture summaries
python main.py generate-architecture --platform=aap

# Collect into organized structure
python main.py collect-architectures --platform=aap

# Generate platform summary
python main.py generate-platform-architecture --platform=aap
```

## Manual Editing

You can manually edit `component-map.json` to:
- Add missed components
- Remove false positives
- Adjust refs/source_folders
- Fix component metadata

Just edit the file and re-run later phases.

## Workflow Comparison

### Manifest-Based (ODH/RHOAI)
```bash
# 1. Parse manifest (writes map)
python main.py parse-manifests --platform=rhoai --write-map

# 2. Later phases read the map automatically
python main.py generate-architecture --platform=rhoai
```

### Breadcrumb-Based (Ansible/AAP)
```bash
# 1. Discover via breadcrumbs (writes map)
python main.py discover-components \
  --platform=aap \
  --checkouts-dir=./checkouts/ansible

# 2. Later phases read the map automatically
python main.py generate-architecture --platform=aap
```

Both approaches produce the same `component-map.json` format, so the rest of the pipeline is identical.
