---
name: generate-architecture-summaries-batch
description: Auto-discover git repositories in a checkouts directory and generate GENERATED_ARCHITECTURE.md for repos that don't have one. Simple batch processing without platform-specific manifest parsing.
allowed-tools: Read, Write, Bash(git *), Bash(find *), Bash(ls *), Bash(python scripts/get_git_changes.py *), Glob, Grep
---

# Generate Architecture Summaries (Batch)

Automatically discover git repositories in a directory and generate `GENERATED_ARCHITECTURE.md` for each repo that doesn't already have one.

This is a **simple discovery-based** skill - it finds git repos and generates architecture summaries. No platform-specific manifest parsing required.

## When to Use This vs Other Skills

- **Use this skill** (`/generate-architecture-summaries-batch`): When you have a directory of git repos and want to document all of them
- **Use `/analyze-platform-components`**: When you have a platform operator with a component manifest script (e.g., `get_all_manifests.sh`)
- **Use `/repo-to-architecture-summary`**: When you want to analyze a single specific repository

## Arguments

Optional:
- `--checkouts-dir=<path>` (default: ./checkouts)
- `--platform=name` (optional - passed to each repo analysis)
- `--version=X.Y` (optional - passed to each repo analysis)
- `--filter=<pattern>` (optional - only process repos matching pattern)
- `--max-depth=N` (default: 2 - how deep to search for git repos)
- `--force` (regenerate even if GENERATED_ARCHITECTURE.md exists)

Examples:
```bash
# Generate architecture summaries for all repos in ./checkouts
/generate-architecture-summaries-batch

# Specify custom checkouts directory
/generate-architecture-summaries-batch --checkouts-dir=./repos

# Only process repos matching a pattern
/generate-architecture-summaries-batch --filter="component-*"

# Force regenerate even if summaries exist
/generate-architecture-summaries-batch --force

# Provide platform context for all repos
/generate-architecture-summaries-batch --platform=myplatform --version=3.3
```

## Instructions

**CRITICAL**: This skill processes repos SEQUENTIALLY in a single execution context.
- DO NOT use the Task tool
- DO NOT spawn sub-agents or background processes
- DO NOT use parallel processing
- Execute analysis instructions directly in this skill's main loop

### Step 1: Parse Arguments

Extract arguments from the skill invocation:
- `--checkouts-dir=<path>` (default: `./checkouts`)
- `--platform=name` (optional)
- `--version=X.Y` (optional)
- `--filter=<pattern>` (optional)
- `--max-depth=N` (default: 2)
- `--force` (boolean flag, default: false)

### Step 2: Discover Git Repositories

Find all git repositories in the checkouts directory:

```bash
find {checkouts-dir} -maxdepth {max-depth} -name ".git" -type d -exec dirname {} \;
```

This returns a list of directories containing git repositories.

**Example output**:
```
./checkouts/component-a
./checkouts/component-b
./checkouts/platform-org/component-c
```

If no git repos found, output error and stop:
```
⚠️  No git repositories found in {checkouts-dir}

Searched with max-depth={max-depth}

Try:
- Cloning repositories to {checkouts-dir}
- Increasing --max-depth if repos are nested deeper
```

### Step 3: Filter Repositories

Apply filters to the discovered repos:

#### 3a. Filter by Pattern (if --filter provided)

If `--filter` is provided, filter the repo list:
- Simple match: `--filter=component-a` matches directories containing "component-a"
- Glob pattern: `--filter="comp*"` matches "component-a", "component-b", etc.

#### 3b. Check for Existing Architecture Summaries

For each repository, check if `GENERATED_ARCHITECTURE.md` exists:

```bash
ls {repo-path}/GENERATED_ARCHITECTURE.md 2>/dev/null
```

**Decision logic**:
- If file exists AND `--force` is NOT set: Mark repo as "skip"
- If file exists AND `--force` IS set: Mark repo as "regenerate"
- If file does NOT exist: Mark repo as "generate"

