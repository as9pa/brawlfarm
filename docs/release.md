# Releasing brawlfarm

A release is a GitHub release with a `vX.Y.Z` tag. Publishing it runs `.github/workflows/release.yml`, which builds the wheel on Windows and uploads it to PyPI with trusted publishing, so there is no API token anywhere in the repository or in the repository secrets.

## One time: register the pending publisher on PyPI

PyPI has to be told which workflow is allowed to publish the project before the first release, otherwise the publish job fails with an OIDC error and nothing reaches PyPI.

Sign in at [pypi.org](https://pypi.org/), open Your account, Publishing, and add a new pending publisher for GitHub with these four values:

- PyPI project name: `brawlfarm`
- Owner: `as9pa`
- Repository name: `brawlfarm`
- Workflow name: `release.yml`
- Environment name: `pypi`

The environment name matters: the publish job runs in a GitHub environment called `pypi`, and PyPI rejects the token if the two do not agree. Create that environment under the repository's Settings, Environments if it does not exist yet. Once the first release has been published the pending publisher becomes a normal publisher and this step is done forever.

## Every release

1. Bump the version in three places, which have to agree: `version` in `pyproject.toml`, `__version__` in `brawlfarm/__init__.py` and `version` in `brawlfarm/web/package.json`. The panel's About page and `brawlfarm --version` both read the Python one, the release workflow compares the `pyproject.toml` one against the tag.
2. Run the checks the way CI does: `uv run ruff check .`, `uv run ruff format --check .`, `uv run python tools/scrub_check.py`, `uv run pytest -q`, and `pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web typecheck`.
3. Commit the bump and get it onto `main`.
4. Tag and release in one step:

```
gh release create v1.1.0 --generate-notes
```

`--generate-notes` writes the notes from the merged pull requests since the last tag. Edit them afterwards if the generated list is not the story you want to tell.

5. Watch the run with `gh run watch`. The build job fails loudly if the wheel version does not match the tag, if the built panel is missing from the wheel, or if the wheel carries the TypeScript sources.

## What the workflow does

The build job runs on `windows-latest` so the wheel is built the same way a contributor builds it: `pnpm install --frozen-lockfile` and `pnpm build` in `brawlfarm/web` produce `brawlfarm/web/dist`, which hatchling then pulls into the wheel as an artifact, and `uv build --wheel` writes it to `dist/`. The wheel is pure Python and platform independent, so a single build is enough.

The publish job downloads that artifact and hands it to `pypa/gh-action-pypi-publish`. It needs `id-token: write` to mint the OIDC token PyPI trades for an upload token, and it runs in the `pypi` environment, which is the other half of what the pending publisher was registered against.

## If a release goes wrong

PyPI does not allow reuploading a version, even after a delete. Bump to the next patch version, make a new tag and release, and yank the broken version on PyPI so installers stop resolving to it.
