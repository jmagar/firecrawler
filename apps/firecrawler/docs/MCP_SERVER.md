# Firecrawler MCP Server Deployment and Configuration Guide

This document provides comprehensive guidance for deploying, configuring, and managing the Firecrawler MCP server in various environments.

## Overview

The Firecrawler MCP server is built on FastMCP 2.12.2+ and provides production-ready web scraping, crawling, and vector search capabilities through the Model Context Protocol. It supports multiple deployment patterns and can be configured for cloud or self-hosted Firecrawl instances.

## Quick Start

### Local Development

```bash
# 1. Navigate to project directory
cd apps/firecrawler

# 2. Install dependencies
uv pip install -e .

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings

# 4. Start development server
fastmcp dev firecrawl_mcp.server
```

### Production Deployment

```bash
# 1. Install production dependencies
uv pip install -e ".[prod]"

# 2. Configure environment
export FIRECRAWL_API_KEY="your-api-key"
export FIRECRAWLER_HOST="0.0.0.0"
export FIRECRAWLER_PORT="8000"

# 3. Start production server
fastmcp run firecrawl_mcp.server
```

## Environment Configuration

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FIRECRAWL_API_KEY` | Your Firecrawl API key | `fc-1234567890abcdef` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FIRECRAWL_API_BASE_URL` | `https://api.firecrawl.dev` | API endpoint URL |
| `FIRECRAWLER_HOST` | `localhost` | Server bind address |
| `FIRECRAWLER_PORT` | `8000` | Server port |
| `FIRECRAWLER_LOG_LEVEL` | `INFO` | Logging level |
| `FIRECRAWLER_TRANSPORT` | `streamable-http` | MCP transport method |

### Advanced Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FIRECRAWLER_MAX_WORKERS` | `4` | Maximum concurrent workers |
| `FIRECRAWLER_TIMEOUT` | `300` | Default request timeout (seconds) |
| `FIRECRAWLER_RATE_LIMIT` | `60` | Requests per minute limit |
| `FIRECRAWLER_CACHE_TTL` | `3600` | Cache TTL in seconds |
| `FIRECRAWLER_LOG_ROTATION` | `5MB` | Log file rotation size |
| `FIRECRAWLER_LOG_BACKUP_COUNT` | `3` | Number of log backups |

### Vector Search Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VECTOR_SEARCH_ENABLED` | `true` | Enable vector search capabilities |
| `VECTOR_EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | Embedding model |
| `VECTOR_DIMENSION` | `1024` | Vector dimensions |
| `TEI_API_BASE_URL` | `http://localhost:8080` | TEI server URL |

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key for extractions |
| `OLLAMA_BASE_URL` | - | Ollama server URL |
| `DEFAULT_LLM_MODEL` | `gpt-3.5-turbo` | Default model for extractions |

## FastMCP Configuration

### Basic Configuration (`fastmcp.json`)

```json
{
  "servers": {
    "firecrawler": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "firecrawl_mcp.server"],
      "transport": "streamable-http",
      "host": "localhost",
      "port": 8000,
      "env": {
        "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"
      }
    }
  }
}
```

### Production Configuration

```json
{
  "servers": {
    "firecrawler": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "firecrawl_mcp.server"],
      "transport": "streamable-http",
      "host": "0.0.0.0",
      "port": 8000,
      "timeout": 300,
      "maxConnections": 100,
      "env": {
        "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}",
        "FIRECRAWLER_LOG_LEVEL": "INFO",
        "FIRECRAWLER_MAX_WORKERS": "8"
      },
      "restart": {
        "enabled": true,
        "maxRestarts": 3,
        "restartDelay": 5000
      }
    }
  },
  "logging": {
    "level": "INFO",
    "file": "logs/fastmcp.log",
    "rotation": "5MB",
    "backupCount": 3
  }
}
```

### SSL/TLS Configuration

```json
{
  "servers": {
    "firecrawler": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "firecrawl_mcp.server"],
      "transport": "streamable-http",
      "host": "0.0.0.0",
      "port": 8443,
      "ssl": {
        "enabled": true,
        "cert": "/path/to/cert.pem",
        "key": "/path/to/key.pem"
      }
    }
  }
}
```

## Deployment Patterns

### Standalone Server

Deploy as a single server instance:

```bash
# Direct execution
fastmcp run firecrawl_mcp.server --host 0.0.0.0 --port 8000

# With configuration file
fastmcp run --config fastmcp.json firecrawler
```

### Docker Deployment

#### Basic Dockerfile

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy application files
COPY . .

# Install Python dependencies
RUN uv pip install -e .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start server
CMD ["fastmcp", "run", "firecrawl_mcp.server"]
```

#### Docker Compose

```yaml
version: '3.8'

