---
name: collect-component-architectures
description: Collect and organize GENERATED_ARCHITECTURE.md files from checkouts into a structured architecture directory by platform, version, and component name.
allowed-tools: Bash(python *)
---

# Collect Component Architectures

Collect `GENERATED_ARCHITECTURE.md` files from repository checkouts and organize them into a structured directory hierarchy: `./architecture/$PLATFORM-$VERSION/$COMPONENTNAME.md`

## Arguments

Optional arguments:
- `--checkouts-dir=<path>` (default: ./checkouts)
- `--output-dir=<path>` (default: ./architecture)

Examples:
```bash
/collect-component-architectures                                      # collect all from default locations
/collect-component-architectures --checkouts-dir=./repos --output-dir=./docs/arch
```

## Platform and Version Detection

This skill uses a robust Python script to handle all collection logic.

**Platform is determined by checkout directory structure**:
- Configure your checkout structure with platform-specific organization directories
- Example: `checkouts/platform-org/*` → platform components
- The script can be configured to recognize your platform's organization structure

**Version is derived from operator repositories** (priority order):
1. **Makefile** `VERSION` variable (primary - developer intent)
2. **VERSION** or **version.txt** file
3. **Git describe** (fallback only)
4. **"unknown"** if all fail

All components in a platform's checkout inherit that platform's version from the operator.

## Instructions

This skill uses a Python script (`scripts/collect_architectures.py`) to handle all the collection logic robustly.

### Step 1: Parse Arguments

Extract arguments from the skill invocation:
- `--checkouts-dir=<path>` (default: ./checkouts)
- `--output-dir=<path>` (default: ./architecture)

### Step 2: Run Python Collection Script

Execute the Python script with the parsed arguments:

```bash
python scripts/collect_architectures.py --checkouts-dir={checkouts-dir} --output-dir={output-dir}
```

The script will:
1. Detect platform checkouts based on configured organization directories
2. Determine platform versions from operator repositories (Makefile → VERSION file → git describe)
3. Find all `GENERATED_ARCHITECTURE.md` files in each platform checkout
4. Copy files to `{output-dir}/{platform}-{version}/{component}.md`
5. Create index README.md files for each platform-version directory
6. Print a detailed summary report

### Step 3: Display Results

The Python script outputs its own summary. Simply let it run and display the output to the user.

The script returns:
- Exit code 0 if successful (at least one platform processed)
- Exit code 1 if no platforms found or error

### Example Output

```
Detecting platform version from checkouts/platform-org/platform-operator
  ✓ Found version in Makefile: 3.3.0

Found 1 platform(s):
  - myplatform 3.3.0

Processing myplatform 3.3.0...
  Output directory: architecture/myplatform-3.3.0
  Found 5 component(s)
    ✓ component-a.md
    ✓ component-b.md
    ✓ component-c.md
    ...
  Created index: architecture/myplatform-3.3.0/README.md

================================================================================
✅ Component architectures collected!
================================================================================

Checkouts directory: checkouts
Output directory: architecture

Platform versions detected:
  - myplatform: 3.3.0 (5 components)

Components collected: 5

Directory structure created:
  - architecture/myplatform-3.3.0/
      README.md
      component-a.md
      component-b.md
      component-c.md
      ...

Next steps:
  1. Review collected architectures in architecture/
  2. Generate platform-level view: /aggregate-platform-architecture --platform=myplatform --version=3.3.0
  3. Generate diagrams: /generate-architecture-diagrams --architecture=architecture/myplatform-3.3.0/component-a.md
```

## Notes

### Why Python?

The original bash-based version detection was fragile with multiple fallback paths. The Python script provides:
- Robust version detection with clear priority handling
- Better error handling and reporting
- Easier to test and maintain
- Consistent behavior across environments

### Recommended Workflow

1. **Generate component architectures**: Run `/repo-to-architecture-summary` on each component repository
2. **Organize files**: Run this skill to collect into `architecture/{platform}-{version}/` structure
3. **Aggregate**: Run `/aggregate-platform-architecture` to create platform-level view

### What Gets Created

```
architecture/
├── platform-3.3.0/
│   ├── README.md              # Index of all platform 3.3.0 components
│   ├── component-a.md         # Individual component architectures
│   ├── component-b.md
│   └── component-c.md
└── platform-2.19/
    ├── README.md              # Index of all platform 2.19 components
    ├── component-a.md
    └── component-b.md
```

### Version Detection Details

The Python script implements this priority order:
1. **Makefile**: `VERSION = 3.3.0` (most authoritative - developer intent)
2. **VERSION file**: Plain text version number
3. **git describe --tags --always**: Current checkout state
   - Strips 'v' prefix automatically
   - Handles tag+offset format (e.g., "v2.8.0-1325-gfa1fcdc0")
4. **Fallback**: "unknown" if all methods fail

This ensures reliable version detection even on development branches where git tags may not reflect the intended version.
