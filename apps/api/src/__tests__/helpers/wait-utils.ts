export async function waitUntil(
  predicate: () => Promise<boolean> | boolean,
  timeoutMs = 10000,
  intervalMs = 100,
  description?: string,
): Promise<void> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    try {
      const result = await predicate();
      if (result) {
        return;
      }
    } catch (error) {
      // Ignore errors during polling, continue checking
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw new Error(
    `Timeout waiting for condition${
      description ? `: ${description}` : ""
    } after ${timeoutMs}ms`,
  );
}

export async function waitForConfigReload(
  configService: any,
  expectedConfig: (config: any) => boolean,
  timeoutMs = 5000,
): Promise<void> {
  await waitUntil(
    async () => {
      // Clear cache to get fresh config
      configService.clearCache();
      const config = await configService.getConfiguration();
      return expectedConfig(config);
    },
    timeoutMs,
    100,
    "configuration reload",
  );
}
