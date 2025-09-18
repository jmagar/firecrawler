import { Mutex } from "async-mutex";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";
import { logger } from "../lib/logger";

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

class ConfigService {
  private static instance: ConfigService;
  private static instanceMutex = new Mutex();

  private configCache: ConfigCache | null = null;
  private fileWatcher: FileWatcher | null = null;
  private watcher: fs.FSWatcher | null = null;
  private configPath: string;
  private readonly cacheTTL: number = 30000; // 30 seconds
  private readonly watchDebounceDelay: number = 1000; // 1 second
  private watchTimeout: NodeJS.Timeout | null = null;

  private constructor() {
    // Discover config file path
    this.configPath = this.discoverConfigPath();
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
    // Check environment variable first
    const envPath = process.env.FIRECRAWL_CONFIG_PATH;
    if (envPath && fs.existsSync(envPath)) {
      return envPath;
    }

    // Default paths to check
    const defaultPaths = [
      path.join(process.cwd(), "defaults.yaml"),
      path.join(process.cwd(), "config", "defaults.yaml"),
      path.join(process.cwd(), "..", "..", "defaults.yaml"), // For monorepo structure
    ];

    for (const configPath of defaultPaths) {
      if (fs.existsSync(configPath)) {
        return configPath;
      }
    }

    // Return default path even if file doesn't exist (for logging purposes)
    return path.join(process.cwd(), "defaults.yaml");
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
        this.watcher?.close();

        // Create new fs.watch watcher with proper options
        this.watcher = fs.watch(
          this.configPath,
          {
            persistent: true,
          },
          (eventType, filename) => {
            // Handle both 'change' and 'rename' events
            if (eventType === "change") {
              this.handleFileChange();
            } else if (eventType === "rename") {
              // Rename indicates atomic replace - file might temporarily disappear
              logger.info(
                "Configuration file was renamed/replaced, handling atomic change",
                {
                  module: "config-service",
                  method: "setupFileWatcher",
                  configPath: this.configPath,
                  eventType,
                  filename,
                },
              );

              // Wait briefly and check if file exists, then re-setup watcher
              setTimeout(() => {
                if (fs.existsSync(this.configPath)) {
                  this.handleFileChange();
                  // Re-establish watcher if file was replaced
                  this.fileWatcher!.isWatching = false;
                  this.setupFileWatcher();
                } else {
                  logger.info(
                    "Configuration file was deleted, clearing cache",
                    {
                      module: "config-service",
                      method: "setupFileWatcher",
                      configPath: this.configPath,
                    },
                  );
                  this.configCache = null;
                }
              }, 100);
            }
          },
        );

        // Handle watcher errors
        this.watcher.on("error", error => {
          logger.warn("File watcher error, recreating watcher", {
            module: "config-service",
            method: "setupFileWatcher",
            configPath: this.configPath,
            error: error instanceof Error ? error.message : String(error),
          });

          // Recreate the watcher after a delay
          setTimeout(() => {
            if (this.fileWatcher) {
              this.fileWatcher.isWatching = false;
              this.setupFileWatcher();
            }
          }, 1000);
        });

        this.fileWatcher.isWatching = true;

        logger.debug("File watcher setup successfully with fs.watch", {
          module: "config-service",
          method: "setupFileWatcher",
          configPath: this.configPath,
        });
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

  private handleFileChange(): void {
    // Clear existing timeout to debounce rapid changes
    if (this.watchTimeout) {
      clearTimeout(this.watchTimeout);
    }

    this.watchTimeout = setTimeout(() => {
      logger.info("Configuration file changed, clearing cache", {
        module: "config-service",
        method: "handleFileChange",
        configPath: this.configPath,
      });

      this.configCache = null;

      if (this.fileWatcher) {
        this.fileWatcher.lastModified = this.getFileModifiedTime(
          this.configPath,
        );
      }
    }, this.watchDebounceDelay);
  }

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

  private substituteEnvInString(str: string): string {
    const envVarRegex = /\$\{([^}]+)\}/g;

    return str.replace(envVarRegex, (match, expression) => {
      const parsed = this.parseEnvironmentExpression(expression);
      const envValue = process.env[parsed.variable];

      if (envValue !== undefined) {
        return envValue;
      } else if (parsed.defaultValue !== undefined) {
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
    // Load YAML file
    const yamlConfig = this.loadYamlFile();

    // Apply environment variable substitution
    const substitutedConfig = this.substituteEnvironmentVariables(yamlConfig);

    // Load JSON override
    const jsonOverride = this.loadJsonOverride();

    // Merge configurations with precedence: JSON override > YAML file
    const finalConfig = this.deepMerge(substitutedConfig, jsonOverride);

    logger.info("Configuration loaded successfully", {
      module: "config-service",
      method: "loadConfiguration",
      configPath: this.configPath,
      hasYamlConfig: Object.keys(yamlConfig).length > 0,
      hasJsonOverride: Object.keys(jsonOverride).length > 0,
      yamlConfigSections: Object.keys(yamlConfig),
      finalConfigSections: Object.keys(finalConfig),
      totalConfigOptions: Object.values(finalConfig).reduce(
        (total: number, section: any) =>
          total +
          (section && typeof section === "object"
            ? Object.keys(section).length
            : 0),
        0,
      ),
    });

    return finalConfig;
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

  public shutdown(): void {
    if (this.watchTimeout) {
      clearTimeout(this.watchTimeout);
      this.watchTimeout = null;
    }

    if (this.watcher) {
      try {
        this.watcher.close();
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
