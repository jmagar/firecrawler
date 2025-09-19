import { Mutex } from "async-mutex";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";
import chokidar, { FSWatcher } from "chokidar";
import { logger } from "../lib/logger";
import { SecurityAuditLogger } from "../lib/security/audit-logger";

interface ConfigCache {
  data: Record<string, any>;
  lastModified: number;
  cacheTimestamp: number;
}

interface FileWatcher {
  lastModified: number;
  isWatching: boolean;
}

interface EnvironmentVariableMatch {
  variable: string;
  defaultValue?: string;
}

// Define base directory for configs - restrict to safe directories
const CONFIG_BASE_DIR = path.resolve(process.cwd(), "config");
const CONFIG_FALLBACK_DIRS = [
  process.cwd(),
  path.resolve(process.cwd(), "..", ".."), // For monorepo structure
];

// Allowed environment variables whitelist for security (same as config-validator)
const ALLOWED_ENV_VARS = new Set([
  "FIRECRAWL_API_URL",
  "PORT",
  "REDIS_HOST",
  "REDIS_PORT",
  "REDIS_PASSWORD",
  "DATABASE_URL",
  "VECTOR_DIMENSION",
  "MODEL_EMBEDDING_NAME",
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "SUPABASE_URL",
  "SUPABASE_ANON_KEY",
  "BULL_AUTH_KEY",
  "LOGTAIL_KEY",
  "PLAYWRIGHT_MICROSERVICE_URL",
  "LLAMAPARSE_API_KEY",
  "SERP_API_KEY",
  "SCRAPING_BEE_API_KEY",
  "FIRE_ENGINE_BETA_URL",
  "HYPERBOLIC_API_KEY",
  "OPENROUTER_API_KEY",
  "TOGETHER_API_KEY",
  "OLLAMA_BASE_URL",
  "FLY_MACHINE_VERSION",
  "POSTHOG_API_KEY",
  "POSTHOG_HOST",
  "SLACK_WEBHOOK_URL",
  "ENV",
  "NODE_ENV",
  "NUM_WORKERS_PER_QUEUE",
  "REDIS_RATE_LIMIT_URL",
  "USE_DB_AUTHENTICATION",
  "SUPABASE_SERVICE_TOKEN",
  "STRIPE_PRICE_ID",
  "STRIPE_WEBHOOK_SECRET",
  "WEBHOOK_URL",
  "WORKERS_URL",
  "WORKERS_TOKEN",
  "SCRAPE_DO_API_KEY",
  "BRIGHTDATA_PASSWORD",
  "BRIGHTDATA_USERNAME",
  "LLAMAINDEX_LOGGING_ENABLED",
  "TEST_API_KEY",
  "SELF_HOSTED_WEBHOOK_URL",
  "FIRECRAWL_CONFIG_PATH",
  "FIRECRAWL_CONFIG_OVERRIDE",
  // Test environment variables used in tests
  "TEST_VAR",
  "TIMEOUT_VAR",
  "MOBILE_VAR",
  "ENABLE_FEATURE",
  "DISABLE_FEATURE",
  "INVALID_NUMBER",
  "MISSING_VAR",
  "NONEXISTENT_VAR",
  "ANOTHER_VAR",
  "UNDEFINED_VAR",
  "VAR",
  "TEST_SUITE_SELF_HOSTED",
  "IDMUX_URL",
  "CONFIG_DEBOUNCE_DELAY",
]);

/**
 * Configuration management service with file watching and caching.
 *
 * Provides centralized configuration loading from YAML files with:
 * - Automatic file watching and hot reloading
 * - Environment variable substitution
 * - JSON override support
 * - Thread-safe caching with mutex protection
 * - Path traversal prevention
 *
 * @example
 * const config = await configService.getConfiguration();
 * const apiConfig = config.api || {};
 */
class ConfigService {
  private static instance: ConfigService;
  private static instanceMutex = new Mutex();

  private configCache: ConfigCache | null = null;
  private fileWatcher: FileWatcher | null = null;
  private watcher: FSWatcher | null = null;
  private configPath: string;
  private readonly cacheTTL: number = 30000; // 30 seconds
  private readonly watchDebounceDelay: number = parseInt(
    process.env.CONFIG_DEBOUNCE_DELAY || "1000",
  ); // 1 second
  private watchTimeout: NodeJS.Timeout | null = null;
  private configMutex = new Mutex();

