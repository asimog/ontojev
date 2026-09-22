"use client";

import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "@/lib/types";

export function EventFeed({ events }: { events: RunEvent[] }) {
  const container = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);
  const [unseen, setUnseen] = useState(0);
  const previousCount = useRef(0);

  useEffect(() => {
    const added = events.length - previousCount.current;
    previousCount.current = events.length;
    if (added <= 0) return;
    if (following && container.current) container.current.scrollTop = container.current.scrollHeight;
    else setUnseen((count) => count + added);
  }, [events, following]);

  const onScroll = () => {
    const node = container.current;
    if (!node) return;
    const atBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 32;
    setFollowing(atBottom);
    if (atBottom) setUnseen(0);
  };

  const resume = () => {
    setFollowing(true);
    setUnseen(0);
    if (container.current) container.current.scrollTop = container.current.scrollHeight;
  };

  return (
    <section className="panel event-section">
      <div className="row spread"><div><div className="eyebrow">CANONICAL RUNEVENT STREAM</div><h2>Live event feed</h2></div>{unseen > 0 && <button onClick={resume}>{unseen} new events ↓</button>}</div>
      <div ref={container} onScroll={onScroll} className="event-feed" data-testid="event-feed">
        {events.map((event) => <details key={event.event_id} className="event"><summary><span className="sequence">{String(event.sequence).padStart(3, "0")}</span><span>{event.stage ?? "RUN"}</span><strong>{event.message}</strong></summary><pre>{JSON.stringify(event.data, null, 2)}</pre></details>)}
      </div>
    </section>
  );
}

