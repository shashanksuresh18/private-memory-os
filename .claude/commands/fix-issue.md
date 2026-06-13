# /fix-issue — Issue Diagnosis & Fix Command

Diagnose and fix a reported issue using a systematic approach.

## Workflow

### Step 1: Understand
- Read the issue description or error message
- Identify the affected component(s)
- Reproduce the issue if possible

### Step 2: Diagnose
- Search for related code using grep/search tools
- Check recent git history for relevant changes
- Identify root cause vs. symptoms

### Step 3: Fix
- Implement the minimal fix that resolves the root cause
- Ensure the fix doesn't introduce regressions
- Follow code style rules in `.claude/rules/code-style.md`

### Step 4: Verify
- Write or update tests to cover the fix
- Run existing tests to confirm no regressions
- Test offline behavior if the fix touches network code

### Step 5: Document
- Add a clear commit message explaining the fix
- Update any affected documentation
- Note any follow-up work needed

## Usage
```
/fix-issue "Data doesn't sync after reconnecting to network"
/fix-issue #42   # Reference a GitHub issue number
```
