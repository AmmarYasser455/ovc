# Contributing to Overlap Violation Checker (OVC)

Thank you for your interest in contributing to OVC! Contributions are welcome and appreciated, whether they are bug reports, feature suggestions, documentation improvements, or code contributions.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Reporting Bugs](#1-reporting-bugs)
- [Suggesting Features](#2-suggesting-features)
- [Development Workflow](#3-development-workflow)
- [Project Structure](#project-structure)
- [Coding Guidelines](#coding-guidelines)
- [Testing](#testing)
- [Documentation](#documentation)
- [Versioning](#versioning) and [Releasing](#releasing)
- [License](#license)

---

## Code of Conduct

This project follows a simple rule:

- **Be respectful** — Treat all contributors with dignity
- **Be constructive** — Provide helpful feedback and solutions
- **Focus on improving the project** — Keep discussions productive

Harassment, discrimination, or unprofessional behavior will not be tolerated.

---

## How to Contribute

### 1. Reporting Bugs

If you find a bug, please help us by:

- **Verifying reproducibility** — Ensure the bug can be consistently reproduced
- **Checking existing issues** — Avoid creating duplicate reports
- **Opening a detailed issue** with:
- Clear description of the problem
- Steps to reproduce the issue
- Expected vs. actual behavior
- Sample data or code snippets (if applicable)

[Report a bug →](https://github.com/AmmarYasser455/ovc/issues/new)

---

### 2. Suggesting Features

Feature requests are welcome! Please open an issue describing:

- **The problem** you are trying to solve
- **Why the current behavior is insufficient**
- **A proposed solution** or workflow enhancement

We'll discuss the feasibility and prioritization in the issue thread.

[Request a feature →](https://github.com/AmmarYasser455/ovc/issues/new)

---

### 3. Development Workflow

Follow these steps to contribute code:

#### **Step 1: Fork and Clone**

```bash
git clone https://github.com/YOUR_USERNAME/ovc.git
cd ovc
```

#### **Step 2: Create a Branch**

```bash
git checkout -b feature/my-feature
```

Use descriptive branch names:
- `feature/add-road-validation`
- `fix/boundary-check-error`
- `docs/update-installation`

#### **Step 3: Make Your Changes**

- Write clean, modular code
- Follow the [coding guidelines](#coding-guidelines)
- Add tests for new functionality

#### **Step 4: Run Tests**

```bash
pytest
```

Ensure all tests pass before proceeding.

#### **Step 5: Commit Your Changes**

```bash
git commit -m "feat(engine): description of the change"
```

Write clear commit messages in the form `type(scope): summary`, as the history does:
-  `fix(overlap): count every part of a multi-part intersection`
-  `feat(engine): add a sliver check`
-  not `Fixed stuff`

#### **Step 6: Push and Open a Pull Request**

```bash
git push origin feature/my-feature
```

Then open a Pull Request on GitHub with:
- A clear title and description
- Reference to related issues (e.g., `Closes #42`)
- Summary of changes and testing performed

---

## Project Structure

```
ovc/
├── engine/       # Topology engine: overlaps, gaps, input quality, area measurement
├── io/           # Read layers with their FIDs; export findings
├── api.py        # check_file(): read a layer and run the engine
├── app/          # Map app: local server, launcher, browser UI (static/)
├── cli.py        # ovc command
├── sample_data/  # Sample GeoPackage bundled with the app
├── checks/ loaders/ export/ metrics/ core/   # Building QC pipeline
├── precheck/     # GeoQA pre-check
└── road_qc/      # Road network quality checks
packaging/windows/  # OVC.exe build
examples/           # Sample generator, GeoQA -> OVC walkthrough
tests/              # Test suite
```

**Guidelines:**
- Keep changes modular and consistent with the existing architecture ([ARCHITECTURE.md](ARCHITECTURE.md))
- The engine does no file I/O; the app and CLI contain no geometry logic
- Update tests alongside code changes

### Adding a tool to the OVC Toolbox

The toolbox in the app is defined in [`ovc/app/static/toolbox.js`](ovc/app/static/toolbox.js). A tool is one entry in a toolset:

```js
{
  id: "find-slivers",
  name: "Find Slivers",
  summary: "One or two sentences shown at the top of the tool.",
  params: [
    { name: "input", label: "Input Features", type: "layer", geometry: "polygon", required: true, help: "..." },
    { name: "min_overlap_area_m2", label: "Minimum Area (m²)", type: "number", min: 0, step: 0.01, default: 0.01, help: "..." },
  ],
  request: (v) => ({ check_overlaps: true, check_gaps: false, min_overlap_area_m2: v.min_overlap_area_m2 }),
}
```

The Geoprocessing pane builds the form from `params` (types: `layer`, `field`, `crs`, `number`, `bool`) and lists the tool in the tree and on the ribbon's Analysis tab. `request` returns the options passed to the engine, so a tool that needs new behaviour also needs the engine change described in "Adding a check" below. Add the tool to the browser test in `tests/test_gui_workflow.py`.

### Adding a check

A check added to the engine is available to the map app, `ovc check` and the Python API at once. The steps, in order:

1. **Define it.** Write down what counts as a finding, what extra input it needs, and its threshold with units. Add a small fixture with exact expected results to `tests/test_engine.py` first.
2. **Geometry.** Put the pure geometry in a new module in `ovc/engine/` (see `overlaps.py` and `gaps.py`). It takes arrays of geometries in the working CRS and returns findings; no I/O, no mutation of inputs.
3. **Issue type.** Add one line per new issue type to `ISSUE_TYPES` in `ovc/engine/model.py` (check name, label, map colour). The app's legend, filter chips, symbology and the export read it from there.
4. **Wire it.** In `ovc/engine/scan.py`, add a `check_<name>` option to `check_polygons`, a `CheckOutcome` for it, and a block that calls your module and records findings with `finding(...)`. Mark the outcome `incomplete` or `not_run` with a message whenever the result would not cover every feature.
5. **Expose it.** Add the flag to `check_command` in `ovc/cli.py`, the option to `_run_scan` in `ovc/app/server.py`, and a checkbox with a one-sentence explanation of the input it needs in `ovc/app/static/index.html` and `run()` in `app.js`.
6. **Document it.** Add it to "What the checks report" in the README and to `CHANGELOG.md` under Unreleased.

Rules every check follows: a data problem never produces a `clean` status; areas are reported in m² through `Measurement.area_m2`; a finding whose area equals the threshold is reported; every finding carries the source FIDs.

To add a new *interface* (for example a QGIS plugin), call `ovc.check_file()` or `ovc.check_polygons()` and read the `ScanResult`; do not reimplement checks.

---

## Coding Guidelines

- **Follow PEP 8** — Use a linter like `flake8` or `black`
- **Write clear, readable code** — Prioritize simplicity over cleverness
- **Add docstrings** — Document all public functions and classes
- **Avoid breaking changes** — Maintain backward compatibility when possible
- **Keep functions focused** — Each function should do one thing well

**Example:**

```python
def detect_overlaps(buildings: gpd.GeoDataFrame, threshold: float = 0.0) -> gpd.GeoDataFrame:
    """
    Detect overlapping building geometries.

    Parameters:
        buildings (GeoDataFrame): Input building layer
        threshold (float): Minimum overlap area to report (default: 0.0)

    Returns:
        GeoDataFrame: Buildings with detected overlaps
    """
    # Implementation
```

---

## Testing

**All contributions must include tests when applicable.**

- Write unit tests for new functions
- Update existing tests if behavior changes
- Aim for high code coverage

**Run tests:**

```bash
pytest
```

**Run with coverage:**

```bash
pytest --cov=ovc
```

 Pull requests with failing tests will not be merged.

---

## Documentation

If your change affects usage or behavior:

- Update **README.md** for user-facing changes
- Update **ARCHITECTURE.md** for structural changes
- Add inline comments for complex logic

Clear documentation is as important as code quality.

---

## Versioning

OVC follows **[Semantic Versioning](https://semver.org/)** (MAJOR.MINOR.PATCH):

- **Patch releases** (0.0.x) — Bug fixes and minor improvements
- **Minor releases** (0.x.0) — New features, backward compatible
- **Major releases** (x.0.0) — Breaking changes

The version lives in one place, `__version__` in `ovc/__init__.py`. Packaging reads it from there, and the README badge shows the newest tag.

### Releasing

1. Set `__version__` in `ovc/__init__.py`.
2. In `CHANGELOG.md`, rename **Unreleased** to the version and date, and add a new empty **Unreleased** section.
3. Merge to `main` and wait for CI.
4. On GitHub, publish a release with the tag `v<version>` (for example `v3.3.0`).

Publishing the release runs the "Windows app" workflow. It fails if the tag does not match `__version__`; otherwise it builds `OVC.exe` and the installer, installs, runs, upgrades and uninstalls it as a test, and attaches `OVC-Setup.exe`, `OVC-Setup.exe.sha256` and `OVC-windows.zip` to the release.

Keep those asset names unchanged. The download link on the website and in the README (`releases/latest/download/OVC-Setup.exe`) and the in-app update both rely on them. Every installed copy of OVC sees the new release the next time it starts and offers **Install update**.

---

## License

By contributing, you agree that your contributions will be licensed under the **MIT License**.

---

## Thank You!

Your contributions help make OVC better for everyone. We appreciate your time and effort in improving this project.

If you have questions, feel free to open an issue or reach out to the maintainers.

**Happy contributing!**
