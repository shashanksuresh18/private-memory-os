import * as React from "react";
import { AtomChip, KindBadge, SafetyBar, ScoreBreakdown, Sidebar, TierBadge, TopBar } from "./dashboard/components";
import { fetchStats, queryEngine, queryEngineWithAnswer, type EngineResponse, type Stats } from "./api";
import { GraphView, type GraphNode } from "./GraphView";
import { EvidenceVault } from "./EvidenceVault";
import { CRM } from "./CRM";
import { AddDocument } from "./AddDocument";
import { PrivacyRouting } from "./PrivacyRouting";
import { MOCK_CITATIONS, type Citation, type CitationAnchor, type Tier } from "./types";

type TierContext = Tier | "Auto";
type FilterTier = Tier | "All";
type AppRoute = "/command-centre" | "/graph" | "/vault" | "/memo" | "/crm" | "/add" | "/audit" | "/gbrain" | "/connectors" | "/settings";

const TIER_RANK: Record<Tier, number> = { S1: 1, S2: 2, S3: 3 };
const SEARCH_TIERS: TierContext[] = ["Auto", "S1", "S2", "S3"];
const FILTER_TIERS: FilterTier[] = ["All", "S1", "S2", "S3"];
const ROUTES = new Set<AppRoute>([
  "/command-centre",
  "/graph",
  "/vault",
  "/memo",
  "/crm",
  "/add",
  "/audit",
  "/gbrain",
  "/connectors",
  "/settings",
]);

function useTier() {
  const [tier, setTier] = React.useState<TierContext>("Auto");
  const resolvedTier: Tier = tier === "Auto" ? "S3" : tier;
  const allows = React.useCallback((citation: Citation) => {
    return TIER_RANK[citation.tier] <= TIER_RANK[resolvedTier];
  }, [resolvedTier]);
  return { tier, setTier, resolvedTier, allows };
}

function useSearch(initialTier: TierContext) {
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<Citation[]>(MOCK_CITATIONS);
  const [loading, setLoading] = React.useState(false);
  // Answer toggle: default OFF preserves existing search-only behaviour.
  const [answerOn, setAnswerOn] = React.useState(false);
  const [answer, setAnswer] = React.useState<EngineResponse | null>(null);

  const runSearch = React.useCallback(async (nextQuery: string, nextTier: TierContext) => {
    setQuery(nextQuery.trim());
    setLoading(true);
    try {
      if (answerOn) {
        const res = await queryEngineWithAnswer(nextQuery.trim(), nextTier, 10);
        setResults(res.citations);
        setAnswer(res.answer ? res : null);
      } else {
        setResults(await queryEngine(nextQuery.trim(), nextTier, 10));
        setAnswer(null);
      }
    } finally {
      setLoading(false);
    }
  }, [answerOn]);

  return { query, setQuery, results, loading, runSearch, initialTier, answerOn, setAnswerOn, answer };
}

function useStats() {
  const [stats, setStats] = React.useState<Stats | null>(null);
  React.useEffect(() => {
    let cancelled = false;
    fetchStats()
      .then((nextStats) => {
        if (!cancelled) setStats(nextStats);
      })
      .catch(() => {
        if (!cancelled) setStats(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return stats;
}

function useViewer() {
  const [citation, setCitation] = React.useState<Citation | null>(null);
  return {
    citation,
    openViewer: setCitation,
    closeViewer: () => setCitation(null),
  };
}

function usePalette(onRunSearch: (query: string, tier: TierContext) => void) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [tier, setTier] = React.useState<TierContext>("Auto");
  const [index, setIndex] = React.useState(0);
  const previewResults = React.useMemo(() => {
    const q = query.toLowerCase().trim();
    return MOCK_CITATIONS.filter((citation) => (
      !q || [citation.page_path, citation.text, citation.tier, ...citation.graph_refs].join(" ").toLowerCase().includes(q)
    ));
  }, [query]);

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
        setIndex(0);
        return;
      }
      if (!open) return;
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setIndex((value) => Math.min(value + 1, Math.max(previewResults.length - 1, 0)));
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setIndex((value) => Math.max(value - 1, 0));
      }
      if (event.key === "Enter") {
        event.preventDefault();
        onRunSearch(query, tier);
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [index, onRunSearch, open, previewResults.length, query, tier]);

  return { open, setOpen, query, setQuery, tier, setTier, index, previewResults };
}

function filename(path: string) {
  return path.split(/[\\/]/).pop() || path;
}

function preview(text: string) {
  return text.length > 200 ? `${text.slice(0, 197)}...` : text;
}

function routeFromHref(href: string): AppRoute {
  return ROUTES.has(href as AppRoute) ? (href as AppRoute) : "/command-centre";
}

function useSha(text: string | undefined) {
  const [hash, setHash] = React.useState("pending");
  React.useEffect(() => {
    if (!text) return;
    let cancelled = false;
    crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)).then((digest) => {
      if (cancelled) return;
      const hex = Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
      setHash(`${hex.slice(0, 16)}...${hex.slice(-8)}`);
    });
    return () => { cancelled = true; };
  }, [text]);
  return hash;
}

