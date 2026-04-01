# Platform Architecture Context Pipeline - Documentation

## Overview

This pipeline analyzes platform components and generates comprehensive architecture documentation using Claude AI agents.

## Key Features

- **Multiple Discovery Methods**: Manifest-based or breadcrumb-based component discovery
- **Flexible Skill Invocation**: Direct skill execution or templated prompt injection
- **Multi-Platform Support**: Works with ODH, RHOAI, Ansible/AAP, and custom platforms
- **Component Maps**: Persistent, editable component definitions
- **Concurrent Processing**: Run multiple agents in parallel
- **Resumable**: Skip already-processed components

## Architecture

```
Phase 1: Fetch repositories (gh-org-clone)
   ↓
Phase 2: Discover components
   ├─ 2a: parse-manifests (manifest script) → component-map.json
   └─ 2b: discover-components (breadcrumbs) → component-map.json
   ↓
Phase 3: generate-architecture (per component) → GENERATED_ARCHITECTURE.md
   ↓
Phase 4: collect-architectures → architecture/<platform>/*.md
   ↓
Phase 5: generate-platform-architecture → PLATFORM.md
   ↓
Phase 6: generate-diagrams → diagrams/*.{mmd,dsl,png}
```

## Component Discovery

The pipeline supports two discovery methods depending on your platform:

### Manifest-Based (ODH/RHOAI)
```bash
python main.py parse-manifests --platform=rhoai --write-map
```

### Breadcrumb-Based (Ansible/AAP)
```bash
python main.py discover-components \
  --platform=aap \
  --checkouts-dir=./checkouts/ansible \
  --entry-repo=awx-operator
```

Both write to: `architecture/<platform>/component-map.json`

See: [component-discovery.md](./component-discovery.md)

## Skill Invocation Patterns

The pipeline uses two approaches for running AI agents:

### 1. Direct Skill Invocation
Claude discovers and invokes skills automatically:
```python
result = await run_agent(job, log_dir, model, enable_skills=True)
```

### 2. Templated Prompts
Extract instructions and inject runtime context:
```python
instructions = extract_instructions_from_skill("skill-name")
prompt = f"{runtime_context}\n\n{instructions}"
result = await run_agent(job, log_dir, model)
```

See: [skill-invocation-patterns.md](./skill-invocation-patterns.md)

## Directory Structure

```
.
├── main.py                      # Entry point
├── lib/
│   ├── phases.py               # Phase orchestrators
│   ├── agent_runner.py         # Agent execution utilities
│   ├── manifest_parser.py      # Manifest script parsing
│   ├── component_discovery.py  # Component map I/O
│   ├── build_info.py           # RHOAI build metadata
│   └── kustomize_context.py    # Kustomize overlay context
├── .claude/skills/
│   ├── discover-components/    # Breadcrumb-based discovery
│   ├── repo-to-architecture-summary/  # Component analysis
│   ├── collect-component-architectures/  # Organization
│   ├── aggregate-platform-architecture/  # Platform summary
│   └── generate-architecture-diagrams/  # Diagram generation
├── architecture/
│   └── <platform>/
│       ├── component-map.json  # Component definitions
│       ├── *.md                # Component architectures
│       ├── PLATFORM.md         # Platform summary
│       └── diagrams/           # Generated diagrams
└── logs/                       # Agent execution logs
```

## Quick Start

### For ODH/RHOAI (manifest-based):
```bash
# Full pipeline
python main.py all --platform=rhoai --branch=rhoai-2.25

# Or step-by-step
python main.py fetch red-hat-data-services --branch=rhoai-2.25
python main.py parse-manifests --platform=rhoai --branch=rhoai-2.25 --write-map
python main.py generate-architecture --platform=rhoai --max-concurrent=5
python main.py collect-architectures --platform=rhoai
python main.py generate-platform-architecture --platform=rhoai
python main.py generate-diagrams --platform=rhoai
```

