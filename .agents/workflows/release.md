---
description: How to create a new release of the ENTSO-E Ceny Energii HACS integration
---

# Release Workflow — ENTSO-E Ceny Energii

## Prerequisites
- All changes committed and pushed to `main`
- Tests passing (CI auto-validates on push)
- Working directory: `/Users/grzegorzciupek/Downloads/Programowanie/entsoe-e`

## Steps

### 1. Decide version bump type
- `patch` — bugfixes, minor tweaks (1.0.0 → 1.0.1)
- `minor` — new features, sensors, config options (1.0.0 → 1.1.0)
- `major` — breaking changes, config migration needed (1.0.0 → 2.0.0)

### 2. Bump version in manifest.json
// turbo
```bash
python3 scripts/bump_version.py <patch|minor|major|X.Y.Z>
```

The script updates `custom_components/entsoe_prices/manifest.json` automatically.

### 3. Commit the version bump
```bash
git add custom_components/entsoe_prices/manifest.json
git commit -m "Bump version to $(python3 -c "import json; print(json.load(open('custom_components/entsoe_prices/manifest.json'))['version'])")"
```

### 4. Create and push the tag
```bash
VERSION=$(python3 -c "import json; print(json.load(open('custom_components/entsoe_prices/manifest.json'))['version'])")
git tag "v${VERSION}"
git push origin main --tags
```

### 5. Verify release
The GitHub Actions workflow `.github/workflows/release.yml` will automatically:
1. Verify manifest.json version matches the tag
2. Create a zip archive of the integration
3. Create a GitHub Release with release notes

Check: `https://github.com/GregECAT/entsoe-e/releases`

## How HACS detects updates
HACS compares `version` in `manifest.json` (on the default branch) against the latest GitHub release tag. When they differ, HACS shows an update notification to the user.

## Important files
| File | Purpose |
|------|---------|
| `custom_components/entsoe_prices/manifest.json` | Contains `version` — HACS reads this |
| `hacs.json` | HACS metadata (min HA version, country) |
| `.github/workflows/release.yml` | Auto-creates GitHub Release on tag push |
| `.github/workflows/validate.yml` | CI — runs tests on push/PR |
| `scripts/bump_version.py` | Version bump helper script |
