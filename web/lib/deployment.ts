export function applicationBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || "";
}

export function applicationPath(path: string) {
  return `${applicationBasePath()}${path}`;
}

export function withoutBasePath(path: string) {
  const base = applicationBasePath();
  if (base && (path === base || path.startsWith(`${base}/`) ||
    path.startsWith(`${base}?`) || path.startsWith(`${base}#`))) {
    const stripped = path.slice(base.length);
    return stripped.startsWith("/") ? stripped : `/${stripped}`;
  }
  return path;
}

export function isPublicDemo() {
  return process.env.NEXT_PUBLIC_PUBLIC_DEMO === "true";
}

export function exampleApiBaseUrl() {
  return `${process.env.NEXT_PUBLIC_DEMO_ORIGIN || "http://127.0.0.1:8000"}${applicationPath("/api/v1")}`;
}
