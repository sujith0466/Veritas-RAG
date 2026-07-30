import { test, expect, Page } from "@playwright/test";
import { login } from "./utils/helpers";

async function injectProbe(page: Page) {
  await page.evaluate(() => {
    const timeline: any[] = [];
    (window as any).__RC_TIMELINE = timeline;
    const log = (event: string, detail: Record<string, unknown> = {}) => {
      const entry = { t: Date.now(), event, ...detail };
      timeline.push(entry);
    };

    let lastProseLen = -1;
    let lastProseCount = -1;
    const poll = () => {
      const els = document.querySelectorAll("div.prose");
      const count = els.length;
      const lastLen = count > 0
        ? (els[els.length - 1] as HTMLElement).innerText.trim().length
        : 0;
      if (count !== lastProseCount || lastLen !== lastProseLen) {
        log("DOM_CHANGE", { prose_count: count, last_prose_len: lastLen });
        if (lastProseLen > 20 && lastLen === 0) {
          log("WIPE_DETECTED", { was: lastProseLen, now: 0 });
        }
        if (lastProseLen > 20 && lastLen < lastProseLen && lastLen < 20) {
          log("PARTIAL_WIPE", { was: lastProseLen, now: lastLen });
        }
        lastProseCount = count;
        lastProseLen = lastLen;
      }
    };
    (window as any).__RC_POLL = setInterval(poll, 100);

    const origFetch = window.fetch.bind(window);
    (window as any).fetch = async function(input: RequestInfo | URL, init?: RequestInit) {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/stream")) {
        log("FETCH_STREAM_START", { url });
        const resp = await origFetch(input, init);
        const origBody = resp.body!;
        const reader = origBody.getReader();
        let byteCount = 0;
        const proxyStream = new ReadableStream({
          async pull(controller) {
            try {
              const { done, value } = await reader.read();
              if (done) {
                log("FETCH_STREAM_DONE", { total_bytes: byteCount });
                controller.close();
              } else {
                byteCount += value.byteLength;
                controller.enqueue(value);
              }
            } catch (e) {
              log("FETCH_STREAM_ERROR", { error: String(e) });
              controller.error(e);
            }
          },
          cancel() {
            log("FETCH_STREAM_CANCELLED");
            reader.cancel();
          }
        });
        return new Response(proxyStream, {
          status: resp.status,
          statusText: resp.statusText,
          headers: resp.headers
        });
      }
      return origFetch(input, init);
    };

    const OrigXHR = window.XMLHttpRequest;
    (window as any).XMLHttpRequest = class ProxiedXHR extends OrigXHR {
      private _url: string = "";
      open(method: string, url: string, ...rest: any[]) {
        this._url = url;
        return super.open(method, url, ...rest);
      }
      send(...args: any[]) {
        const url = this._url;
        if (url.includes("/messages")) {
          log("XHR_MESSAGES_SENT", { url });
          this.addEventListener("load", () => {
            try {
              const body = JSON.parse(this.responseText);
              const msgs = body?.data ?? [];
              log("XHR_MESSAGES_RESOLVED", {
                url,
                messages_count: msgs.length,
                roles: msgs.map((m: any) => m.role)
              });
            } catch {
              log("XHR_MESSAGES_RESOLVED_UNPARSED", { status: this.status });
            }
          });
        } else if (url.includes("/chat/sessions") && !url.includes("/messages") && !url.includes("/stream")) {
          log("XHR_SESSION_SENT", { url });
          this.addEventListener("load", () => {
            try {
              const body = JSON.parse(this.responseText);
              const session = body?.data;
              log("XHR_SESSION_RESOLVED", {
                url,
                session_id: session?.id,
                has_messages_field: "messages" in (session ?? {})
              });
            } catch {
              log("XHR_SESSION_RESOLVED_UNPARSED", { status: this.status });
            }
          });
        }
        return super.send(...args);
      }
    };

    log("PROBE_INJECTED");
  });
}

