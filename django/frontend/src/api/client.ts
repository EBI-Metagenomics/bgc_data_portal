const basePath =
  document.querySelector('meta[name="base-path"]')?.getAttribute("content") ??
  "";

const API_BASE = `${basePath}/api/discovery`;

function getCsrfToken(): string | null {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match?.[1] ?? null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** A query-string value; ``undefined`` / ``null`` / ``""`` entries are dropped. */
export type QueryParamValue = string | number | boolean | null | undefined;

/**
 * Constraint for a typed query-params object. Written as a mapped type over
 * ``keyof P`` (rather than a string index signature) so plain interfaces such
 * as ``IbgcRosterParams`` satisfy it without a cast.
 */
export type QueryParams<P> = { [K in keyof P]?: QueryParamValue };

interface RequestOptions<P> {
  method?: "GET" | "POST" | "DELETE";
  params?: P;
  headers?: Record<string, string>;
  body?: BodyInit;
}

/**
 * Single transport core shared by every helper below: builds the URL under
 * ``API_BASE``, appends non-empty query params, attaches the Django CSRF
 * header on mutating methods and turns any non-2xx response into ``ApiError``.
 */
async function request<P extends QueryParams<P>>(
  path: string,
  { method = "GET", params, headers = {}, body }: RequestOptions<P> = {},
): Promise<Response> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params) as [
      string,
      QueryParamValue,
    ][]) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  const finalHeaders = { ...headers };
  if (method !== "GET") {
    const csrf = getCsrfToken();
    if (csrf) finalHeaders["X-CSRFToken"] = csrf;
  }
  const response = await fetch(url.toString(), {
    method,
    headers: finalHeaders,
    body,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "Unknown error");
    throw new ApiError(response.status, text);
  }
  return response;
}

const jsonBody = (body: unknown) => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export async function apiGet<T, P extends QueryParams<P> = Record<string, never>>(
  path: string,
  params?: P,
): Promise<T> {
  const response = await request(path, { params });
  return response.json() as Promise<T>;
}

/** GET with custom headers — used to thread X-Asset-Token through ``/ibgcs/{id}/``. */
export async function apiGetWithHeaders<
  T,
  P extends QueryParams<P> = Record<string, never>,
>(
  path: string,
  extraHeaders: Record<string, string>,
  params?: P,
): Promise<T> {
  const response = await request(path, { params, headers: extraHeaders });
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await request(path, { method: "POST", ...jsonBody(body) });
  return response.json() as Promise<T>;
}

export async function apiPostBlob(path: string, body: unknown): Promise<Blob> {
  const response = await request(path, { method: "POST", ...jsonBody(body) });
  return response.blob();
}

/**
 * POST a multipart/form-data payload (file uploads). Skips JSON serialisation
 * so the browser sets the multipart boundary header itself.
 */
export async function apiPostMultipart<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const response = await request(path, { method: "POST", body: formData });
  return response.json() as Promise<T>;
}

/** Fire-and-forget DELETE; returns true on 2xx (204 included). */
export async function apiDelete(path: string): Promise<boolean> {
  await request(path, { method: "DELETE" });
  return true;
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
