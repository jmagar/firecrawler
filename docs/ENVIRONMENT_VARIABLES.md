# Environment Variables Reference

Complete list of environment variables used in Firecrawl.

## Required Variables

### VECTOR_DIMENSION
- **Type**: Integer
- **Required**: Yes (for vector search)
- **Description**: Output dimension of your embedding model
- **Common Values**:
  - `384`: MiniLM models
  - `768`: BERT-based models
  - `1024`: Large BERT models
  - `1536`: OpenAI text-embedding-3-small
  - `3072`: OpenAI text-embedding-3-large
- **Example**: `VECTOR_DIMENSION=1536`

### MODEL_EMBEDDING_NAME
- **Type**: String
- **Required**: Yes (for embeddings)
- **Description**: Name of the embedding model to use
- **Examples**: 
  - `text-embedding-3-small`
  - `text-embedding-3-large`
  - `all-MiniLM-L6-v2`

## Performance Configuration

### MAX_THRESHOLD_HISTORY
- **Type**: Integer
- **Default**: `10`
- **Description**: Maximum size of threshold history for memory management
- **Range**: 1-100

### CONFIG_DEBOUNCE_DELAY
- **Type**: Integer
- **Default**: `1000`
- **Description**: Delay in milliseconds for config file change debouncing
- **Range**: 100-10000

### VECTOR_THRESHOLD_FLOOR_1
- **Type**: Float
- **Default**: `0.55`
- **Description**: Primary threshold floor for vector similarity

### VECTOR_THRESHOLD_FLOOR_2
- **Type**: Float
- **Default**: `0.4`
- **Description**: Secondary threshold floor for vector similarity

### VECTOR_THRESHOLD_FLOOR_3
- **Type**: Float
- **Default**: `0.3`
- **Description**: Tertiary threshold floor for vector similarity

## Security Configuration

### CONFIG_BASE_DIR
- **Type**: Path
- **Default**: Current working directory
- **Description**: Base directory for configuration files (prevents traversal)
- **Example**: `/app/config`

### SECURITY_AUDIT_LOG
- **Type**: Boolean
- **Default**: `false`
- **Description**: Enable security audit logging
- **Values**: `true` | `false`

## API Configuration

### FIRECRAWL_API_KEY
- **Type**: String
- **Required**: Yes
- **Description**: API key for Firecrawl service
- **Security**: Never commit to version control

### FIRECRAWL_API_URL
- **Type**: URL
- **Default**: `https://api.firecrawl.dev`
- **Description**: Base URL for Firecrawl API

### FIRECRAWL_CONFIG_PATH
- **Type**: Path
- **Default**: Auto-discovered
- **Description**: Path to configuration YAML file

## Database Configuration

### DATABASE_URL
- **Type**: Connection String
- **Required**: Yes (for database features)
- **Description**: PostgreSQL connection string
- **Example**: `postgresql://user:pass@localhost/dbname`

### REDIS_URL
- **Type**: Connection String
- **Required**: Yes (for caching)
- **Description**: Redis connection string
- **Example**: `redis://localhost:6379`

## Logging

### LOG_LEVEL
- **Type**: String
- **Default**: `info`
- **Description**: Logging verbosity
- **Values**: `debug` | `info` | `warn` | `error`

### NODE_ENV
- **Type**: String
- **Default**: `development`
- **Description**: Application environment
- **Values**: `development` | `production` | `test`

## Testing

### TEST_SUITE_SELF_HOSTED
- **Type**: Boolean
- **Description**: Running in self-hosted test environment
- **Usage**: Skip tests requiring cloud services

### OPENAI_API_KEY
- **Type**: String
- **Description**: OpenAI API key for AI features
- **Required**: For AI-powered extraction

### OLLAMA_BASE_URL
- **Type**: URL
- **Description**: Ollama API endpoint for local AI
- **Alternative**: To OpenAI for self-hosted AI

## Port Configuration

### PORT
- **Type**: Integer
- **Default**: `3000`
- **Description**: Server listening port
- **Range**: 1-65535