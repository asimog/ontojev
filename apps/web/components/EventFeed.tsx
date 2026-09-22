"use client";

import { useEffect, useRef, useState } from "react";
import { JudgmentVector } from "@/components/JudgmentVector";
import { formatLabel, formatTime } from "@/lib/format";
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
      <p className="sr-only" aria-live="polite">{events.length} canonical events rendered</p>
      <div ref={container} onScroll={onScroll} className="event-feed" data-testid="event-feed">
        {events.map((event) => (
          <details key={event.event_id} className="event" data-event-id={event.event_id}>
            <summary>
              <span className="sequence">{String(event.sequence).padStart(3, "0")}</span>
              <span className="event-time">{formatTime(event.timestamp)}</span>
              <span>{event.stage ?? "RUN"}</span>
              <span className="event-type">{event.type}</span>
              <strong>{event.message}</strong>
            </summary>
            <EventDetail event={event} />
          </details>
        ))}
      </div>
    </section>
  );
}

function EventDetail({ event }: { event: RunEvent }) {
  const entries = Object.entries(event.data);
  const vector = event.data.judgment_vector;
  return (
    <div className="event-detail">
      <p className="event-meta">{event.type}{event.iteration != null ? ` · iteration ${event.iteration}` : ""}{event.candidate_id ? ` · candidate ${event.candidate_id.slice(0, 8)}` : ""}</p>
      {isJudgmentVector(vector) && <JudgmentVector vector={vector} />}
      <dl className="event-data">
        {entries.slice(0, 40).map(([key, value]) => (
          <div key={key}><dt>{formatLabel(key)}</dt><dd>{renderValue(value)}</dd></div>
        ))}
      </dl>
      {entries.length > 40 && <p className="fine">Showing 40 of {entries.length} payload fields; the durable event retains all of them.</p>}
    </div>
  );
}

function isJudgmentVector(value: unknown): value is Parameters<typeof JudgmentVector>[0]["vector"] {
  return typeof value === "object" && value !== null;
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "unknown";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "unknown";
  if (typeof value === "string") return value.length > 400 ? `${value.slice(0, 400)}…` : value;
  const text = JSON.stringify(value);
  return text.length > 400 ? `${text.slice(0, 400)}…` : text;
}
