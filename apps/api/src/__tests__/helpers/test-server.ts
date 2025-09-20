import express from "express";
import { Server } from "http";

export interface TestEchoServer {
  port: number;
  url: string;
  server: Server;
  close: () => Promise<void>;
}

export function createTestEchoServer(): Promise<TestEchoServer> {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "1mb" }));
  app.use(express.urlencoded({ extended: true, limit: "1mb" }));

  // Echo headers endpoint (mimics httpbin.org/headers)
  app.get("/headers", (req, res) => {
    res.json({
      headers: req.headers,
    });
  });

  // Generic echo endpoint for other tests
  app.all("/echo", (req, res) => {
    res.json({
      method: req.method,
      headers: req.headers,
      body: req.body,
      query: req.query,
      path: req.path,
      url: req.url,
    });
  });

  // Simple HTML page for scraping tests
  app.get("/", (req, res) => {
    res.send(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Test Page</title>
        </head>
        <body>
          <h1>Test Echo Server</h1>
          <p>This is a test server for E2E tests.</p>
          <div id="headers">${JSON.stringify(req.headers).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
        </body>
      </html>
    `);
  });

  return new Promise((resolve, reject) => {
    const server = app.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (address && typeof address === "object") {
        const port = address.port;
        resolve({
          port,
          url: `http://127.0.0.1:${port}`,
          server,
          close: () =>
            new Promise((resolveClose, rejectClose) => {
              server.close(error => {
                if (error) {
                  console.error("Test server close error:", error);
                  return rejectClose(error);
                }
                resolveClose();
              });
            }),
        });
      } else {
        server.close(() => {
          reject(new Error("Test server failed to obtain a TCP address"));
        });
      }
    });

    server.on("error", error => {
      console.error("Test server startup error:", error);
      reject(error);
    });
  });
}
