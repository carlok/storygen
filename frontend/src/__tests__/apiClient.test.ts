import { ApiError, apiFetch } from "@/api/client";

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("sends session credentials and JSON headers", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ email: "user@example.com" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await apiFetch<{ email: string }>("/api/me", {
      headers: { "X-Trace": "test" },
    });

    expect(result).toEqual({ email: "user@example.com" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/me",
      expect.objectContaining({
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Trace": "test",
        },
      }),
    );
  });

  test("throws ApiError with server-provided detail", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Forbidden" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(apiFetch("/api/admin/users")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      detail: "Forbidden",
      message: "Forbidden",
    });
  });

  test("uses HTTP status text when an error body is not JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("bad gateway", { status: 502 }),
    );

    await expect(apiFetch("/api/unstable")).rejects.toEqual(
      new ApiError(502, "HTTP 502"),
    );
  });

  test("returns undefined for 204 responses", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    await expect(
      apiFetch("/auth/logout", { method: "POST" }),
    ).resolves.toBeUndefined();
  });
});
