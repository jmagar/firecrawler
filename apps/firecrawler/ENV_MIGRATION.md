# Environment Configuration Migration Notice

## Important: .env File Has Been Moved

As of this update, the Firecrawl MCP server no longer uses a separate `.env` file in this directory.

### New Configuration Location

All environment variables are now centrally managed in the **root `.env` file** at the project root:
```
/home/jmagar/compose/firecrawl/.env
```

### Why This Change?

1. **Single Source of Truth**: One configuration file for the entire stack
2. **Reduced Maintenance**: No need to keep multiple .env files in sync
3. **Better Security**: Centralized secret management
4. **Simpler Deployment**: One file to configure for Docker Compose and all services

### Migration Steps

If you had custom settings in `apps/firecrawler/.env`:

1. Copy any custom values to the root `.env` file
2. For MCP-specific overrides, create `.env.local` in this directory (not tracked by git)
3. Remove the old `apps/firecrawler/.env` file

### Local Overrides

You can still override settings locally by creating:
```
apps/firecrawler/.env.local
```

This file will be loaded after the root `.env` and can override any settings.

### Example Configuration

See `.env.example` in the root directory for all available configuration options.

### Questions?

Refer to the main documentation or the consolidated environment plan in `CONSOLIDATE-ENV.md`.