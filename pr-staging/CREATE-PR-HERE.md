# Create the PR from this folder

Ready-to-push branch: `qwen/new-suggestions-expansion-ideas` (2 commits on top of `origin/main` @ 36911ab)
- `0203bc7` — Add "new qwen suggestions" folder (5 docs, 565 insertions, docs-only)
- `ce81514` — adds `pr-body-for-branch.md` (this PR's description as a file so it survives push; delete before merge or drop this commit)

## Option A — push + create PR with gh CLI (needs your GitHub auth)
```bash
cd /workspace/pr-staging/wt        # branch already checked out here
git push https://github.com/sr104696/Claudey.git qwen/new-suggestions-expansion-ideas
gh pr create --repo sr104696/Claudey \
  --base main --head qwen/new-suggestions-expansion-ideas \
  --title 'Add "new qwen suggestions" folder: wider role/posting discovery ideas' \
  --body-file pr-body-for-branch.md
```

## Option B — no gh? Open the compare URL after pushing:
https://github.com/sr104696/Claudey/compare/main...qwen/new-suggestions-expansion-ideas?expand=1

## Option C — if the sandbox checkout was reset (worktree gone): import the bundle
```bash
git fetch /workspace/pr-staging/qwen-expansion-ideas.bundle \
  qwen/new-suggestions-expansion-ideas:qwen/new-suggestions-expansion-ideas
# then Option A's push command from the main repo
```

## Why the branch was rebuilt on origin/main
The sandbox checkout's base predated several merged PRs; pushing it directly would have made the diff appear to revert them. This branch contains ONLY the new folder (+ the throwaway pr-body commit). Note: run_log shows PR #4 for this content existed previously — that attempt had the bad-diff problem above.