  private constructor() {
    // Discover config file path
    this.configPath = this.discoverConfigPath();
  }

  private validateConfigPath(configPath: string): string | null {
    try {
      const resolved = path.resolve(configPath);

      // Check against allowed base directories
      const isAllowedPath = CONFIG_FALLBACK_DIRS.some(baseDir => {
        const resolvedBaseDir = path.resolve(baseDir);
        return resolved.startsWith(resolvedBaseDir);
      });

      if (!isAllowedPath) {
        logger.error(
          "Path traversal attempt detected - path outside allowed directories",
          {
            module: "config-service",
            method: "validateConfigPath",
            attempted: configPath,
            resolved,
            allowedDirectories: CONFIG_FALLBACK_DIRS,
          },
        );
        SecurityAuditLogger.logPathAccess(configPath, false);
        SecurityAuditLogger.logUnauthorizedAccess("PATH_TRAVERSAL", {
          attempted: configPath,
          resolved,
          reason: "outside_allowed_directories",
        });
        return null;
      }

      // Additional security: ensure no upward directory traversal patterns
      const normalizedPath = path.normalize(configPath);
      if (normalizedPath.includes("..")) {
        logger.error(
          "Path traversal attempt detected - contains directory traversal patterns",
          {
            module: "config-service",
            method: "validateConfigPath",
            attempted: configPath,
            normalized: normalizedPath,
          },
        );
        SecurityAuditLogger.logPathAccess(configPath, false);
        SecurityAuditLogger.logUnauthorizedAccess("PATH_TRAVERSAL", {
          attempted: configPath,
          normalized: normalizedPath,
          reason: "directory_traversal_patterns",
        });
        return null;
      }

      // Ensure the resolved path actually ends with a reasonable config file
      if (!resolved.match(/\.(yaml|yml|json)$/i)) {
        logger.warn("Invalid config file extension", {
          module: "config-service",
          method: "validateConfigPath",
          attempted: configPath,
          resolved,
        });
        return null;
      }

      logger.debug("Config path validated successfully", {
        module: "config-service",
        method: "validateConfigPath",
        original: configPath,
        resolved,
      });

      SecurityAuditLogger.logPathAccess(configPath, true);
      return resolved;
    } catch (error) {
      logger.error("Error validating config path", {
        module: "config-service",
        method: "validateConfigPath",
        attempted: configPath,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  public static async getInstance(): Promise<ConfigService> {
    if (ConfigService.instance) {
      return ConfigService.instance;
    }

    await this.instanceMutex.runExclusive(async () => {
      if (!ConfigService.instance) {
        ConfigService.instance = new ConfigService();
      }
    });

    return ConfigService.instance;
  }

  private discoverConfigPath(): string {
    // Check environment variable first with validation
    const envPath = process.env.FIRECRAWL_CONFIG_PATH;
    if (envPath) {
      const validatedPath = this.validateConfigPath(envPath);
      if (validatedPath && fs.existsSync(validatedPath)) {
        logger.info("Using environment-specified config path", {
          module: "config-service",
          method: "discoverConfigPath",
          configPath: validatedPath,
        });
        return validatedPath;
      } else if (envPath) {
        logger.warn(
          "Environment-specified config path is invalid or does not exist",
          {
            module: "config-service",
            method: "discoverConfigPath",
            attempted: envPath,
            validated: validatedPath,
          },
        );
      }
    }

    // Default paths to check
    const defaultPaths = [
      path.join(process.cwd(), "defaults.yaml"),
      path.join(process.cwd(), "config", "defaults.yaml"),
      path.join(process.cwd(), "..", "..", "defaults.yaml"), // For monorepo structure
    ];

    for (const configPath of defaultPaths) {
      const validatedPath = this.validateConfigPath(configPath);
      if (validatedPath && fs.existsSync(validatedPath)) {
        logger.info("Using default config path", {
          module: "config-service",
          method: "discoverConfigPath",
          configPath: validatedPath,
        });
        return validatedPath;
      }
    }

    // Return default path even if file doesn't exist (for logging purposes)
    const defaultPath = path.join(process.cwd(), "defaults.yaml");
    logger.debug("No existing config found, using default path", {
      module: "config-service",
      method: "discoverConfigPath",
      configPath: defaultPath,
    });
    return defaultPath;
  }

  private getFileModifiedTime(filePath: string): number {
    try {
      const stats = fs.statSync(filePath);
      return stats.mtime.getTime();
    } catch (error) {
      return 0;
    }
  }

  private isCacheValid(): boolean {
    if (!this.configCache) {
      return false;
    }

    const now = Date.now();
    const cacheAge = now - this.configCache.cacheTimestamp;

    // Check cache TTL
    if (cacheAge > this.cacheTTL) {
      return false;
    }

    // Check if file has been modified
    const currentModified = this.getFileModifiedTime(this.configPath);
    return currentModified === this.configCache.lastModified;
  }

  private setupFileWatcher(): void {
    if (!fs.existsSync(this.configPath)) {
      return;
    }

    try {
      if (!this.fileWatcher) {
        this.fileWatcher = {
          lastModified: this.getFileModifiedTime(this.configPath),
          isWatching: false,
        };
      }

      if (!this.fileWatcher.isWatching) {
        // Close existing watcher before creating new one
        if (this.watcher) {
          this.watcher.close();
          this.watcher = null;
        }

        // Create new chokidar watcher with options for better atomic write handling
        this.watcher = chokidar.watch(this.configPath, {
          persistent: true,
          ignoreInitial: true, // Don't trigger on initial scan
          atomic: true, // Wait for write operations to complete
          awaitWriteFinish: {
            stabilityThreshold: 100, // Wait 100ms for file size to stabilize
            pollInterval: 50, // Check every 50ms
          },
          usePolling: false, // Use native fs events when possible
          alwaysStat: false, // Don't always stat files for better performance
        });

        // Handle file changes
        this.watcher.on("change", (filePath: string) => {
          logger.debug("Configuration file changed", {
            module: "config-service",
            method: "setupFileWatcher",
            configPath: this.configPath,
            changedPath: filePath,
          });
          this.handleFileChange();
        });

        // Handle atomic replacements (common with editors and atomic writes)
        this.watcher.on("add", (filePath: string) => {
          logger.info(
            "Configuration file was added/replaced, handling atomic change",
            {
              module: "config-service",
              method: "setupFileWatcher",
              configPath: this.configPath,
              addedPath: filePath,
            },
          );
          this.handleFileChange();
        });

        // Handle file deletion
        this.watcher.on("unlink", (filePath: string) => {
          logger.info("Configuration file was deleted, clearing cache", {
            module: "config-service",
            method: "setupFileWatcher",
            configPath: this.configPath,
            deletedPath: filePath,
          });
          this.configCache = null;
        });

        // Handle watcher errors
        this.watcher.on("error", (error: Error) => {
          logger.warn("File watcher error, recreating watcher", {
            module: "config-service",
            method: "setupFileWatcher",
            configPath: this.configPath,
            error: error.message,
          });

          // Recreate the watcher after a delay
          setTimeout(() => {
            if (this.fileWatcher) {
              this.fileWatcher.isWatching = false;
              this.setupFileWatcher();
            }
          }, 1000);
        });

        // Handle when watcher is ready
        this.watcher.on("ready", () => {
          logger.debug("File watcher setup successfully with chokidar", {
            module: "config-service",
            method: "setupFileWatcher",
            configPath: this.configPath,
          });
        });

        this.fileWatcher.isWatching = true;
      }
    } catch (error) {
      logger.warn("Failed to setup file watcher for config file", {
        module: "config-service",
        method: "setupFileWatcher",
        configPath: this.configPath,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  // Add debounce utility method
  private debounce<T extends (...args: any[]) => void>(
    func: T,
    wait: number,
  ): (...args: Parameters<T>) => void {
    let timeoutId: NodeJS.Timeout | null = null;
    let lastCallTime = 0;

    return (...args: Parameters<T>) => {
      const now = Date.now();
      const timeSinceLastCall = now - lastCallTime;

      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      // Log rapid changes for monitoring
      if (timeSinceLastCall < 100) {
        logger.warn("Rapid config changes detected", {
          timeSinceLastCall,
          module: "config-service",
        });
      }

      lastCallTime = now;
      timeoutId = setTimeout(() => {
        func(...args);
        timeoutId = null;
      }, wait);
    };
  }

  // Replace handleFileChange implementation
  private handleFileChange = this.debounce((): void => {
    this.configMutex.runExclusive(async () => {
      try {
        logger.info("Configuration file changed, reloading atomically", {
          module: "config-service",
          method: "handleFileChange",
          configPath: this.configPath,
        });

        // Atomic cache invalidation and reload
        const previousCache = this.configCache;
        this.configCache = null;

        // Update file watcher state
        if (this.fileWatcher) {
          this.fileWatcher.lastModified = this.getFileModifiedTime(
            this.configPath,
          );
        }

        // Attempt to reload configuration
        try {
          await this.getConfiguration();
          logger.info("Configuration reloaded successfully");
        } catch (error) {
          // Restore previous cache on failure
          this.configCache = previousCache;
          logger.error("Failed to reload configuration, restored previous", {
            error,
          });
        }
      } catch (error) {
        logger.error("Critical error in handleFileChange", { error });
      }
    });
  }, this.watchDebounceDelay);

  private substituteEnvironmentVariables(value: any): any {
    if (typeof value === "string") {
      return this.substituteEnvInString(value);
    } else if (Array.isArray(value)) {
      return value.map(item => this.substituteEnvironmentVariables(item));
    } else if (value && typeof value === "object") {
      const result: Record<string, any> = {};
      for (const [key, val] of Object.entries(value)) {
        result[key] = this.substituteEnvironmentVariables(val);
      }
      return result;
    }
    return value;
  }

  private coerceScalar(v: any): any {
    if (typeof v !== "string") return v;
    const s = v.trim().toLowerCase();
    if (s === "true") return true;
    if (s === "false") return false;
    if (/^-?\d+(\.\d+)?$/.test(s)) {
      const n = Number(v);
      if (Number.isFinite(n)) return n;
    }
    return v;
  }

  private sanitizeEnvValue(varName: string, value: string): string {
    // Remove potentially dangerous characters that could be used for injection
    const sanitized = value.replace(/[<>&'"\\]/g, "");

    // Log sanitization using SecurityAuditLogger
    SecurityAuditLogger.logSanitization("ENV_VALUE", value, sanitized);

    // Log sensitive variable access with redacted values
    if (
      varName.includes("KEY") ||
      varName.includes("SECRET") ||
      varName.includes("TOKEN") ||
      varName.includes("PASSWORD")
    ) {
      logger.info(
        "Sensitive environment variable accessed during config substitution",
        {
          variable: varName,
          redacted: "[REDACTED]",
          module: "config-service",
          method: "sanitizeEnvValue",
        },
      );
    } else {
      logger.debug("Environment variable sanitized", {
        variable: varName,
        originalLength: value.length,
        sanitizedLength: sanitized.length,
        module: "config-service",
        method: "sanitizeEnvValue",
      });
    }

    // Warn if sanitization removed characters
    if (sanitized.length !== value.length) {
      logger.warn(
        "Potentially dangerous characters removed from environment variable",
        {
          variable: varName,
          originalLength: value.length,
          sanitizedLength: sanitized.length,
          module: "config-service",
          method: "sanitizeEnvValue",
        },
      );
    }

    return sanitized;
  }

  private substituteEnvInString(str: string): any {
    const envVarRegex = /\$\{([^}]+)\}/g;

    const result = str.replace(envVarRegex, (match, expression) => {
      const parsed = this.parseEnvironmentExpression(expression);

      // Security: Check if environment variable is whitelisted
      if (!ALLOWED_ENV_VARS.has(parsed.variable)) {
        logger.warn(
          "Attempted to access unauthorized environment variable during config substitution",
          {
            variable: parsed.variable,
            expression,
            module: "config-service",
            method: "substituteEnvInString",
          },
        );
        SecurityAuditLogger.logUnauthorizedAccess("ENV_ACCESS", {
          variable: parsed.variable,
          context: "config-service.substituteEnvInString",
          expression,
        });
        return parsed.defaultValue || "";
      }

      const envValue = process.env[parsed.variable];

      if (envValue !== undefined) {
        // Log environment variable access
        SecurityAuditLogger.logEnvAccess(
          parsed.variable,
          "config-service.substituteEnvInString",
        );
        // Sanitize the environment value before using it
        const sanitizedValue = this.sanitizeEnvValue(parsed.variable, envValue);
        return sanitizedValue;
      } else if (parsed.defaultValue !== undefined) {
        logger.debug("Using default value for environment variable", {
          variable: parsed.variable,
          hasDefault: true,
          module: "config-service",
          method: "substituteEnvInString",
        });
        return parsed.defaultValue;
      } else {
        logger.warn("Environment variable not found and no default provided", {
          module: "config-service",
          method: "substituteEnvInString",
          variable: parsed.variable,
          expression,
        });
        return match; // Return original if no substitution possible
      }
    });

    return this.coerceScalar(result);
  }

  private parseEnvironmentExpression(
    expression: string,
  ): EnvironmentVariableMatch {
    const parts = expression.split(":-");
    return {
      variable: parts[0].trim(),
      defaultValue: parts[1]?.trim(),
    };
  }

  private loadYamlFile(): Record<string, any> {
    if (!fs.existsSync(this.configPath)) {
      logger.debug("YAML config file not found, using empty configuration", {
        module: "config-service",
        method: "loadYamlFile",
        configPath: this.configPath,
      });
      return {};
    }

    try {
      const fileContent = fs.readFileSync(this.configPath, "utf8");
      const parsedYaml = yaml.load(fileContent, {
        schema: yaml.JSON_SCHEMA,
      }) as Record<string, any>;

      if (!parsedYaml || typeof parsedYaml !== "object") {
        logger.warn(
          "YAML config file is empty or invalid, using empty configuration",
          {
            module: "config-service",
            method: "loadYamlFile",
            configPath: this.configPath,
          },
        );
        return {};
      }

      return parsedYaml;
    } catch (error) {
      logger.error(
        "Failed to parse YAML config file, using empty configuration",
        {
          module: "config-service",
          method: "loadYamlFile",
          configPath: this.configPath,
          error: error instanceof Error ? error.message : String(error),
        },
      );
      return {};
    }
  }

  private loadJsonOverride(): Record<string, any> {
    const jsonOverride = process.env.FIRECRAWL_CONFIG_OVERRIDE;

    if (!jsonOverride) {
      return {};
    }

    const overrideSize = jsonOverride.length;
    if (overrideSize > 50000) {
      logger.warn(
        `FIRECRAWL_CONFIG_OVERRIDE too large (${overrideSize} chars), skipping`,
        {
          module: "config-service",
          method: "loadJsonOverride",
          size: overrideSize,
        },
      );
      return {};
    }

    try {
      const parsed = JSON.parse(jsonOverride);

      if (!parsed || typeof parsed !== "object") {
        logger.warn(
          "FIRECRAWL_CONFIG_OVERRIDE is not a valid object, ignoring",
          {
            module: "config-service",
            method: "loadJsonOverride",
          },
        );
        return {};
      }

      // Apply environment variable substitution (similar to YAML behavior)
      const substitutedConfig = this.substituteEnvironmentVariables(parsed);

      logger.debug(
        `Applied JSON configuration override (${overrideSize} chars)`,
        {
          module: "config-service",
          method: "loadJsonOverride",
          overrideKeys: Object.keys(substitutedConfig),
          size: overrideSize,
        },
      );

      return substitutedConfig;
    } catch (error) {
      logger.error("Failed to parse FIRECRAWL_CONFIG_OVERRIDE JSON, ignoring", {
        module: "config-service",
        method: "loadJsonOverride",
        error: error instanceof Error ? error.message : String(error),
      });
      return {};
    }
  }

  private deepMerge(
    target: Record<string, any>,
    source: Record<string, any>,
  ): Record<string, any> {
    const result = { ...target };

    for (const [key, value] of Object.entries(source)) {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        if (
          result[key] &&
          typeof result[key] === "object" &&
          !Array.isArray(result[key])
        ) {
          result[key] = this.deepMerge(result[key], value);
        } else {
          result[key] = { ...value };
        }
      } else {
        result[key] = value;
      }
    }

    return result;
  }

  private loadConfiguration(): Record<string, any> {
    const startTime = Date.now();

    // Load YAML file
    const yamlConfig = this.loadYamlFile();

    // Apply environment variable substitution with security logging
    logger.debug("Applying environment variable substitution to config", {
      module: "config-service",
      method: "loadConfiguration",
      configSections: Object.keys(yamlConfig),
    });
    const substitutedConfig = this.substituteEnvironmentVariables(yamlConfig);

    // Load JSON override
    const jsonOverride = this.loadJsonOverride();

    // Merge configurations with precedence: JSON override > YAML file
    const finalConfig = this.deepMerge(substitutedConfig, jsonOverride);

    const loadTime = Date.now() - startTime;

    // Security: Log configuration loading patterns for monitoring
    SecurityAuditLogger.logConfigChange(this.configPath);
    logger.info("Configuration loaded successfully", {
      module: "config-service",
      method: "loadConfiguration",
      configPath: this.configPath,
      hasYamlConfig: Object.keys(yamlConfig).length > 0,
      hasJsonOverride: Object.keys(jsonOverride).length > 0,
      yamlConfigSections: Object.keys(yamlConfig),
      jsonOverrideSections: Object.keys(jsonOverride),
      finalConfigSections: Object.keys(finalConfig),
      totalConfigOptions: Object.values(finalConfig).reduce(
        (total: number, section: any) =>
          total +
          (section && typeof section === "object"
            ? Object.keys(section).length
            : 0),
        0,
      ),
      loadTimeMs: loadTime,
      timestamp: new Date().toISOString(),
    });

    // Security audit: detect unusual configuration patterns
    this.auditConfigurationLoad(yamlConfig, jsonOverride, finalConfig);

    return finalConfig;
  }

  private auditConfigurationLoad(
    yamlConfig: Record<string, any>,
    jsonOverride: Record<string, any>,
    finalConfig: Record<string, any>,
  ): void {
    // Detect if JSON override is overriding significant portions of YAML config
    const yamlKeys = Object.keys(yamlConfig);
    const overrideKeys = Object.keys(jsonOverride);
    const overriddenYamlKeys = yamlKeys.filter(key =>
      overrideKeys.includes(key),
    );

    if (overriddenYamlKeys.length > 0) {
      logger.info("JSON override is overriding YAML configuration sections", {
        module: "config-service",
        method: "auditConfigurationLoad",
        overriddenSections: overriddenYamlKeys,
        overridePercentage: Math.round(
          (overriddenYamlKeys.length / yamlKeys.length) * 100,
        ),
      });
    }

    // Detect large JSON overrides (potential security concern)
    const jsonOverrideSize = JSON.stringify(jsonOverride).length;
    if (jsonOverrideSize > 10000) {
      logger.warn("Large JSON configuration override detected", {
        module: "config-service",
        method: "auditConfigurationLoad",
        overrideSize: jsonOverrideSize,
        overrideSections: Object.keys(jsonOverride),
      });
    }

    // Log final configuration structure for audit trail
    const configStructure = Object.fromEntries(
      Object.entries(finalConfig).map(([key, value]) => [
        key,
        value && typeof value === "object" ? Object.keys(value).length : 1,
      ]),
    );

    logger.debug("Final configuration structure audit", {
      module: "config-service",
      method: "auditConfigurationLoad",
      structure: configStructure,
      totalSections: Object.keys(finalConfig).length,
    });
  }

  public async getConfiguration(): Promise<Record<string, any>> {
    if (this.isCacheValid()) {
      return this.configCache!.data;
    }

    return await ConfigService.instanceMutex.runExclusive(async () => {
      // Double-check cache validity after acquiring lock
      if (this.isCacheValid()) {
        return this.configCache!.data;
      }

      const config = this.loadConfiguration();
      const lastModified = this.getFileModifiedTime(this.configPath);

      this.configCache = {
        data: config,
        lastModified,
        cacheTimestamp: Date.now(),
      };

      // Setup file watching for auto-reload
      this.setupFileWatcher();

      return config;
    });
  }

  public async getConfigForRoute(route: string): Promise<Record<string, any>> {
    const fullConfig = await this.getConfiguration();

    // Route-specific configuration extraction
    const routeConfig = fullConfig[route] || {};

    // Also include global/default sections that apply to all routes
    const globalConfig = {
      ...(fullConfig.global || {}),
      ...(fullConfig.defaults || {}),
    };

    return this.deepMerge(globalConfig, routeConfig);
  }

  public clearCache(): void {
    this.configCache = null;
    logger.debug("Configuration cache cleared", {
      module: "config-service",
      method: "clearCache",
    });
  }

  public async shutdown(): Promise<void> {
    if (this.watchTimeout) {
      clearTimeout(this.watchTimeout);
      this.watchTimeout = null;
    }

    if (this.watcher) {
      try {
        await this.watcher.close();
        this.watcher = null;
        if (this.fileWatcher) {
          this.fileWatcher.isWatching = false;
          this.fileWatcher = null;
        }
      } catch (error) {
        logger.warn("Failed to cleanup file watcher", {
          module: "config-service",
          method: "shutdown",
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    this.configCache = null;

    logger.debug("ConfigService shutdown completed", {
      module: "config-service",
      method: "shutdown",
    });
  }
}

export const configServicePromise = ConfigService.getInstance();
export default configServicePromise;
