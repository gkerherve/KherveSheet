# Contributing to KherveSheet

Thank you for your interest in KherveSheet. Contributions of every size are
welcome, including bug reports, new templates, documentation and code.

## Reporting a bug or asking for help

Open an issue at <https://github.com/gkerherve/KherveSheet/issues>. For a
bug, please include:

- your operating system and the KherveSheet version (shown in the title bar);
- what you did, what you expected, and what happened;
- the crash log, if there is one (`khervesheet_crash.log` in your temporary
  folder), and a small `.ksheet` or `.xlsx` that reproduces the problem.

Questions about using KherveSheet are also welcome as issues.

## Contributing code or templates

1. Fork the repository and create a branch from `master`.
2. Set up a development environment:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt pytest
   ```
3. Make your change. Keep each module in `khervesheet/` near 1500 lines and
   split new code into a new module rather than growing a large one. Code
   in `khervesheet/core/` must not import Qt.
4. Add or update tests in `tests/`, and run `pytest tests/`. If you change
   formula behaviour on purpose, regenerate the golden data with
   `KHERVESHEET_WRITE_GOLDEN=1 pytest tests/test_formula_golden.py` and
   explain why in the pull request.
5. Open a pull request describing the change. The test workflow runs on
   every pull request.

New templates go in `examples/` as a `build_<name>.py` script that writes
the `.ksheet`. The existing scripts show the pattern.

## Code of conduct

Please be respectful and constructive. Harassment or abuse of any kind is
not tolerated. Report concerns to the maintainer, Gwilherm Kerherve, through
the email address on his GitHub profile.