test("RC_PROBE v3: Race condition with existing session precondition", async ({ page }) => {
  test.setTimeout(120000);
  await login(page, "user");

  if (!page.url().includes("/chat/")) {
    const sessionListResp = await page.waitForResponse(
      resp => resp.url().includes("/api/v1/chat/sessions") && resp.status() === 200,
      { timeout: 20000 }
    ).catch(() => null);

    if (sessionListResp) {
      try {
        const body = await sessionListResp.json();
        const sessions: any[] = body?.data ?? [];
        if (sessions.length > 0) {
          const existingId = sessions[0].id;
          console.log("[SETUP] Navigating to existing session:", existingId);
          await page.goto("/chat/" + existingId);
          await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 15000 });
          await page.waitForResponse(
            resp => resp.url().includes("/messages") && resp.status() === 200,
            { timeout: 15000 }
          ).catch(() => {});
          console.log("[SETUP] Existing session loaded. activeSession.id is now primed.");
        }
      } catch {}
    }
  }

  await page.goto("/chat");
  await expect(page).toHaveURL(/.*\/chat$/, { timeout: 10000 });
  console.log("[SETUP] Navigated to /chat (no session). activeSession should be null.");

  await page.waitForResponse(
    resp => resp.url().includes("/api/v1/chat/sessions") && resp.status() === 200,
    { timeout: 15000 }
  ).catch(() => {});

  const t0 = Date.now();
  await injectProbe(page);
  console.log("[+" + (Date.now() - t0) + "ms] PROBE INJECTED");

  const question = "What are the core capabilities of RAGuard?";
  const input = page.locator("textarea").first();
  await expect(input).toBeVisible({ timeout: 10000 });
  await input.click();
  await input.fill(question);

  const submitBtn = page.locator("button[type=\"submit\"]").first();
  await expect(submitBtn).toBeEnabled({ timeout: 5000 });
  await submitBtn.click();
  console.log("[+" + (Date.now() - t0) + "ms] SUBMIT CLICKED");

  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 15000 });
  console.log("[+" + (Date.now() - t0) + "ms] URL: " + page.url());

  await page.waitForResponse(
    resp => resp.url().includes("/stream") && resp.status() < 500,
    { timeout: 30000 }
  ).catch(() => {});
  console.log("[+" + (Date.now() - t0) + "ms] Stream response received");

  let finalProseLen = 0;
  let wipeDetectedInPoll = false;
  let streamCompleted = false;

  for (let i = 0; i < 45; i++) {
    await page.waitForTimeout(2000);
    const snap = await page.evaluate(() => {
      const els = document.querySelectorAll("div.prose");
      const count = els.length;
      const lastLen = count > 0
        ? (els[els.length - 1] as HTMLElement).innerText.trim().length
        : 0;
      const streamingDots = document.querySelectorAll("[class*=\"animate-\"]").length;
      return { count, lastLen, streamingDots };
    });

    console.log(
      "[+" + (Date.now() - t0) + "ms] POLL #" + (i + 1) +
      ": prose_count=" + snap.count +
      ", last_len=" + snap.lastLen +
      ", animating_els=" + snap.streamingDots
    );

    if (snap.lastLen > 20 && !streamCompleted) {
      streamCompleted = true;
      console.log("[+" + (Date.now() - t0) + "ms] *** STREAM CONTENT APPEARED (" + snap.lastLen + " chars) ***");
      finalProseLen = snap.lastLen;

      for (let j = 0; j < 4; j++) {
        await page.waitForTimeout(1000);
        const postSnap = await page.evaluate(() => {
          const els = document.querySelectorAll("div.prose");
          const count = els.length;
          const lastLen = count > 0
            ? (els[els.length - 1] as HTMLElement).innerText.trim().length
            : 0;
          return { count, lastLen };
        });
        console.log(
          "[+" + (Date.now() - t0) + "ms] POST-STREAM WATCH #" + (j + 1) +
          ": prose_count=" + postSnap.count + ", last_len=" + postSnap.lastLen
        );
        if (postSnap.lastLen < finalProseLen && postSnap.lastLen < 20) {
          wipeDetectedInPoll = true;
          console.log("!!! WIPE DETECTED IN DOM POLL: was=" + finalProseLen + " now=" + postSnap.lastLen);
        }
      }
      break;
    }
  }

  const timeline = await page.evaluate(() => (window as any).__RC_TIMELINE ?? []);
  await page.evaluate(() => clearInterval((window as any).__RC_POLL));

  const t_first = timeline.length > 0 ? timeline[0].t : t0;

  console.log("\n======= DOM STATE TIMELINE =======");
  for (const entry of timeline) {
    const relT = entry.t - t_first;
    const detail = Object.entries(entry)
      .filter(([k]) => k !== "t" && k !== "event")
      .map(([k, v]) => k + "=" + JSON.stringify(v))
      .join("  ");
    console.log("[+" + String(relT).padStart(6) + "ms]  " + entry.event + (detail ? "  |  " + detail : ""));
  }

  const wipeEvents = timeline.filter((e: any) => e.event === "WIPE_DETECTED" || e.event === "PARTIAL_WIPE");
  const fetchStreamDone = timeline.find((e: any) => e.event === "FETCH_STREAM_DONE");

  console.log("\n======= ANALYSIS =======");
  console.log("Stream completed (FETCH_STREAM_DONE):", !!fetchStreamDone);
  console.log("Wipe events in probe:", wipeEvents.length);
  if (wipeEvents.length > 0) {
    for (const w of wipeEvents) {
      console.log("  !!! " + w.event + ": was=" + w.was + " now=" + w.now + " at +" + (w.t - t_first) + "ms");
    }
    expect(wipeEvents.length).toBe(0);
  } else {
      console.log("No wipe detected. Fix is successful.");
  }
  console.log("Wipe detected in poll loop:", wipeDetectedInPoll);
  console.log("Final prose content length:", finalProseLen);
  console.log("========================\n");

  expect(timeline.length).toBeGreaterThan(0);
});