export function App() {
  const tierState = useTier();
  const search = useSearch(tierState.tier);
  const viewer = useViewer();
  const stats = useStats();
  const palette = usePalette((q, t) => {
    tierState.setTier(t);
    search.runSearch(q, t);
  });
  const [filterTier, setFilterTier] = React.useState<FilterTier>("All");
  const [route, setRoute] = React.useState<AppRoute>("/command-centre");
  // Graph node click -> retrieve that page from the engine, open the Citation Viewer.
  const onGraphSelect = React.useCallback(async (node: GraphNode) => {
    const pagePath = node.source_file ?? node.id;
    const cites = await queryEngine(pagePath, tierState.tier, 10);
    const match = cites.find((c) => c.page_path === pagePath || c.page_path.endsWith(pagePath)) ?? cites[0];
    if (match) viewer.openViewer(match);
  }, [tierState.tier, viewer]);
  // CRM row click -> retrieve that contact/company by name, open the Citation Viewer.
  const onOpenPage = React.useCallback(async (query: string, tier: Tier) => {
    const cites = await queryEngine(query, tier, 10);
    if (cites.length) viewer.openViewer(cites[0]);
  }, [viewer]);
  const visibleResults = search.results
    .filter(tierState.allows)
    .filter((citation) => filterTier === "All" || citation.tier === filterTier);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    search.runSearch(search.query, tierState.tier);
  }

  return (
    <div className="app-shell">
      <Sidebar
        pathname={route}
        stats={stats}
        onNavigate={(href) => setRoute(routeFromHref(href))}
      />
      <main className="react-dashboard" data-tier={tierState.resolvedTier}>
        <TopBar onOpenPalette={() => palette.setOpen(true)} pathname={route} stats={stats} />
        <SafetyBar
          posture={{
            cloudAllowed: false,
            modelCallUsed: false,
            liveProviderUsed: false,
            generatedMemoFilteredCount: 0,
            vaultId: "synthetic",
            vaultTier: tierState.resolvedTier,
            sessionId: "local",
          }}
        />

        {route === "/graph" ? (
          <GraphView resolvedTier={tierState.resolvedTier} onSelectNode={onGraphSelect} />
        ) : route === "/vault" ? (
          <EvidenceVault stats={stats} onOpenCitation={viewer.openViewer} />
        ) : route === "/crm" ? (
          <CRM onOpenPage={onOpenPage} />
        ) : route === "/add" ? (
          <AddDocument />
        ) : route === "/audit" ? (
          <PrivacyRouting />
        ) : route === "/command-centre" ? (
        <>
        <form className="search-shell" onSubmit={submit}>
          <input
            value={search.query}
            onChange={(event) => search.setQuery(event.target.value)}
            type="search"
            placeholder="Search citations"
            autoComplete="off"
          />
          <select value={tierState.tier} onChange={(event) => tierState.setTier(event.target.value as TierContext)}>
            {SEARCH_TIERS.map((tier) => <option key={tier} value={tier}>{tier === "Auto" ? "Auto = S3" : tier}</option>)}
          </select>
          <button
            type="button"
            className={search.answerOn ? "answer-toggle is-active" : "answer-toggle"}
            data-tier={search.answer?.answer_tier ?? tierState.resolvedTier}
            aria-pressed={search.answerOn}
            onClick={() => search.setAnswerOn((on) => !on)}
            title="Extraction answer layer (verbatim quotes only)"
          >
            Answer {search.answerOn ? "ON" : "OFF"}
          </button>
          <button type="submit">{search.loading ? "Searching" : "Search"}</button>
        </form>

        <section className="toolbar" aria-label="Tier filters">
          <div className="segmented">
            {FILTER_TIERS.map((tier) => (
              <button
                key={tier}
                type="button"
                className={filterTier === tier ? "is-active" : ""}
                onClick={() => setFilterTier(tier)}
              >
                {tier}
              </button>
            ))}
          </div>
          <p id="resultCount">{visibleResults.length} result{visibleResults.length === 1 ? "" : "s"}</p>
        </section>

        {search.answer?.answer ? (
          <AnswerPanel
            response={search.answer}
            onAnchorClick={(anchor) => {
              const match =
                search.results.find(
                  (c) =>
                    c.page_path === anchor.page_path &&
                    c.line_start <= anchor.line_start &&
                    c.line_end >= anchor.line_start,
                ) ?? search.results.find((c) => c.page_path === anchor.page_path);
              if (match) viewer.openViewer(match);
            }}
          />
        ) : null}

        <SearchResultsView citations={visibleResults} onOpen={viewer.openViewer} />
        </>
        ) : (
          <PlaceholderView route={route} />
        )}
      </main>

      <CitationViewer citation={viewer.citation} onClose={viewer.closeViewer} />
      <CommandPalette palette={palette} onRun={(q, t) => {
        tierState.setTier(t);
        search.runSearch(q, t);
      }} />
    </div>
  );
}