### For Ansible/AAP (breadcrumb-based):
```bash
# Assuming repos already cloned in ./checkouts/ansible/
python main.py discover-components \
  --platform=aap \
  --checkouts-dir=./checkouts/ansible

# Then same as above
python main.py generate-architecture --platform=aap
python main.py collect-architectures --platform=aap
python main.py generate-platform-architecture --platform=aap
python main.py generate-diagrams --platform=aap
```

## Component Map Format

Central to the pipeline is the `component-map.json` file:

```json
{
  "metadata": {
    "platform": "aap",
    "discovery_method": "breadcrumb",
    "discovered_at": "2026-04-01T10:30:00Z",
    "components_discovered": 42
  },
  "components": {
    "awx-operator": {
      "key": "awx-operator",
      "repo_org": "ansible",
      "repo_name": "awx-operator",
      "ref": "main",
      "source_folder": "config",
      "checkout_path": "checkouts/ansible/awx-operator",
      "has_architecture": false
    }
  }
}
```

This file is:
- **Inspectable**: Review before processing
- **Editable**: Manually add/remove components
- **Resumable**: Tracks which components have architectures
- **Portable**: Version-controlled definition of platform components

## CLI Commands

```bash
# Phase 1: Fetch
python main.py fetch <org> [--branch=BRANCH]

# Phase 2a: Parse manifests (ODH/RHOAI)
python main.py parse-manifests --platform=<odh|rhoai> [--write-map]

# Phase 2b: Discover components (Ansible/AAP)
python main.py discover-components --platform=NAME --checkouts-dir=PATH

# Phase 3: Generate architectures
python main.py generate-architecture --platform=NAME [--component=PATTERN]

# Phase 4: Collect
python main.py collect-architectures [--platform=NAME]

# Phase 5: Platform summary
python main.py generate-platform-architecture --platform=NAME

# Phase 6: Diagrams
python main.py generate-diagrams --platform=NAME

# All phases
python main.py all --platform=<odh|rhoai> [--branch=BRANCH]
```

## Models

Choose model based on task complexity:
- `opus` (default): Most capable, best for complex analysis
- `sonnet`: Balanced performance/speed, good for discovery
- `haiku`: Fastest, use for simple tasks

```bash
python main.py generate-architecture --platform=aap --model=opus
python main.py discover-components --platform=aap --model=sonnet
```

## Concurrency

Control parallel agent execution:
```bash
python main.py generate-architecture --platform=aap --max-concurrent=10
```

Default is 5 concurrent agents.

## Filtering

Process specific components:
```bash
# Single component
python main.py generate-architecture --platform=aap --component=awx-operator

# Glob pattern
python main.py generate-architecture --platform=aap --component="awx-*"

# Multiple patterns
python main.py generate-architecture --platform=aap \
  --component=awx-operator \
  --component=eda-operator
```

## Output Files

### Per Component
- `checkouts/<org>/<repo>/GENERATED_ARCHITECTURE.md` - Generated summary
- `checkouts/<org>/<repo>/GENERATED_ARCHITECTURE_PROMPT.md` - Prompt used

### Platform Level
- `architecture/<platform>/component-map.json` - Component definitions
- `architecture/<platform>/<component>.md` - Collected architectures
- `architecture/<platform>/PLATFORM.md` - Platform summary
- `architecture/<platform>/diagrams/*.mmd` - Mermaid diagrams
- `architecture/<platform>/diagrams/*.dsl` - C4 diagrams
- `architecture/<platform>/diagrams/*.png` - Rendered images

### Logs
- `logs/discover-components/<platform>.log`
- `logs/generate-architecture/<component>.log`
- `logs/generate-platform-architecture/<platform>.log`
- `logs/generate-diagrams/<platform>-<component>.log`

## Environment

Create `.env` with:
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

## Dependencies

- Python 3.9+
- `claude-agent-sdk`
- `python-dotenv`
- `gh` CLI (for fetching repos)

## Further Reading

- [Component Discovery](./component-discovery.md) - Detailed discovery methods
- [Skill Invocation Patterns](./skill-invocation-patterns.md) - Agent execution approaches
