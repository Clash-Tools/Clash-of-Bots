# Contributing

Thanks for helping. Before you start:

1. Read the [hard rules](docs/RULES.md). Pull requests that break one are not merged.
2. Open or pick an issue first for anything bigger than a small fix, so the approach can be agreed.
3. Set up: `uv sync --python 3.13`, then `git config core.hooksPath .githooks` (ruff and the tests run
   before every push).
4. Work on a branch, write Conventional Commit messages (`fix(attack): ...`, `feat(ui): ...`), and open a
   pull request that says what changed, how it was tested, and whether it ran live on a device.
5. A feature that is not finished or not checked live yet goes behind a feature flag
   ([docs/FEATURE_FLAGS.md](docs/FEATURE_FLAGS.md)) with its issue on the project board.
6. New screenshots for tests: run `python scripts/anonymize_fixtures.py <file>` first and check that no
   player, clan or opponent name can be read.

By contributing you agree that your work is published under the project's [GPL-3.0 licence](LICENSE).
