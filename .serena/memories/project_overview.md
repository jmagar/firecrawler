# Firecrawl Project Overview

## Project Purpose
Firecrawl is a web scraping and crawling API service that converts websites into clean, LLM-ready data. It provides:
- URL scraping with markdown/structured data output
- Website crawling with subpage discovery
- Advanced data extraction capabilities
- Support for dynamic content, PDFs, images
- Anti-bot mechanism handling
- Vector search capabilities (self-hosted)

## Tech Stack

### Backend (Primary: apps/api)
- **Language**: TypeScript/Node.js 
- **Runtime**: Node.js with TypeScript
- **Build Tools**: pnpm, tsc, tsx
- **Testing**: Jest
- **Queue/Workers**: Custom queue service with NUQ workers
- **Database**: PostgreSQL (via nuq-postgres), Redis
- **Deployment**: Docker Compose

### MCP Server (apps/firecrawler)
- **Language**: Python 3.11+
- **Framework**: FastMCP for Model Context Protocol
- **Dependencies**: firecrawl-py SDK, pydantic, httpx
- **Purpose**: Expose Firecrawl API to LLM clients

### SDKs
- JavaScript/TypeScript SDK (apps/js-sdk)
- Python SDK (apps/python-sdk)

### UI Components
- Ingestion UI (apps/ui/ingestion-ui)

## Repository Structure
- Monorepo architecture with multiple apps
- Main API: `apps/api/`
- MCP server: `apps/firecrawler/`
- SDKs: `apps/js-sdk/`, `apps/python-sdk/`
- Testing: `apps/test-suite/`
- Services: Redis, PostgreSQL containers

## Development Workflow
1. Write end-to-end tests (called "snips") first
2. Implement features
3. Run tests with `pnpm harness jest`
4. Push to branch and create PR
5. Let CI run full test suite