import * as React from "react";
import { fetchCrm, type CrmCompany, type CrmPerson } from "./api";
import { TierBadge } from "./dashboard/components";
import type { Tier } from "./types";

type CrmTab = "people" | "companies";

/**
 * CRM screen: contacts (people) and companies sourced from vault frontmatter via
 * GET /crm. S3 rows are sealed (tier badge only, no detail, no click-through),
 * matching the Evidence Vault sealing rule. Clicking a non-sealed row asks the
 * parent to open the Citation Viewer for that page.
 */
export function CRM({
  onOpenPage,
}: {
  onOpenPage: (query: string, tier: Tier) => void;
}) {
  const [tab, setTab] = React.useState<CrmTab>("people");
  const [people, setPeople] = React.useState<CrmPerson[]>([]);
  const [companies, setCompanies] = React.useState<CrmCompany[]>([]);
  const [message, setMessage] = React.useState("");

  React.useEffect(() => {
    let cancelled = false;
    fetchCrm()
      .then((data) => {
        if (cancelled) return;
        setPeople(data.people);
        setCompanies(data.companies);
        setMessage("");
      })
      .catch(() => {
        if (!cancelled) setMessage("CRM unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function openRow(name: string, tier: Tier, sealed: boolean) {
    if (sealed) {
      setMessage("S3 content sealed");
      return;
    }
    setMessage("");
    onOpenPage(name, tier);
  }

  const count = tab === "people" ? people.length : companies.length;

  return (
    <section className="vault-screen" aria-label="CRM">
      <header className="screen-header">
        <div>
          <p className="eyebrow">Relationships</p>
          <h2>CRM - {people.length} people, {companies.length} companies</h2>
        </div>
        <div className="segmented">
          <button
            type="button"
            className={tab === "people" ? "is-active" : ""}
            onClick={() => setTab("people")}
          >
            People
          </button>
          <button
            type="button"
            className={tab === "companies" ? "is-active" : ""}
            onClick={() => setTab("companies")}
          >
            Companies
          </button>
        </div>
      </header>

      {message ? <div className="inline-alert">{message}</div> : null}

      {tab === "people" ? (
        <div className="vault-table" role="table" aria-label="People">
          <div className="vault-table__head vault-table__head--crm" role="row">
            <span>Tier</span>
            <span>Name</span>
            <span>Company</span>
            <span>Role</span>
          </div>
          {people.map((person) => {
            const sealed = person.tier === "S3";
            return (
              <button
                key={person.slug}
                type="button"
                className={sealed ? "vault-row vault-row--crm vault-row--sealed" : "vault-row vault-row--crm"}
                onClick={() => openRow(person.name, person.tier, sealed)}
              >
                <TierBadge tier={person.tier} />
                <span className="vault-row__file">{sealed ? <b>SEALED</b> : person.name}</span>
                <span>{sealed ? "" : person.company ?? "-"}</span>
                <span>{sealed ? "" : person.role ?? "-"}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="vault-table" role="table" aria-label="Companies">
          <div className="vault-table__head vault-table__head--crm-co" role="row">
            <span>Tier</span>
            <span>Name</span>
            <span>Type</span>
          </div>
          {companies.map((company) => {
            const sealed = company.tier === "S3";
            return (
              <button
                key={company.slug}
                type="button"
                className={sealed ? "vault-row vault-row--crm-co vault-row--sealed" : "vault-row vault-row--crm-co"}
                onClick={() => openRow(company.name, company.tier, sealed)}
              >
                <TierBadge tier={company.tier} />
                <span className="vault-row__file">{sealed ? <b>SEALED</b> : company.name}</span>
                <span>{sealed ? "" : company.type ?? "-"}</span>
              </button>
            );
          })}
        </div>
      )}

      {count === 0 && !message ? (
        <section className="empty-state">
          <h2>No {tab} in vault</h2>
        </section>
      ) : null}
    </section>
  );
}
