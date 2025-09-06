import "dotenv/config";
import { logger as _logger } from "../../lib/logger";
import { processJobInternal } from "./scrape-worker";
import { scrapeQueue, nuqGetLocalMetrics, nuqHealthCheck } from "./nuq";
import Express from "express";
import { _ } from "ajv";

(async () => {
  let isShuttingDown = false;
  const myLock = crypto.randomUUID();

  const app = Express();

  app.get("/metrics", (_, res) =>
    res.contentType("text/plain").send(nuqGetLocalMetrics()),
  );
  app.get("/health", async (_, res) => {
    if (await nuqHealthCheck()) {
      res.status(200).send("OK");
    } else {
      res.status(500).send("Not OK");
    }
  });

  const server = app.listen(
    Number(process.env.NUQ_WORKER_PORT ?? process.env.PORT ?? 3000),
    () => {
      _logger.info("NuQ worker metrics server started");
    },
  );

  function shutdown() {
    isShuttingDown = true;
  }

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  let noJobTimeout = 500;

  while (!isShuttingDown) {
    const job = await scrapeQueue.getJobToProcess(myLock);

    if (job === null) {
      _logger.info("No jobs to process", { module: "nuq/metrics" });
      await new Promise(resolve => setTimeout(resolve, noJobTimeout));
      noJobTimeout = Math.min(noJobTimeout * 2, 10000);
      continue;
    }

    noJobTimeout = 500;

    const logger = _logger.child({
      module: "nuq-worker",
      scrapeId: job.id,
      zeroDataRetention: job.data?.zeroDataRetention ?? false,
    });

    logger.info("Acquired job");

    const lockRenewInterval = setInterval(async () => {
      logger.info("Renewing lock");
      if (!(await scrapeQueue.renewLock(job.id, myLock, logger))) {
        logger.warn("Failed to renew lock");
        clearInterval(lockRenewInterval);
        return;
      }
      logger.info("Renewed lock");
    }, 15000);

    let processResult:
      | { ok: true; data: Awaited<ReturnType<typeof processJobInternal>> }
      | { ok: false; error: any };

    try {
      processResult = { ok: true, data: await processJobInternal(job) };
    } catch (error) {
      processResult = { ok: false, error };
    }

    clearInterval(lockRenewInterval);

    if (processResult.ok) {
      if (
        !(await scrapeQueue.jobFinish(
          job.id,
          myLock,
          processResult.data,
          logger,
        ))
      ) {
        logger.warn("Could not update job status");
      }
    } else {
      if (
        !(await scrapeQueue.jobFail(
          job.id,
          myLock,
          processResult.error instanceof Error
            ? processResult.error.message
            : typeof processResult.error === "string"
              ? processResult.error
              : JSON.stringify(processResult.error),
          logger,
        ))
      ) {
        logger.warn("Could not update job status");
      }
    }
  }

  _logger.info("NuQ worker shutting down");

  server.close(async () => {
    await scrapeQueue.shutdown();
    _logger.info("NuQ worker shut down");
    process.exit(0);
  });
})();
