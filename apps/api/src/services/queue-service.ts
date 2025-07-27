import { Queue } from "bullmq";
import { logger } from "../lib/logger";
import IORedis from "ioredis";

export type QueueFunction = () => Queue<any, any, string, any, any, string>;

let scrapeQueue: Queue;
let extractQueue: Queue;
let loggingQueue: Queue;
let indexQueue: Queue;
let deepResearchQueue: Queue;
let generateLlmsTxtQueue: Queue;
let billingQueue: Queue;
let precrawlQueue: Queue;

export function createRedisConnection(): IORedis {
  return new IORedis(process.env.REDIS_URL!, {
    maxRetriesPerRequest: null,
  });
}

export const redisConnection = createRedisConnection();

export const scrapeQueueName = "{scrapeQueue}";
export const extractQueueName = "{extractQueue}";
export const loggingQueueName = "{loggingQueue}";
export const indexQueueName = "{indexQueue}";
export const generateLlmsTxtQueueName = "{generateLlmsTxtQueue}";
export const deepResearchQueueName = "{deepResearchQueue}";
export const billingQueueName = "{billingQueue}";
export const precrawlQueueName = "{precrawlQueue}";

export function getScrapeQueue(_redisConnection?: IORedis) {
  const _scrapeQueue = !scrapeQueue || _redisConnection !== undefined ? new Queue(scrapeQueueName, {
    connection: _redisConnection ?? redisConnection,
    defaultJobOptions: {
      removeOnComplete: {
        age: 3600, // 1 hour
      },
      removeOnFail: {
        age: 3600, // 1 hour
      },
    },
  }) : undefined;

  if (_redisConnection !== undefined) {
    return _scrapeQueue!;
  } else if (!scrapeQueue) {
    scrapeQueue = _scrapeQueue!;
    logger.info("Web scraper queue created");
  }

  return scrapeQueue;
}

export function getExtractQueue() {
  if (!extractQueue) {
    extractQueue = new Queue(extractQueueName, {
      connection: redisConnection,
      defaultJobOptions: {
        removeOnComplete: {
          age: 90000, // 25 hours
        },
        removeOnFail: {
          age: 90000, // 25 hours
        },
      },
    });
    logger.info("Extraction queue created");
  }
  return extractQueue;
}

export function getGenerateLlmsTxtQueue() {
  if (!generateLlmsTxtQueue) {
    generateLlmsTxtQueue = new Queue(generateLlmsTxtQueueName, {
      connection: redisConnection,
      defaultJobOptions: {
        removeOnComplete: {
          age: 90000, // 25 hours
        },
        removeOnFail: {
          age: 90000, // 25 hours
        },
      },
    });
    logger.info("LLMs TXT generation queue created");
  }
  return generateLlmsTxtQueue;
}

export function getDeepResearchQueue() {
  if (!deepResearchQueue) {
    deepResearchQueue = new Queue(deepResearchQueueName, {
      connection: redisConnection,
      defaultJobOptions: {
        removeOnComplete: {
          age: 90000, // 25 hours
        },
        removeOnFail: {
          age: 90000, // 25 hours
        },
      },
    });
    logger.info("Deep research queue created");
  }
  return deepResearchQueue;
}

export function getBillingQueue() {
  if (!billingQueue) {
    billingQueue = new Queue(billingQueueName, {
      connection: redisConnection,
      defaultJobOptions: {
        removeOnComplete: {
          age: 60, // 1 minute
        },
        removeOnFail: {
          age: 3600, // 1 hour
        },
      },
    });
    logger.info("Billing queue created");
  }
  return billingQueue;
}

export function getPrecrawlQueue() {
  if (!precrawlQueue) {
    precrawlQueue = new Queue(precrawlQueueName, {
      connection: redisConnection,
      defaultJobOptions: {
        removeOnComplete: {
          age: 24 * 60 * 60, // 1 day
        },
        removeOnFail: {
          age: 24 * 60 * 60, // 1 day
        },
      },
    });
    logger.info("Precrawl queue created");
  }
  return precrawlQueue;
}
