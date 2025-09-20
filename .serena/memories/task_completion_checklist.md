# Task Completion Checklist

When completing any development task in Firecrawl, follow these steps:

## Before Starting
1. Read relevant existing code to understand patterns
2. Check neighboring files for conventions
3. Look for existing utilities/components to extend

## During Development
1. Write E2E tests first if implementing new features
   - Happy path test(s)
   - Failure path test(s)
   - Gate tests appropriately for dependencies
2. Implement code following existing patterns
3. Use proper types (never `any`)
4. Throw errors early, no silent failures
5. Don't add comments unless requested

## After Implementation
1. Run type checking: `tsc --noEmit`
2. Format code: `pnpm format`
3. Run relevant tests: `pnpm harness jest [test-path]`
4. Verify tests pass locally
5. Check for any linting issues

## Before Committing
1. Review all changes with `git diff`
2. Ensure no secrets/keys in code
3. Verify imports are organized properly
4. Check that error handling is comprehensive
5. Confirm following existing patterns

## Testing Requirements
- E2E tests (snips) preferred over unit tests
- Use `scrapeTimeout` from `./lib` for timeouts
- Gate tests based on requirements:
  - Fire-engine: `!process.env.TEST_SUITE_SELF_HOSTED`
  - AI features: Check for API keys

## Quality Checks
- No `any` types used
- Proper error propagation
- Following file naming conventions
- Matching existing code style
- Using existing libraries/utilities

## Final Steps
1. Stage changes: `git add .`
2. Create descriptive commit message
3. Push to feature branch
4. Open PR for CI validation
5. Let CI run full test suite

## MCP Development Specific
For MCP server changes (apps/firecrawler):
1. Ensure async/Context signatures
2. Use MCP-specific exceptions
3. Add comprehensive metadata
4. Test with MCP clients
5. Update module documentation if needed