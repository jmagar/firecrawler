# Suggested Commands for Firecrawl Development

## Build & Development
- `pnpm build` - Build the TypeScript API project
- `pnpm dev` - Run API in development mode with hot reload
- `pnpm start` - Build and start the API server
- `pnpm harness` - Start test harness for running tests

## Testing
- `pnpm harness jest [path]` - Run specific tests with harness
- `pnpm test:snips` - Run end-to-end snips tests
- `pnpm test` - Run tests (excludes e2e_noAuth)
- `pnpm test:full` - Run full test suite
- `npx jest --testPathPattern="pattern"` - Run tests matching pattern

## Code Quality
- `pnpm format` - Format code with Prettier
- `tsc --noEmit` - Type check without building

## Workers & Services
- `pnpm workers` - Start queue workers in watch mode
- `pnpm nuq-worker` - Start NUQ worker in watch mode
- `pnpm index-worker` - Start index worker in watch mode
- `docker-compose up` - Start all services (Redis, PostgreSQL, etc.)

## Configuration
- `pnpm generate-config` - Generate configuration from environment

## Git Commands (Linux)
- `git status` - Check repository status
- `git diff` - View changes
- `git add .` - Stage changes
- `git commit -m "message"` - Commit changes
- `git push` - Push to remote
- `git checkout -b branch-name` - Create new branch

## File System (Linux)
- `ls -la` - List files with details
- `cd directory` - Change directory
- `pwd` - Show current directory
- `find . -name "pattern"` - Find files
- `grep -r "pattern" .` - Search in files
- `cat file` - View file contents

## Package Management
- `pnpm install` - Install dependencies
- `pnpm add package` - Add new package
- `pnpm add -D package` - Add dev dependency

## Docker
- `docker-compose logs service` - View service logs
- `docker-compose restart service` - Restart service
- `docker exec -it container bash` - Shell into container