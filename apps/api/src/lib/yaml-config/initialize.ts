import { logger } from "../logger";

/**
 * Early initialization hook for YAML configuration service.
 * This function is called during application startup after dotenv but before other services.
 * It ensures the ConfigService singleton is ready before middleware needs it.
 */
export async function initializeYamlConfig(): Promise<void> {
  try {
    logger.info("Initializing YAML configuration service...");

    // Try to import and initialize ConfigService
    // This will fail gracefully if dependencies are missing
    const configServicePromise =
      require("../../services/config-service").default;

    // Get the singleton instance (await the promise)
    const instance = await configServicePromise;

    // Load initial configuration and log details
    const config = await instance.getConfiguration();
    const isObject = config && typeof config === "object";
    const configKeys = isObject
      ? Object.keys(config as Record<string, any>)
      : [];
    const hasConfiguration = configKeys.length > 0;

    logger.info("YAML configuration service initialized successfully", {
      module: "yaml-config",
      method: "initializeYamlConfig",
      configPath: instance.configPath || "not found",
      hasConfiguration,
      configSections: configKeys,
      totalConfigOptions: hasConfiguration
        ? Object.values(config).reduce(
            (total: number, section: any) =>
              total +
              (section && typeof section === "object"
                ? Object.keys(section).length
                : 0),
            0,
          )
        : 0,
    });
  } catch (error) {
    // Graceful error handling - log error but don't break startup
    // The application should continue working with environment variables
    const errorMessage = error instanceof Error ? error.message : String(error);

    if (/\bjs-yaml\b/i.test(errorMessage)) {
      logger.info(
        "YAML configuration service dependencies not installed, skipping initialization",
      );
      logger.info(
        "Install 'js-yaml' and '@types/js-yaml' to enable YAML configuration features",
      );
    } else {
      logger.warn("Failed to initialize YAML configuration service", {
        error: errorMessage,
        stack: error instanceof Error ? error.stack : undefined,
      });
    }

    logger.info(
      "Application will continue with environment variable configuration",
    );
  }
}

// Automatically initialize when this module is imported
initializeYamlConfig().catch(error => {
  logger.warn(
    "Failed to initialize YAML configuration service during module import",
    {
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    },
  );
});
