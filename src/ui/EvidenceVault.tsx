import * as React from "react";
import { fetchPages, type PageSummary, type Stats } from "./api";
import { TierBadge } from "./dashboard/components";
import type { Citation, Tier } from "./types";

type FilterTier = Tier | "All";

const FILTERS: FilterTier[] = ["All", "S1", "S2", "S3"];

function basename(path: string) {
  return path.split(/[\\/]/).pop() || path;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat().format(value);
}

export function EvidenceVault({
  stats,
  onOpenCitation,
}: {
  stats: Stats | null;
  onOpenCitation: (citation: Citation) => void;
}) {
  const [filter, setFilter] = React.useState<FilterTier>("All");
  const [pages, setPages] = React.useState<PageSummary[]>([]);
  const [message, setMessage] = React.useState("");

  React.useEffect(() => {
    let cancelled = false;
    fetchPages(filter)
      .then((nextPages) => {
        if (!cancelled) {
          setPages(nextPages);
          setMessage("");
        }
      })
      .catch(() => {
        if (!cancelled) setMessage("Vault inventory unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  function openPage(page: PageSummary) {
    if (page.tier === "S3") {
      setMessage("S3 content sealed");
      return;
    }
    if (page.first_chunk) {
      onOpenCitation(page.first_chunk);
    } else {
      setMessage("No chunk available for this page");
    }
  }

  return (
    <section className="vault-screen" aria-label="Evidence Vault">
      <header className="screen-header">
        <div>
          <p className="eyebrow">Evidence Vault</p>
          <h2>Evidence Vault - {formatNumber(stats?.pages ?? 0)} pages, {formatNumber(stats?.chunks ?? 0)} chunks</h2>
        </div>
        <div className="segmented">
          {FILTERS.map((tier) => (
            <button
              key={tier}
              type="button"
              className={filter === tier ? "is-active" : ""}
              onClick={() => setFilter(tier)}
            >
              {tier}
            </button>
          ))}
        </div>
      </header>

      {message ? <div className="inline-alert">{message}</div> : null}

      <div className="vault-table" role="table" aria-label="Vault pages">
        <div className="vault-table__head" role="row">
          <span>Tier</span>
          <span>File</span>
          <span>Chunks</span>
          <span>Lines</span>
        </div>
        {pages.map((page) => {
          const sealed = page.tier === "S3";
          return (
            <button
              key={page.page_path}
              type="button"
              className={sealed ? "vault-row vault-row--sealed" : "vault-row"}
              onClick={() => openPage(page)}
            >
              <TierBadge tier={page.tier} />
              <span className="vault-row__file">{basename(page.page_path)}</span>
              <span>{sealed ? <b>SEALED</b> : formatNumber(page.chunk_count)}</span>
              <span>{sealed ? "content sealed" : formatNumber(page.line_count)}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
