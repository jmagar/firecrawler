# Code Style and Conventions

## TypeScript/JavaScript Conventions

### TypeScript Configuration
- Target: ES2022
- Module: NodeNext
- Strict null checks enabled
- Source maps enabled
- Root directory: `./src`
- Output: `./dist/src`

### Code Style (Prettier)
- Tab width: 2 spaces
- No tabs (spaces only)
- Semicolons: always
- Quotes: double quotes
- Print width: 80 characters
- Trailing commas: all
- Arrow parens: avoid when possible
- Bracket spacing: true
- End of line: LF

### Naming Conventions
- Files: kebab-case (e.g., `queue-service.ts`)
- Classes: PascalCase
- Interfaces/Types: PascalCase
- Functions/Methods: camelCase
- Constants: UPPER_SNAKE_CASE
- Private members: prefix with underscore

### Type Safety Rules
- **NEVER use `any` type** - always use proper types
- Look up actual types rather than guessing
- Use strict null checks
- Define interfaces for complex objects
- Use type imports when needed

### Error Handling
- **Throw errors early and often**
- No silent failures or fallbacks
- Clear error messages
- Use try-catch for async operations
- Propagate errors up the stack

### Import Organization
- Group imports by type (external, internal, types)
- Use absolute imports where configured
- Import types separately when possible

## Python Conventions (MCP Server)

### Python Version
- Requires Python 3.11+
- Use modern type hints: `dict[str, Any]` not `Dict[str, Any]`
- Async/await patterns for MCP functions

### FastMCP Patterns
- All MCP functions must be async
- Include Context parameter in signatures
- Use MCP-specific exceptions (ToolError, ResourceError)
- Add comprehensive metadata for all components

### Error Handling
- Use structured logging via Context
- Raise appropriate MCP exceptions
- Include detailed error messages
- Handle edge cases explicitly

## General Rules

### Comments
- **DO NOT add comments unless explicitly requested**
- Code should be self-documenting
- Use meaningful variable/function names

### File Management
- **Always prefer editing existing files over creating new ones**
- Never create documentation files unless requested
- Extend existing patterns before creating new ones

### Testing
- Write E2E tests first (called "snips")
- Gate tests appropriately:
  - Fire-engine required: `!process.env.TEST_SUITE_SELF_HOSTED`
  - AI required: Check for API keys
- Use `scrapeTimeout` from `./lib` for timeouts

### Pre-production Notes
- It's okay to break code when refactoring
- No fallbacks - fail fast
- Focus on correctness over backwards compatibility during development