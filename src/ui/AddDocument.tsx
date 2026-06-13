import * as React from "react";
import { addDocument } from "./api";
import { TierBadge } from "./dashboard/components";
import type { Tier } from "./types";

/**
 * Add Document screen (/add): a non-technical capture form. Paste raw notes,
 * pick a document type and tier, and the local engine structures + indexes it
 * into the vault. Everything stays local (gemma4-citadel on loopback); S3 is
 * visually flagged rose with an explicit "never leaves your machine" warning.
 * Binary upload is out of scope for v1 — helper text points at vault/raw/.
 */

const DOC_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "meeting", label: "Meeting Notes" },
  { value: "company", label: "Company Profile" },
  { value: "memo", label: "Memo" },
  { value: "research", label: "Research Note" },
  { value: "email", label: "Email Thread" },
];

const TIER_OPTIONS: { value: Tier; label: string; desc: string }[] = [
  { value: "S1", label: "S1 - Public", desc: "Public reports, filings, news" },
  { value: "S2", label: "S2 - Sensitive", desc: "Meeting notes, internal documents" },
  { value: "S3", label: "S3 - Confidential", desc: "Board memos, deal documents, MNPI" },
];

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; chunks: number; filename: string }
  | { kind: "error"; message: string };

export function AddDocument() {
  const [docType, setDocType] = React.useState("meeting");
  const [tier, setTier] = React.useState<Tier>("S2");
  const [title, setTitle] = React.useState("");
  const [content, setContent] = React.useState("");
  const [status, setStatus] = React.useState<Status>({ kind: "idle" });

  const tierDesc = TIER_OPTIONS.find((t) => t.value === tier)?.desc ?? "";
  const isS3 = tier === "S3";
  const loading = status.kind === "loading";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!content.trim()) {
      setStatus({ kind: "error", message: "Paste some notes before adding to the vault." });
      return;
    }
    setStatus({ kind: "loading" });
    try {
      const res = await addDocument({
        content: content.trim(),
        doc_type: docType,
        tier,
        title: title.trim() || undefined,
      });
      setStatus({ kind: "success", chunks: res.chunks, filename: res.filename });
      setContent("");
      setTitle("");
    } catch (err) {
      setStatus({
        kind: "error",
        message: err instanceof Error ? err.message : "Could not add document.",
      });
    }
  }

  return (
    <section className="vault-screen add-doc" data-tier={tier} aria-label="Add Document">
      <header className="screen-header">
        <div>
          <p className="eyebrow">Capture</p>
          <h2>Add Document</h2>
        </div>
        <TierBadge tier={tier} className="citation-tier-prominent" />
      </header>

      <form className="add-doc__form" onSubmit={submit}>
        <div className="add-doc__row">
          <label className="add-doc__field">
            <span className="add-doc__label">Document Type</span>
            <select value={docType} onChange={(e) => setDocType(e.target.value)} disabled={loading}>
              {DOC_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>

          <label className="add-doc__field">
            <span className="add-doc__label">Tier</span>
            <select
              value={tier}
              onChange={(e) => setTier(e.target.value as Tier)}
              disabled={loading}
            >
              {TIER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <span className="add-doc__hint">{tierDesc}</span>
          </label>
        </div>

        {isS3 ? (
          <div className="add-doc__warning" role="note">
            This will never leave your machine.
          </div>
        ) : null}

        <label className="add-doc__field">
          <span className="add-doc__label">Title <span className="add-doc__optional">(optional)</span></span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Leave blank to derive from the notes"
            autoComplete="off"
            disabled={loading}
          />
        </label>

        <label className="add-doc__field">
          <span className="add-doc__label">Notes</span>
          <textarea
            className="add-doc__textarea"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste your notes here"
            rows={14}
            disabled={loading}
          />
        </label>

        <p className="add-doc__upload-hint">
          To add PDFs, Word, Excel, or PowerPoint files, drop them into{" "}
          <code>vault/raw/s1</code>, <code>vault/raw/s2</code>, or <code>vault/raw/s3</code>.
        </p>

        <div className="add-doc__actions">
          <button type="submit" className="add-doc__submit" disabled={loading}>
            {loading ? (
              <>
                <span className="add-doc__spinner" aria-hidden="true" /> Adding...
              </>
            ) : (
              "Add to Vault"
            )}
          </button>
        </div>
      </form>

      {status.kind === "success" ? (
        <div className="inline-alert add-doc__success" role="status">
          Added to vault. Indexed {status.chunks} chunk{status.chunks === 1 ? "" : "s"}.
          <span className="add-doc__filename"> ({status.filename})</span>
        </div>
      ) : null}

      {status.kind === "error" ? (
        <div className="inline-alert add-doc__error" role="alert">
          {status.message}
        </div>
      ) : null}
    </section>
  );
}
