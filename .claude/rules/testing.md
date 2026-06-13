# Testing Rules

## Test Framework
- Use **Vitest** for unit and integration tests
- Use **Playwright** for end-to-end browser tests
- Test files live next to source files: `feature.js` → `feature.test.js`

## Coverage Requirements
- Minimum 80% line coverage for new code
- 100% coverage for utility/helper functions
- All public API functions must have tests

## Test Structure
- Use `describe` blocks to group related tests
- Use clear, descriptive test names: `it('should return empty array when no data exists')`
- Follow Arrange-Act-Assert (AAA) pattern
- Each test should test one thing only

## What to Test
- ✅ Business logic and data transformations
- ✅ Edge cases (empty inputs, null values, boundary conditions)
- ✅ Error handling paths
- ✅ Local storage read/write operations
- ✅ Offline/online state transitions
- ❌ Don't test framework internals
- ❌ Don't test trivial getters/setters

## Mocking
- Mock external APIs and network calls
- Mock file system operations in unit tests
- Use real implementations for integration tests
- Never mock the module under test

## Running Tests
```bash
npm test              # Run all tests
npm test -- --watch   # Watch mode
npm run test:e2e      # End-to-end tests
npm run test:coverage # Coverage report
```