### Step 4: Read repo-to-architecture-summary Skill Instructions

Read the skill file to get the complete instructions that will be executed for each repo:

```bash
cat .claude/skills/repo-to-architecture-summary/SKILL.md
```

Extract the `## Instructions` section and all its content. Store this in memory for the loop.

### Step 5: Process Each Repository Sequentially

For each repository (in alphabetical order):

#### 5a. Report Progress

If skipping (default behavior when GENERATED_ARCHITECTURE.md exists):
```
⏭️  Skipping {repo-name} (GENERATED_ARCHITECTURE.md already exists)
```

If regenerating (--force set and GENERATED_ARCHITECTURE.md exists):
```
🔄 Regenerating architecture summary for {repo-name} ({current}/{total})...
   Repository: {repo-path}
```

If generating (no existing GENERATED_ARCHITECTURE.md):
```
🔍 Generating architecture summary for {repo-name} ({current}/{total})...
   Repository: {repo-path}
```

#### 5b. Execute Analysis Instructions

**IMPORTANT**: DO NOT use the Task tool or Skill tool. Execute the instructions directly in this context.

For repositories that need analysis, execute the full `repo-to-architecture-summary` instructions:

**Key substitutions when executing instructions**:
- Repository path: `{repo-path}` (use this as working directory)
- Platform: `--platform` value (if provided)
- Version: `--version` value (if provided), otherwise auto-detect
- Output file: `{repo-path}/GENERATED_ARCHITECTURE.md`

