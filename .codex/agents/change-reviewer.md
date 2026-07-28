---
name: change-reviewer
description: Carry out a comprehensive review of all uncommitted changes and write the findings to planning/REVIEW.md.
---

# Change Reviewer

Run an independent Codex review of the current working tree. Do not review the
changes yourself and do not edit source files as part of this subagent.

Use this command from the repository root:

```bash
codex review --uncommitted "Review all changes since the last commit. Write defect-first findings only, ordered by severity. Include file and line references for every actionable issue. If there are no qualifying findings, say No findings. Mention material test gaps or residual risks." > planning/REVIEW.md
```

After the command completes, report that the review results were written to
`planning/REVIEW.md`.
