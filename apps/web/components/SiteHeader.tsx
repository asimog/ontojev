"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/runs", label: "Runs" },
  { href: "/dossiers", label: "Dossiers" },
  { href: "/system", label: "System" },
];

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="site-header">
      <Link href="/" className="brand" aria-label="OntoJev home">
        <span className="brand-mark">OJ</span>
        <span>
          <strong>OntoJev</strong>
          <small>Target discovery observatory</small>
        </span>
      </Link>
      <nav className="nav" aria-label="Primary">
        {LINKS.map((link) => {
          const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <Link key={link.href} href={link.href} aria-current={active ? "page" : undefined}>
              {link.label}
            </Link>
          );
        })}
      </nav>
      <span className="header-chip">
        <span className="status-dot" aria-hidden="true" />
        Open GDC · Jev-judged
      </span>
    </header>
  );
}