Execute each step of the skill instructions:
1. Parse arguments (use repo-path, platform, version from this skill's context)
2. Navigate to repository: `cd {repo-path}`
3. Prepare repository (check for special cases like operator manifests)
4. Discover repository structure
5. Analyze code artifacts
6. Extract git information using the Python script:
   ```bash
   python scripts/get_git_changes.py {repo-path} --format=metadata --since="3 months ago" --limit=20
   ```
7. Generate GENERATED_ARCHITECTURE.md with structured tables
8. **Write the file** using the Write tool

#### 5c. Report Completion

After completing each repository:
```
✅ Completed {repo-name} ({current}/{total})
   Created: {repo-path}/GENERATED_ARCHITECTURE.md
```

**Then immediately move to the next repository** (if any remain). Do not try to batch, optimize, or parallelize. Process one repo at a time, completely.

### Step 6: Report Final Summary

After processing all repositories, output a summary:

```
================================================================================
✅ Architecture summary generation complete!
================================================================================

Checkouts directory: {checkouts-dir}
Total repositories found: {total_count}
Already had summaries: {skipped_count}
Newly generated: {generated_count}

Repositories processed:
✅ {repo1}
✅ {repo2}
✅ {repo3}
...

Repositories skipped (already had GENERATED_ARCHITECTURE.md):
⏭️  {skipped1}
⏭️  {skipped2}
...

Output location: Each repository's root directory

Next steps:
1. Review generated GENERATED_ARCHITECTURE.md files in each repo
2. Collect architectures: /collect-component-architectures
3. Aggregate platform: /aggregate-platform-architecture --platform={platform} --version={version}
4. Generate diagrams: /generate-component-diagrams
```

## Example Workflow

### Simple Discovery Workflow

```bash
# 1. Clone some repos
git clone https://github.com/org/component-a checkouts/component-a
git clone https://github.com/org/component-b checkouts/component-b
git clone https://github.com/org/component-c checkouts/component-c

# 2. Generate architecture summaries for all repos (auto-discovery)
/generate-architecture-summaries-batch
# Grants Write permission once, then analyzes each repo
# Creates GENERATED_ARCHITECTURE.md in each repo

# 3. Collect and aggregate
/collect-component-architectures
/aggregate-platform-architecture --platform=myplatform --version=1.0
```

### Resumable Workflow

```bash
# Start generation
/generate-architecture-summaries-batch --checkouts-dir=./checkouts

# ... Ctrl-C after 5 repos ...

# Resume later - automatically detects and skips the 5 completed, continues with remaining
/generate-architecture-summaries-batch --checkouts-dir=./checkouts
```

### Platform-Aware Workflow

```bash
# Generate with platform context
/generate-architecture-summaries-batch --platform=myplatform --version=3.3

# All generated summaries will have platform/version metadata
```

## Notes

### Sequential Processing

- Repositories are processed one-by-one (not parallel)
- **Resumable by default**: Automatically skips repos that already have GENERATED_ARCHITECTURE.md
- **Force regeneration**: Use `--force` to regenerate all summaries (even if they exist)
- Can be interrupted (Ctrl-C) and restarted safely
- Progress reported after each repository

### Discovery Mechanism

- Uses `find` to locate `.git` directories
- Default max-depth=2 finds repos like:
  - `./checkouts/component-a/.git` → `./checkouts/component-a`
  - `./checkouts/org/component-b/.git` → `./checkouts/org/component-b`
- Increase `--max-depth` if your repos are nested deeper

### Filtering

- `--filter` supports simple string matching or glob patterns
- Applied to the repository directory name (not full path)
- Case-sensitive matching

### Permission Handling

- **User grants Write permission ONCE** at the start of the skill
- No additional permission prompts during execution
- Much simpler than granting permission N times (one per repo)

### Autonomous Operation

- No user input required during generation
- Each repository analyzed in isolation
- Failures in one repo don't stop others
- **Main skill executes instructions directly** (no sub-agents needed)

### Output Location

Each repository analysis creates `GENERATED_ARCHITECTURE.md` in its root directory:
```
checkouts/
├── component-a/
│   ├── .git/
│   └── GENERATED_ARCHITECTURE.md        ← Created by skill
├── component-b/
│   ├── .git/
│   └── GENERATED_ARCHITECTURE.md        ← Created by skill
└── platform-org/
    └── component-c/
        ├── .git/
        └── GENERATED_ARCHITECTURE.md    ← Created by skill
```

Run `/collect-component-architectures` to organize these into `architecture/{platform}-{version}/`.

### Resource Usage

- Sequential processing (one repo at a time)
- Lower resource usage than parallel approach
- Can run in background while you do other work
- Use `--filter` for analyzing specific repos only

### Error Handling

- Each repository processed independently
- If one repo fails, skill continues with next repo
- Failed repos can be re-analyzed by deleting their `GENERATED_ARCHITECTURE.md` and re-running the skill
- Or analyze specific failed repos manually:
  ```bash
  /repo-to-architecture-summary checkouts/component-a
  ```
- Progress is preserved - can resume after fixing issues

## Comparison with Other Skills

| Skill | Discovery Method | Platform-Aware | Use Case |
|-------|-----------------|----------------|----------|
| `/repo-to-architecture-summary` | Manual (single repo) | Optional | Deep-dive one component |
| `/generate-architecture-summaries-batch` | **Auto (find git repos)** | Optional | Document all repos in a directory |
| `/analyze-platform-components` | Manifest parsing | Yes | Platform with component manifest |

### Manual (repo-by-repo):
```bash
/repo-to-architecture-summary checkouts/component-a
# Grant Write permission...
# Wait for completion...
/repo-to-architecture-summary checkouts/component-b
# Grant Write permission again...
# Wait for completion...
# ... repeat N more times (N total permission grants!) ...
```

### Automated (this skill):
```bash
/generate-architecture-summaries-batch
# Grant Write permission ONCE
# Analyzes all N repos sequentially
# Can Ctrl-C and resume later
# Skips already-completed repos automatically
```

**Key Benefits**:
- ✅ One permission grant vs N
- ✅ Resumable (Ctrl-C safe)
- ✅ Automatic git repo discovery
- ✅ Progress tracking
- ✅ No platform manifest required
- ✅ No babysitting required