services:
  firecrawler:
    build: .
    container_name: firecrawler-mcp
    ports:
      - "8000:8000"
    environment:
      - FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}
      - FIRECRAWLER_HOST=0.0.0.0
      - FIRECRAWLER_PORT=8000
      - FIRECRAWLER_LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - firecrawler-net

  # Optional: Redis for caching
  redis:
    image: redis:7-alpine
    container_name: firecrawler-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped
    networks:
      - firecrawler-net

volumes:
  redis-data:

networks:
  firecrawler-net:
    driver: bridge
```

### Kubernetes Deployment

#### Basic Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: firecrawler-mcp
  labels:
    app: firecrawler-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: firecrawler-mcp
  template:
    metadata:
      labels:
        app: firecrawler-mcp
    spec:
      containers:
      - name: firecrawler
        image: firecrawler-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: FIRECRAWL_API_KEY
          valueFrom:
            secretKeyRef:
              name: firecrawler-secrets
              key: api-key
        - name: FIRECRAWLER_HOST
          value: "0.0.0.0"
        - name: FIRECRAWLER_PORT
          value: "8000"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: logs
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: firecrawler-mcp-service
spec:
  selector:
    app: firecrawler-mcp
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
---
apiVersion: v1
kind: Secret
metadata:
  name: firecrawler-secrets
type: Opaque
data:
  api-key: <base64-encoded-api-key>
```

#### Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: firecrawler-mcp-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - firecrawler.yourdomain.com
    secretName: firecrawler-tls
  rules:
  - host: firecrawler.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: firecrawler-mcp-service
            port:
              number: 8000
