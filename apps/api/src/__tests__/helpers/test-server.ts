import express from "express";
import { Server } from "http";

export interface TestEchoServer {
  port: number;
  url: string;
  server: Server;
  close: () => Promise<void>;
}

export async function createTestEchoServer(): Promise<TestEchoServer> {
  const app = express();
  app.use(express.json());
  app.use(express.urlencoded({ extended: true }));

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
          <div id="headers">${JSON.stringify(req.headers).replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
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
          url: `http://localhost:${port}`,
          server,
          close: () =>
            new Promise(resolveClose => {
              server.close(error => {
                if (error) {
                  console.error("Test server close error:", error);
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
