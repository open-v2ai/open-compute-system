import { withoutBasePath } from "./deployment";

export function safeInternalPath(value: string | null | undefined, fallback: string) {
  if (value) value = withoutBasePath(value);
  if (
    !value ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    /[\\\u0000-\u001f\u007f]/.test(value)
  ) {
    return fallback;
  }
  try {
    const internalOrigin = "https://internal.invalid";
    return new URL(value, internalOrigin).origin === internalOrigin ? value : fallback;
  } catch {
    return fallback;
  }
}

export function safeExternalUrl(value: string | null | undefined) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}
