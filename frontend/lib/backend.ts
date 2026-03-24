function requiredEnv(name: "BACKEND_URL" | "BACKEND_API_KEY"): string {
  const value = process.env[name]?.trim();
  if (value) {
    return value.replace(/\/$/, "");
  }

  if (name === "BACKEND_URL" && process.env.NODE_ENV !== "production") {
    return "http://localhost:8000";
  }

  throw new Error(`${name} is not configured`);
}

export function backendUrl(path: string): string {
  const baseUrl = requiredEnv("BACKEND_URL");
  return `${baseUrl}${path}`;
}

export function backendHeaders(contentType = false): HeadersInit {
  const headers: HeadersInit = {
    "X-API-Key": requiredEnv("BACKEND_API_KEY"),
  };

  if (contentType) {
    headers["Content-Type"] = "application/json";
  }

  return headers;
}