function PlaceholderView({ route }: { route: AppRoute }) {
  const copy: Record<Exclude<AppRoute, "/command-centre" | "/graph" | "/crm" | "/add">, { title: string; body: string; status: string }> = {
    "/vault": {
      title: "Evidence Vault",
      body: "Vault files are indexed locally from markdown under vault/. Search and citation viewing are live in Command Centre; this section will become the file browser.",
      status: "Read-only browser pending",
    },
    "/memo": {
      title: "Memos",
      body: "Memo capture and editing will write markdown into vault/memos with explicit tier frontmatter. For now, create memos through the agent or CLI ingest flow.",
      status: "Draft UI pending",
    },
    "/audit": {
      title: "Privacy & Routing",
      body: "Safety gates are enforced in Python tests and API guards. This page will expose routing decisions, tier state, and local-only status.",
      status: "Audit surface pending",
    },
    "/gbrain": {
      title: "GBrain Sync",
      body: "GBrain is a sidecar only. It is not the answer path. Current policy requires cloud model fields to remain none or loopback.",
      status: "Sidecar status pending",
    },
    "/connectors": {
      title: "Connectors",
      body: "Connectors are not wired yet. Future imports should land in vault/inbox and pass through local conversion and tier checks.",
      status: "No active connectors",
    },
    "/settings": {
      title: "Settings",
      body: "Settings are currently file/env driven. Local services must bind 127.0.0.1 only, and unknown tier still fails closed to S3.",
      status: "Config UI pending",
    },
  };
  const item = copy[route as Exclude<AppRoute, "/command-centre" | "/graph" | "/crm" | "/add">];
  return (
    <section className="route-placeholder" aria-label={item.title}>
      <div>
        <p className="eyebrow">Workspace Route</p>
        <h2>{item.title}</h2>
      </div>
      <p>{item.body}</p>
      <span>{item.status}</span>
    </section>
  );
}

