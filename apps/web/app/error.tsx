"use client";
export default function ErrorPage({ reset }: { error: Error; reset: () => void }) { return <div className="api-warning"><h2>The interface could not render this record.</h2><button onClick={reset}>Try again</button></div>; }

