#!/bin/bash
# Example workflow for using component discovery

# This example shows how to use the new discover-components phase
# for platforms that don't have a central manifest script (like get_all_manifests.sh)

PLATFORM="aap"
CHECKOUTS_DIR="./checkouts/ansible"
ENTRY_REPO="awx-operator"

echo "================================================================================"
echo "Component Discovery Workflow Example"
echo "================================================================================"
echo ""
echo "Platform: $PLATFORM"
echo "Checkouts: $CHECKOUTS_DIR"
echo "Entry point: $ENTRY_REPO"
echo ""

# Phase 1: Fetch repositories (if needed)
# Assuming you already have repos cloned in $CHECKOUTS_DIR

# Phase 2: Discover components via breadcrumb exploration
echo "Phase 2: Discovering components..."
python main.py discover-components \
  --platform="$PLATFORM" \
  --checkouts-dir="$CHECKOUTS_DIR" \
  --entry-repo="$ENTRY_REPO" \
  --model=sonnet

echo ""
echo "✓ Component map written to: architecture/$PLATFORM/component-map.json"
echo ""

# Optional: Review and edit component-map.json
echo "Review the component map:"
echo "  cat architecture/$PLATFORM/component-map.json | jq"
echo ""
echo "Edit if needed to add/remove components manually"
echo ""

# Phase 3: Generate architecture summaries
echo "Phase 3: Generating architecture summaries..."
python main.py generate-architecture \
  --platform="$PLATFORM" \
  --max-concurrent=5 \
  --model=opus

echo ""

# Phase 4: Collect architectures into organized structure
echo "Phase 4: Collecting architectures..."
python main.py collect-architectures \
  --platform="$PLATFORM"

echo ""

# Phase 5: Generate platform-level summary
echo "Phase 5: Generating platform architecture..."
python main.py generate-platform-architecture \
  --platform="$PLATFORM" \
  --model=opus

echo ""

# Phase 6: Generate diagrams
echo "Phase 6: Generating diagrams..."
python main.py generate-diagrams \
  --platform="$PLATFORM" \
  --model=opus

echo ""
echo "================================================================================"
echo "✓ Complete! Check architecture/$PLATFORM/ for results"
echo "================================================================================"
