---
name: doc-review
description: Review documentation or planning files and append a feedback section with questions, clarifications, simplification opportunities, and actionable review notes. Use when the user asks to review a planning document, documentation draft, spec, proposal, README, or named file and add review feedback directly to the document.
---

# Doc Review

## Overview

Review the target document as an editor and implementation partner. Append a new section at the end of the file containing the review feedback, rather than replacing or rewriting the existing document.

## Workflow

1. Identify the target file from the user request.
   - If the user provides a path, use that path.
   - If the user provides only a filename or title, first look in likely planning or documentation folders such as `planning/`, `plans/`, `docs/`, `doc/`, `.codex/plans/`, and the repository root.
   - If multiple plausible files match, ask for the exact target.

2. Read the full document before editing.
   - Preserve the existing content, structure, formatting, and frontmatter.
   - Notice unclear goals, unsupported assumptions, missing edge cases, duplicated work, sequencing risks, and opportunities to simplify.

3. Append one new section at the end of the document.
   - Use a heading level consistent with the document. If unclear, use `## Review Notes`.
   - Include concise bullets grouped under useful labels such as `Questions`, `Clarifications`, `Feedback`, and `Opportunities to Simplify`.
   - Prefer specific, actionable notes tied to the document's content.
   - Avoid broad praise, generic style advice, or speculative concerns that do not affect the plan.

4. Verify the edit.
   - Re-open the changed tail of the file and confirm the new section was appended once.
   - In the final response, name the edited file and summarize the categories of feedback added.

## Review Style

Be direct and concrete. Frame questions so the document owner can answer them or use them to revise the plan. When suggesting simplification, identify what can be removed, combined, deferred, or made more explicit.

## Example Section

```markdown
## Review Notes

### Questions
- What decision does this plan need to enable, and who is the decision maker?

### Clarifications
- Define the expected output format before implementation starts.

### Opportunities to Simplify
- Combine the setup and validation steps if they always happen together.

### Feedback
- Add acceptance criteria for the highest-risk workflow.
```