```

### Cloud Deployment

#### AWS ECS

```json
{
  "family": "firecrawler-mcp",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "firecrawler",
      "image": "your-repo/firecrawler-mcp:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "FIRECRAWLER_HOST",
          "value": "0.0.0.0"
        },
        {
          "name": "FIRECRAWLER_PORT", 
          "value": "8000"
        }
      ],
      "secrets": [
        {
          "name": "FIRECRAWL_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:firecrawl-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/firecrawler-mcp",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

#### Google Cloud Run

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: firecrawler-mcp
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/memory: "1Gi"
        run.googleapis.com/cpu: "1000m"
        run.googleapis.com/max-scale: "10"
    spec:
      containerConcurrency: 80
      containers:
      - image: gcr.io/project-id/firecrawler-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: FIRECRAWLER_HOST
          value: "0.0.0.0"
        - name: FIRECRAWLER_PORT
          value: "8000"
        - name: FIRECRAWL_API_KEY
          valueFrom:
            secretKeyRef:
              name: firecrawler-secrets
              key: api-key
        resources:
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

## Monitoring and Observability

### Health Checks

The server exposes several health check endpoints:

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed status
curl http://localhost:8000/status

# Readiness check
curl http://localhost:8000/ready
```

### Metrics Collection

#### Prometheus Integration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'firecrawler-mcp'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

#### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Firecrawler MCP Server",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(firecrawler_requests_total[5m])",
            "legendFormat": "Requests/sec"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, firecrawler_request_duration_seconds_bucket)",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(firecrawler_errors_total[5m])",
            "legendFormat": "Errors/sec"
          }
        ]
      }
    ]
  }
}
```

### Logging Configuration

#### Structured Logging

```python
# logging.yaml
version: 1
disable_existing_loggers: false
formatters:
  json:
    format: '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s"}'
  standard:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: json
    filename: logs/firecrawler.log
    maxBytes: 5242880  # 5MB
    backupCount: 3

  error_file:
    class: logging.handlers.RotatingFileHandler
    level: ERROR
    formatter: json
    filename: logs/errors.log
    maxBytes: 5242880  # 5MB
    backupCount: 3

loggers:
  firecrawl_mcp:
    level: DEBUG
    handlers: [console, file]
    propagate: false
  
  middleware:
    level: INFO
    handlers: [file]
    propagate: false

root:
  level: WARNING
  handlers: [console, error_file]
```

## Security Configuration

### API Key Management

```bash
# Environment variable
export FIRECRAWL_API_KEY="fc-your-api-key"

# Using secrets manager (AWS)
aws secretsmanager create-secret \
  --name firecrawl-api-key \
  --secret-string '{"api_key":"fc-your-api-key"}'

# Using Kubernetes secrets
kubectl create secret generic firecrawler-secrets \
  --from-literal=api-key=fc-your-api-key
```

### Network Security

#### Firewall Rules

```bash
# Allow HTTP traffic
sudo ufw allow 8000/tcp

# Allow HTTPS traffic
sudo ufw allow 8443/tcp

# Restrict to specific IPs
sudo ufw allow from 192.168.1.0/24 to any port 8000
```

#### Rate Limiting

```python
# Custom rate limiting configuration
RATE_LIMIT_CONFIG = {
    "default": {
        "requests": 60,
        "window": 60,  # seconds
        "burst": 10
    },
    "scrape": {
        "requests": 100,
        "window": 60
    },
    "crawl": {
        "requests": 10,
        "window": 60
    },
    "extract": {
        "requests": 50,
        "window": 60
    }
}
```

### SSL/TLS Configuration

#### Generate Self-Signed Certificate

```bash
# Generate private key
openssl genrsa -out server.key 2048

# Generate certificate signing request
openssl req -new -key server.key -out server.csr

# Generate self-signed certificate
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt
```

#### Let's Encrypt Certificate

```bash
# Install certbot
sudo apt install certbot

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Certificate files location
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

## Performance Tuning

### Resource Allocation

```python
# Performance configuration
PERFORMANCE_CONFIG = {
    "max_workers": 8,           # Concurrent workers
    "max_connections": 100,     # Max HTTP connections
    "connection_timeout": 30,   # Connection timeout
    "read_timeout": 60,         # Read timeout
    "pool_size": 20,           # Connection pool size
    "pool_timeout": 30,        # Pool timeout
    "cache_size": 1000,        # Memory cache size
    "cache_ttl": 3600          # Cache TTL seconds
}
```

### Optimization Settings

```bash
# Environment optimizations
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=random

# UV optimizations
export UV_CACHE_DIR=/tmp/uv-cache
export UV_RESOLVER_STRATEGY=lowest-direct
```

### Database Optimization

```sql
-- PostgreSQL optimizations for vector search
-- Increase shared buffers
shared_buffers = 256MB

-- Increase work memory for sorting
work_mem = 64MB

-- Increase maintenance work memory
maintenance_work_mem = 256MB

-- Optimize for vector operations
effective_cache_size = 1GB
random_page_cost = 1.1
```

## Backup and Recovery

### Configuration Backup

```bash
#!/bin/bash
# backup-config.sh

BACKUP_DIR="/backup/firecrawler/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup configuration files
cp fastmcp.json $BACKUP_DIR/
cp .env $BACKUP_DIR/
cp -r logs/ $BACKUP_DIR/logs/

# Backup application code
tar -czf $BACKUP_DIR/app.tar.gz firecrawl_mcp/

echo "Backup completed: $BACKUP_DIR"
```

### Database Backup

```bash
#!/bin/bash
# backup-database.sh

# PostgreSQL backup
pg_dump -h localhost -U postgres -d firecrawl_vectors \
  --format=custom \
  --file=/backup/vectors_$(date +%Y%m%d_%H%M%S).dump

# Redis backup
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb /backup/redis_$(date +%Y%m%d_%H%M%S).rdb
```

### Recovery Procedures

```bash
#!/bin/bash
# restore-config.sh

BACKUP_DIR=$1

if [ -z "$BACKUP_DIR" ]; then
  echo "Usage: $0 <backup_directory>"
  exit 1
fi

# Stop service
systemctl stop firecrawler-mcp

# Restore configuration
cp $BACKUP_DIR/fastmcp.json ./
cp $BACKUP_DIR/.env ./

# Restore logs
cp -r $BACKUP_DIR/logs/ ./

# Restore application
tar -xzf $BACKUP_DIR/app.tar.gz

# Start service
systemctl start firecrawler-mcp

echo "Recovery completed from: $BACKUP_DIR"
```

## Troubleshooting

### Common Issues

#### Connection Problems

```bash
# Check server status
curl -v http://localhost:8000/health

# Check logs
tail -f logs/firecrawler.log

# Check process
ps aux | grep fastmcp

# Check port binding
netstat -tlnp | grep 8000
```

#### Performance Issues

```bash
# Monitor resource usage
htop
iotop
netstat -i

# Check memory usage
free -h
cat /proc/meminfo

# Monitor disk I/O
iostat -x 1
```

#### API Issues

```bash
# Test API connectivity
curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/scrape \
  -d '{"url": "https://example.com"}'

# Check rate limits
curl -I https://api.firecrawl.dev/v2/scrape

# Verify credentials
echo $FIRECRAWL_API_KEY | base64 -d
```

### Debug Mode

```bash
# Enable debug logging
export FIRECRAWLER_LOG_LEVEL=DEBUG

# Run with debug output
fastmcp run firecrawl_mcp.server --debug

# Enable Python debugging
export PYTHONPATH=/app:$PYTHONPATH
python -m pdb -m fastmcp run firecrawl_mcp.server
```

### Log Analysis

```bash
# Recent errors
grep "ERROR" logs/firecrawler.log | tail -20

# Performance metrics
grep "TIMING" logs/middleware.log | tail -10

# Rate limit warnings
grep "RATE_LIMIT" logs/firecrawler.log

# Memory usage
grep "MEMORY" logs/firecrawler.log
```

For additional troubleshooting guidance, see the [main README](../README.md#troubleshooting) and check the FastMCP documentation at `docs/fastmcp/`.