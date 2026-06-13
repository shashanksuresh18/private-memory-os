import * as React from "react";
import { fetchHealth, type HealthResponse } from "./api";

const RULES = [
  ["S1", "cloud AI allowed -> DeepSeek-V3.2"],
  ["S2", "DLP scrub -> cloud, redacted only"],
  ["S3", "local only -> gemma4-citadel"],
  ["Auto", "fail-closed -> S3"],
];

function shortHash(value: string) {
  if (!value) return "not recorded";
  return value.length > 18 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value;
}

export function PrivacyRouting() {
  const [health, setHealth] = React.useState<HealthResponse | null>(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((nextHealth) => {
        if (!cancelled) {
          setHealth(nextHealth);
          setError("");
        }
      })
      .catch(() => {
        if (!cancelled) setError("Health endpoint unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const gbrain = health?.gbrain ?? {};
  const auditEntries = health?.audit_entries ?? [];

  return (
    <section className="privacy-screen" aria-label="Privacy and Routing">
      {error ? <div className="inline-alert">{error}</div> : null}

      <section className="route-section">
        <header>
          <p className="eyebrow">Live Posture</p>
          <h2>Local-only routing</h2>
        </header>
        <div className="posture-grid">
          <PostureItem label="Cloud egress" value={health?.cloudAllowed ? "ALLOWED" : "BLOCKED"} ok={!health?.cloudAllowed} />
          <PostureItem label="gbrain embedding_model" value={`${gbrain.embedding_model ?? "unknown"} ${gbrain.embedding_model === "none" ? "ok" : ""}`} ok={gbrain.embedding_model === "none"} />
          <PostureItem label="gbrain chat_model" value={`${gbrain.chat_model ?? "unknown"} ${gbrain.chat_model === "none" ? "ok" : ""}`} ok={gbrain.chat_model === "none"} />
          <PostureItem label="S3 zero-egress test" value={health?.s3_zero_egress_test ?? "unknown"} ok={(health?.s3_zero_egress_test ?? "").includes("12/12")} />
        </div>
      </section>

      <section className="route-section">
        <header>
          <p className="eyebrow">Tier Rules</p>
          <h2>Fail-closed policy</h2>
        </header>
        <div className="rules-list">
          {RULES.map(([tier, rule]) => (
            <div key={tier} className="rule-row">
              <b>{tier}</b>
              <span>{rule}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="route-section">
        <header>
          <p className="eyebrow">Recent Audit Entries</p>
          <h2>Hash-only metadata</h2>
        </header>
        <div className="audit-table" role="table" aria-label="Recent audit entries">
          <div className="audit-table__head" role="row">
            <span>Timestamp</span>
            <span>Tier</span>
            <span>Query hash</span>
            <span>Model used</span>
          </div>
          {auditEntries.length ? auditEntries.map((entry, index) => (
            <div className="audit-row" role="row" key={`${entry.query_hash}-${index}`}>
              <span>{entry.timestamp || "not recorded"}</span>
              <span>{entry.tier || "n/a"}</span>
              <span className="font-mono">{shortHash(entry.query_hash)}</span>
              <span>{entry.model_used || "n/a"}</span>
            </div>
          )) : (
            <div className="audit-empty">No audit entries found</div>
          )}
        </div>
      </section>
    </section>
  );
}

function PostureItem({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className={ok ? "posture-item posture-item--ok" : "posture-item"}>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}
