# /review — Code Review Command

Review the current staged changes or a specified file for:

## Checklist
1. **Code Quality**: Check for code smells, duplication, and complexity
2. **Style Compliance**: Verify adherence to rules in `.claude/rules/code-style.md`
3. **Testing**: Ensure adequate test coverage per `.claude/rules/testing.md`
4. **Security**: Flag any hardcoded secrets, unsafe inputs, or exposed ports
5. **Performance**: Identify potential bottlenecks or memory leaks
6. **Accessibility**: Check for proper ARIA labels and semantic HTML
7. **Offline Compatibility**: Ensure features work without network connectivity

## Output Format
Provide findings as a structured report:
- 🔴 **Critical** — Must fix before merge
- 🟡 **Warning** — Should fix, but not blocking
- 🟢 **Suggestion** — Nice-to-have improvements
- ✅ **Passed** — Areas that look good

## Usage
```
/review                    # Review staged changes
/review src/data-store.js  # Review specific file
```
