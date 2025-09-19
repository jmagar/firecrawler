import { logger } from "../logger";

export class SecurityAuditLogger {
  private static enabled = process.env.SECURITY_AUDIT_LOG === "true";

  static logEnvAccess(varName: string, context: string): void {
    if (!this.enabled) return;

    const audit = {
      type: "ENV_ACCESS",
      variable: varName,
      context,
      timestamp: new Date().toISOString(),
      sensitive: this.isSensitive(varName),
    };

    logger.info("[SECURITY_AUDIT] Environment variable access", audit);
  }

  static logPathAccess(path: string, validated: boolean): void {
    if (!this.enabled) return;

    const audit = {
      type: "PATH_ACCESS",
      path,
      validated,
      timestamp: new Date().toISOString(),
    };

    logger.info("[SECURITY_AUDIT] Path access attempt", audit);
  }

  static logConfigChange(path: string, user?: string): void {
    if (!this.enabled) return;

    const audit = {
      type: "CONFIG_CHANGE",
      path,
      user: user || "system",
      timestamp: new Date().toISOString(),
    };

    logger.info("[SECURITY_AUDIT] Configuration change", audit);
  }

  static logUnauthorizedAccess(
    type: string,
    details: Record<string, any>,
  ): void {
    if (!this.enabled) return;

    const audit = {
      type: "UNAUTHORIZED_ACCESS",
      subtype: type,
      details,
      timestamp: new Date().toISOString(),
      severity: "HIGH",
    };

    logger.warn("[SECURITY_AUDIT] Unauthorized access attempt", audit);
  }

  static logSanitization(
    type: string,
    original: string,
    sanitized: string,
  ): void {
    if (!this.enabled) return;

    const audit = {
      type: "SANITIZATION",
      subtype: type,
      originalLength: original.length,
      sanitizedLength: sanitized.length,
      charactersRemoved: original.length - sanitized.length,
      timestamp: new Date().toISOString(),
    };

    if (audit.charactersRemoved > 0) {
      logger.warn("[SECURITY_AUDIT] Content sanitized", audit);
    } else {
      logger.debug("[SECURITY_AUDIT] Content passed sanitization", audit);
    }
  }

  private static isSensitive(varName: string): boolean {
    const sensitivePatterns = [
      "KEY",
      "SECRET",
      "PASSWORD",
      "TOKEN",
      "CREDENTIAL",
    ];
    return sensitivePatterns.some(pattern =>
      varName.toUpperCase().includes(pattern),
    );
  }
}
