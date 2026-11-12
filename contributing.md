# Contributing

See the [README](README.md) for user-facing requirements and usage.

## Publishing

The `release.yml` workflow is restricted to `vipwolf/python-lacrosse`.
Pushes to `main` and `develop` build and publish to TestPyPI. Pull requests,
other branches, and manual runs do not trigger it. Pushing a canonical
`X.Y.Z` tag, optionally followed by `aN`, `bN`, or `rcN`, publishes only
to PyPI, after environment approval. For example, use `1.0.0a1`, `1.0.0b1`,
or `1.0.0rc1` for prereleases; spellings such as `1.0.0alpha1` are rejected
to keep tags identical to the published version. The tagged
commit must be in `main` history. Lightweight and annotated tags are
supported; prefixes such as `v` and leading zeroes are rejected.

Branch builds increment the patch component of the highest canonical final `X.Y.Z`
tag reachable from the commit and append `.dev<run_id>`. For example, after
`0.5.0`, run `123` publishes `0.5.1.dev123` to TestPyPI. A reachable
canonical final release tag is required; prerelease tags are ignored for branch
versioning. Git hash suffixes are omitted because
PyPI and TestPyPI do not accept local version identifiers.
New runs have distinct versions; reruns retain the same version and cannot
republish distributions already uploaded successfully. Push a new commit
to publish another development version. Release versions come from the
existing Hatch VCS configuration and must match the tag exactly.
Reuploading a PyPI version fails instead of skipping files.
Artifacts expire after seven days; monitor TestPyPI's project storage quota.

### GitHub Release Setup

Naming an environment in YAML does not configure its protection rules. To make
sure we have configured the environment protection rules correctly check:

1. Verify ownership of `pylacrosse` on both indexes. Owning this GitHub fork
   does not grant ownership of the upstream PyPI project. An existing project
   owner must authorize the publisher; pending publishers only work for an
   available project name.
2. Under GitHub **Settings > Environments**, ensure `pypi` exists with the
   following settings:
   **Required reviewers**, select a trusted maintainer, enable **Prevent
   self-review**, and disable administrator bypass. Under **Deployment
   branches and tags**, select **Selected branches and tags** and allow only
   tags matching `[0-9]*.[0-9]*.[0-9]*`. The workflow additionally enforces
   exact syntax and ancestry. Independent review needs a second maintainer;
   do not silently disable this control for a solo release.
3. Ensure `testpypi` environment exists without required approval. Allow only
   the branch refs `main` and `develop`, with no permitted tag refs. Neither environment
   needs secrets. Required-reviewer availability for private repositories
   depends on the GitHub plan; confirm support before activation.
4. On each index, open the project's **Publishing** settings and add a GitHub
   Trusted Publisher: owner `vipwolf`, repository `python-lacrosse`,
   workflow filename `release.yml`, and environment `pypi` or `testpypi`
   respectively. Use pending publishers only for new projects. Remove and
   revoke old publishing tokens after migrating.
5. Under **Settings > Rules > Rulesets**, activate rules for `main` and
   `develop` requiring pull requests and independent review, dismissing
   stale approvals, and preventing force pushes and deletion. Avoid broad
   bot/admin bypass. Do not require this publishing workflow as a PR check:
   it does not run on PRs. Require maintainer review of workflows, dependency
   locks, build hooks, and package changes; configure code ownership with your
   actual reviewers.
6. Create a tag ruleset for `[0-9]*.[0-9]*.[0-9]*` restricting creation,
   with only release maintainers on its bypass list. Separately create an
   immutable-tag ruleset with no bypass, restricting updates and deletions
   and blocking force pushes. This permits creation without replacement.
7. Keep the default GitHub token read-only, disable Actions creating or
   approving PRs, and restrict allowed actions to reviewed immutable refs.
   Use MFA/passkeys, review app and personal-token access, and review Trusted
   Publishers when offboarding maintainers.

### Release Verification

First verify an authorized branch push on TestPyPI: inspect both distributions,
the version, and PEP 740 attestations. For an actual release, push an unused
`X.Y.Z` tag (or a canonical prerelease tag) on `main` history.
Under **Actions > workflow run > Review deployments**, check the commit and
artifacts before approving `pypi`.
Do not publish fake production versions to test authentication.

Builds and installed-wheel tests run in an unprivileged job. Publishing jobs
only download this run's artifact by ID and invoke the official PyPA container
using short-lived OIDC authentication. They do not check out code or install
the package. The Linux/amd64 publisher image is pinned by manifest digest from
PyPA's `v1.14.3` image tag, instead of using the standard wrapper's mutable
container tag. All input defaults are explicit; attestations and metadata
checks are enabled, duplicates are fatal, and verbose debugging is disabled.

### Maintaining Dependencies

The release environment uses Python 3.11 and the `release` dependency group
in `pyproject.toml`, resolved with package hashes in `uv.lock`. The workflow
pins both the setup-uv action commit and the uv archive checksum, and disables
shared caches. Use a reviewed `uv` installation to update release dependencies:

```shell
uv lock --upgrade-group release --default-index https://pypi.org/simple
```

Review changed versions, hashes, and security advisories. Synchronize with:

```shell
uv sync --locked --no-default-groups --group release --no-install-project --no-build --python 3.11
```

This installs only locked wheels, not the project. Build using:

```shell
uv build --no-build-isolation --python <environment>/bin/python --no-create-gitignore
```

This ensures build backends come from that locked environment.
Do not add a TestPyPI extra index or let isolation resolve unpinned backends.
Check distributions with `python -m twine check --strict dist/*` and test
the wheel outside the checkout, installing it with `uv pip install --no-deps --no-index`
into the same environment. Updating uv also requires reviewing
and changing its version and archive checksum together in the workflow.

Dependabot proposes weekly action updates without automatic merges. Review
upstream commits and source. After action changes, regenerate
`.github/workflows/actions.lock` using the official, reviewed
`github/gh-actions-lock` extension and `gh actions-lock`. Never hand-edit
the generated lock. The generator rewrites action references to version tags;
restore the corresponding reviewed full commit SHAs in the workflow afterward
to retain explicit pins as well. Check with `gh actions-lock --verify` and
`gh actions-lock --verify-local`. These accept explicit SHAs with a warning
that the generator prefers tag references. Generation and online verification
require GitHub authentication. The action lock does not pin runner images,
Python runtime downloads, or container images.

Update the `docker://` publisher digest manually in both publishing steps.
Resolve the official `ghcr.io/pypa/gh-action-pypi-publish` release image,
inspect source/platform metadata, and verify its manifest digest. Never resolve
a mutable image tag during a release. Verify updates through TestPyPI first.

After changes, run `python -m pytest`,
`actionlint .github/workflows/release.yml`, and
`zizmor .github/workflows/release.yml`. Policy tests cover rejected events,
forks, tag syntax and ancestry, checkout identity, and development retries.

This follows the [PyPA publishing guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
and addresses mutable dependencies, privileged untrusted builds, shell injection,
and stolen maintainer credentials highlighted in the
[2026 workflow attack report](https://www.stepsecurity.io/blog/hackerbot-claw-github-actions-exploitation)
and [WFX incident report](https://www.stepsecurity.io/blog/wfx-phantom-the-github-actions-secret-stealer).
Pins establish integrity, not benign content; attestations identify publishers,
not whether code is malware-free. Compromised approvers, trusted dependencies,
or GitHub/PyPI services remain risks. This workflow does not claim reproducible
runner images or network egress enforcement.
