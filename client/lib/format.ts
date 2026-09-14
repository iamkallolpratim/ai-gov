import { format, formatDistanceToNow, parseISO } from "date-fns";

export function formatDate(value: string | null | undefined, pattern = "d MMM yyyy") {
  if (!value) return "—";
  try {
    return format(parseISO(value), pattern);
  } catch {
    return "—";
  }
}

export function formatDateTime(value: string | null | undefined) {
  return formatDate(value, "d MMM yyyy, HH:mm");
}

export function formatRelative(value: string | null | undefined) {
  if (!value) return "never";
  try {
    return formatDistanceToNow(parseISO(value), { addSuffix: true });
  } catch {
    return "—";
  }
}

export function formatPercent(value: number, digits = 0) {
  return `${(value * 100).toFixed(digits)}%`;
}

/** `employment_screening` → `Employment screening`. */
export function humanize(value: string | null | undefined) {
  if (!value) return "—";
  return value.replace(/[_-]/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function initials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function formatBytes(bytes: number) {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function truncate(value: string, max = 120) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}
