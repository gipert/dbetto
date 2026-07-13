## Testing

- `nox -s tests` runs the test suite.
- `nox -s docs --non-interactive` builds the docs.
- `nox -s lint` runs the pre-commit hooks; `nox -s pylint` runs PyLint (CI runs
  both). Bare `nox` runs lint + pylint + tests. Note: mypy is manual-stage and
  not run by `nox -s lint`.

## Submitting a Pull Request

Make sure to include a concise description of the changes and link the relevant
pull requests or issues.
