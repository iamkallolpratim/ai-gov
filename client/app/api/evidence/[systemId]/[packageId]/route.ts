import { NextRequest, NextResponse } from "next/server";

/**
 * Streams an evidence package to the browser.
 *
 * The backend presigns object-storage URLs against its own view of MinIO, which under
 * docker compose is `http://minio:9000` — a hostname only resolvable inside the compose
 * network. Linking to it directly would give every user a dead download.
 *
 * Rewriting the host is not an option: S3 signatures cover the Host header, so a
 * rewritten URL fails the signature check. Instead this handler runs server-side, where
 * `minio:9000` *does* resolve, fetches the object with the signature intact, and pipes
 * the bytes back.
 *
 * Running `next dev` on the host instead of in compose? Add `127.0.0.1 minio` to your
 * hosts file (see client/README.md).
 */

const INTERNAL_API_URL = (
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000"
).replace(/\/$/, "");

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ systemId: string; packageId: string }> },
) {
  const { systemId, packageId } = await context.params;
  const kind = request.nextUrl.searchParams.get("kind") === "json" ? "json" : "pdf";

  // The browser holds the token, so forward it; with AUTH_DISABLED there is none to send.
  const authorization = request.headers.get("authorization");
  const headers: HeadersInit = authorization ? { Authorization: authorization } : {};

  let metadataResponse: Response;
  try {
    metadataResponse = await fetch(
      `${INTERNAL_API_URL}/api/v1/systems/${systemId}/evidence/${packageId}`,
      { headers, cache: "no-store" },
    );
  } catch {
    return NextResponse.json(
      { error: "Could not reach the API to look up this evidence package." },
      { status: 502 },
    );
  }

  if (!metadataResponse.ok) {
    return NextResponse.json(
      { error: "Evidence package not found, or you do not have access to it." },
      { status: metadataResponse.status },
    );
  }

  const body = (await metadataResponse.json()) as {
    data?: { status?: string; file_url?: string | null; json_url?: string | null };
  };
  const pkg = body.data;

  if (!pkg || pkg.status !== "completed") {
    return NextResponse.json(
      { error: `This package is not ready to download (status: ${pkg?.status ?? "unknown"}).` },
      { status: 409 },
    );
  }

  const objectUrl = kind === "json" ? pkg.json_url : pkg.file_url;
  if (!objectUrl) {
    return NextResponse.json({ error: `No ${kind.toUpperCase()} file on this package.` }, { status: 404 });
  }

  let objectResponse: Response;
  try {
    objectResponse = await fetch(objectUrl, { cache: "no-store" });
  } catch (cause) {
    const detail = cause instanceof Error ? (cause.cause ?? cause).toString() : String(cause);
    console.error("[evidence-proxy] object fetch failed", { objectUrl, detail });
    return NextResponse.json(
      {
        error:
          "Could not reach object storage. If you are running the client outside docker " +
          "compose, add `127.0.0.1 minio` to your hosts file.",
        detail,
      },
      { status: 502 },
    );
  }

  if (!objectResponse.ok || !objectResponse.body) {
    return NextResponse.json(
      { error: "Object storage rejected the download. The signed link may have expired — regenerate the package." },
      { status: 502 },
    );
  }

  const filename = `evidence-${packageId.slice(0, 8)}.${kind}`;
  return new NextResponse(objectResponse.body, {
    status: 200,
    headers: {
      "Content-Type": kind === "json" ? "application/json" : "application/pdf",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
