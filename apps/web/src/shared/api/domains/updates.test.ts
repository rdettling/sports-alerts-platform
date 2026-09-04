import { afterEach, describe, expect, it, vi } from "vitest";

import { subscribeToGameUpdates } from "./updates";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly listeners = new Map<string, EventListener>();
  closed = false;

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, listener);
  }

  close() {
    this.closed = true;
  }
}

describe("subscribeToGameUpdates", () => {
  afterEach(() => {
    FakeEventSource.instances = [];
    vi.unstubAllGlobals();
  });

  it("opens the public game stream, listens for named events, and closes", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const onUpdate = vi.fn();

    const onOpen = vi.fn();
    const close = subscribeToGameUpdates(onUpdate, onOpen);
    const source = FakeEventSource.instances[0];
    source.listeners.get("games")?.(new Event("games"));

    expect(source.url).toBe("http://localhost:8000/updates/games");
    expect(onUpdate).toHaveBeenCalledTimes(1);
    source.listeners.get("open")?.(new Event("open"));
    source.listeners.get("open")?.(new Event("open"));
    expect(onOpen).toHaveBeenCalledTimes(2);

    close();
    expect(source.closed).toBe(true);
  });

  it("falls back silently when EventSource is unavailable", () => {
    vi.stubGlobal("EventSource", undefined);
    expect(() => subscribeToGameUpdates(vi.fn(), vi.fn())()).not.toThrow();
  });
});