function AnswerPanel({ response, onAnchorClick }: {
  response: EngineResponse;
  onAnchorClick: (anchor: CitationAnchor) => void;
}) {
  const tier = (response.answer_tier ?? "S3") as Tier;
  const anchors = response.anchors ?? [];
  // S3 answers are sealed: no copy/export, matching the Citation Viewer rule.
  const sealed = tier === "S3";

  function copyAnswer() {
    if (sealed || !response.answer) return;
    void navigator.clipboard?.writeText(response.answer);
  }

  return (
    <section className="answer-panel" data-tier={tier} aria-label="Extracted answer">
      <header className="answer-panel__head">
        <TierBadge tier={tier} className="citation-tier-prominent" />
        <span className="answer-panel__title">Answer</span>
        {response.model_used ? (
          <span className="answer-panel__model">{response.model_used}</span>
        ) : null}
        {response.redacted ? (
          <span className="answer-panel__pill answer-panel__pill--amber">Redacted</span>
        ) : (
          <span className="answer-panel__pill">clean</span>
        )}
        {sealed ? (
          <span className="answer-panel__pill answer-panel__pill--rose">Sealed</span>
        ) : null}
        {!sealed ? (
          <button type="button" className="answer-panel__copy" onClick={copyAnswer}>
            Copy
          </button>
        ) : null}
      </header>

      <pre className="answer-panel__text">{response.answer}</pre>

      {anchors.length ? (
        <ul className="answer-panel__anchors">
          {anchors.map((anchor) => (
            <li key={anchor.anchor}>
              <button
                type="button"
                className="answer-panel__anchor"
                onClick={() => onAnchorClick(anchor)}
              >
                {anchor.anchor}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function SearchResultsView({ citations, onOpen }: {
  citations: Citation[];
  onOpen: (citation: Citation) => void;
}) {
  if (!citations.length) {
    return (
      <section className="empty-state">
        <h2>No results found in vault</h2>
      </section>
    );
  }
  return (
    <section className="results-list" aria-label="Ranked citations">
      {citations.map((citation, index) => (
        <ResultCard key={citation.chunk_id} rank={index + 1} citation={citation} onClick={() => onOpen(citation)} />
      ))}
    </section>
  );
}

function ResultCard({ rank, citation, onClick }: {
  rank: number;
  citation: Citation;
  onClick: () => void;
}) {
  return (
    <button className="result-card" type="button" onClick={onClick}>
      <span className="result-card__rank">{rank}</span>
      <span className="result-card__body">
        <span className="result-card__meta">
          <TierBadge tier={citation.tier} />
          <span>{filename(citation.page_path)}</span>
          <span>lines {citation.line_start}-{citation.line_end}</span>
          {citation.atoms.length > 0 ? <KindBadge kind="GENERATED" /> : null}
        </span>
        <span className="result-card__preview">{preview(citation.text)}</span>
        <ScoreBreakdown scores={citation.scores} />
      </span>
    </button>
  );
}

function CitationViewer({ citation, onClose }: {
  citation: Citation | null;
  onClose: () => void;
}) {
  const hash = useSha(citation?.text);
  if (!citation) return null;
  return (
    <aside className="viewer is-open" aria-hidden="false">
      <article className="viewer__panel" role="dialog" aria-modal="true" aria-label="Citation viewer">
        <header className="viewer__header">
          <div>
            <TierBadge tier={citation.tier} className="citation-tier-prominent" />
            <h2>{citation.page_path}</h2>
            <p>lines {citation.line_start}-{citation.line_end} | bytes {citation.byte_start}-{citation.byte_end}</p>
          </div>
          <button id="viewerClose" type="button" aria-label="Close citation viewer" onClick={onClose}>x</button>
        </header>

        <pre className="viewer__text">{citation.text}</pre>
        <ScoreBreakdown scores={citation.scores} />

        <section>
          <h3>Atoms</h3>
          <div className="atom-row">
            {citation.atoms.length ? citation.atoms.map((atom) => (
              <AtomChip
                key={atom.atom_id}
                atom={atom}
                lineStart={citation.line_start}
                lineEnd={citation.line_end}
              />
            )) : <div className="placeholder-inline">No atoms resolved</div>}
          </div>
        </section>

        <section>
          <h3>Graph refs</h3>
          <ul className="graph-list">
            {citation.graph_refs.length ? citation.graph_refs.map((ref) => <li key={ref}>{ref}</li>) : <li className="muted">No graph references</li>}
          </ul>
        </section>

        <footer className="viewer__footer">
          <span>SHA-256 <b>{hash}</b></span>
          <strong>{citation.tier === "S3" ? "S3 sealed: copy/export unavailable" : "Local viewer only"}</strong>
        </footer>
      </article>
    </aside>
  );
}

function CommandPalette({ palette, onRun }: {
  palette: ReturnType<typeof usePalette>;
  onRun: (query: string, tier: TierContext) => void;
}) {
  if (!palette.open) return null;
  return (
    <aside className="palette is-open" aria-hidden="false">
      <section className="palette__panel" role="dialog" aria-modal="true" aria-label="Command palette">
        <form
          className="palette__controls"
          onSubmit={(event) => {
            event.preventDefault();
            onRun(palette.query, palette.tier);
            palette.setOpen(false);
          }}
        >
          <input
            autoFocus
            value={palette.query}
            onChange={(event) => {
              palette.setQuery(event.target.value);
            }}
            type="search"
            placeholder="Search citations"
          />
          <select value={palette.tier} onChange={(event) => palette.setTier(event.target.value as TierContext)}>
            {SEARCH_TIERS.map((tier) => <option key={tier} value={tier}>{tier === "Auto" ? "Auto = S3" : tier}</option>)}
          </select>
        </form>
        <ul className="palette__results">
          {palette.previewResults.length ? palette.previewResults.map((citation, index) => (
            <li key={citation.chunk_id} className={index === palette.index ? "is-active" : ""}>
              <TierBadge tier={citation.tier} />
              <span>{filename(citation.page_path)}</span>
              <b>{citation.score.toFixed(2)}</b>
            </li>
          )) : <li className="palette__empty">No matching mock citations</li>}
        </ul>
      </section>
    </aside>
  );
}
