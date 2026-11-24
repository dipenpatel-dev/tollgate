# Contributing

Thanks for helping. Please read the [Code of Conduct](CODE_OF_CONDUCT.md) first.

## Before you start

- For anything bigger than a small fix, open an issue first so we can agree on the approach.
- Security problems do not go in issues. Follow [SECURITY.md](SECURITY.md).
- Use synthetic data only. Never put real PHI, PII or credentials in code, tests, issues or pull requests.

## Making a change

1. Fork the repo and branch from `main`.
2. Keep the change small and focused on one thing.
3. Add or update tests. Hooks are tested in `tests/hooks`, the installer in `tests/installer`.
4. Run the tests the same way CI does (see `.github/workflows/tests.yml`), for example:

   ```
   bash tests/hooks/run.sh
   python3 -m unittest discover -s tests/hooks -p 'test_*.py'
   bash tests/installer/run.sh
   ```

5. Update the docs in `docs/` if behavior changes.
6. Open a pull request against `main` and fill in the template.

## Guidelines

- Pick the simplest approach that solves the problem.
- A hook that fails to start must block the action, not let it through.
- Do not add a new dependency without saying why an existing one cannot do the job.
