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
- [Versioning](#versioning)
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
git commit -m "Add feature: description of changes"
```

Write clear commit messages:
- ✅ `Fix: Resolve boundary overlap detection issue`
- ✅ `Feature: Add support for MultiPolygon geometries`
- ❌ `Fixed stuff`

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
├── core/        # Core utilities and shared logic
├── loaders/     # Data loading and preprocessing
├── checks/      # Quality control checks
├── export/      # Pipeline execution and outputs
tests/           # Test suite
```

**Guidelines:**
- Keep changes modular and consistent with the existing architecture
- Place new functionality in the appropriate module
- Update tests alongside code changes

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

⚠️ Pull requests with failing tests will not be merged.

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

---

## License

By contributing, you agree that your contributions will be licensed under the **MIT License**.

---

## Thank You! 🙏

Your contributions help make OVC better for everyone. We appreciate your time and effort in improving this project.

If you have questions, feel free to open an issue or reach out to the maintainers.

**Happy contributing!**
