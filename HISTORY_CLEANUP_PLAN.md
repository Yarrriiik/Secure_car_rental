# Git History Cleanup Plan

The repository history contains a local `.env` file and IDE metadata. The
current public tree ignores these paths, but removing them from the current
tree does not remove earlier blobs.

The affected paths were found in `master` and `portfolio-hardening`. No tags
were present during this review. Re-scan local and remote refs immediately
before any approved cleanup.

History rewriting is intentionally not performed in this branch. If the
repository is public, rotate every credential that may have appeared in the
old `.env` before following this procedure:

1. Make a fresh `--mirror` clone into an isolated directory.
2. Use `git-filter-repo` with path rules for `.env` and `.idea/`, using
   `--invert-paths` only after reviewing the selected paths.
3. Inspect every rewritten branch and tag with `git log --all --name-only` and
   verify that the sensitive paths no longer exist.
4. Run the test suite from a normal clone of the rewritten repository.
5. Coordinate the force-push with collaborators and invalidate old clones.
6. Create a fresh clone after publication; do not reuse an old working copy.

No credential values are recorded in this plan.
