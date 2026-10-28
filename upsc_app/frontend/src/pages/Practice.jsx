import { useEffect, useState } from "react";
import { api } from "../api/client";
import { navigate, parseHash } from "../app/router";
import "./Practice.css";

function Practice() {
  const [data, setData] = useState({ questions: [], pagination: { total: 0 } });
  const [loading, setLoading] = useState(true);
  const { params } = parseHash();

  const stage = params.get("stage") || "all";
  const paper = params.get("paper") || "all";
  const year = params.get("year") || "all";
  const search = params.get("q") || "";

  useEffect(() => {
    setLoading(true);
    const qs = new URLSearchParams();
    if (stage && stage !== "all") qs.set("stage", stage);
    if (paper && paper !== "all") qs.set("paper", paper);
    if (year && year !== "all") qs.set("year", year);
    if (search) qs.set("search", search);
    api.get(`/api/questions/?${qs.toString()}`)
      .then(setData)
      .catch(() => setData({ questions: [], pagination: { total: 0 } }))
      .finally(() => setLoading(false));
  }, [window.location.hash]);

  const updateFilter = (key, value) => {
    const p = new URLSearchParams(window.location.hash.split("?")[1] || "");
    if (value === "all" || value === "") p.delete(key);
    else p.set(key, value);
    navigate("/practice", Object.fromEntries(p.entries()));
  };

  return (
    <div className="practice-grid">
      <section className="page-card">
        <header className="page-card-header">
          <div>
            <h1>Practice</h1>
            <p>{data.pagination?.total || 0} questions</p>
          </div>
        </header>
        <div className="practice-filters">
          <select value={stage} onChange={(e) => updateFilter("stage", e.target.value)}>
            <option value="all">All Stages</option>
            <option value="prelims">Prelims</option>
            <option value="mains">Mains</option>
          </select>
          <select value={paper} onChange={(e) => updateFilter("paper", e.target.value)}>
            <option value="all">All Papers</option>
            <option value="Prelims GS">Prelims GS</option>
            <option value="Prelims CSAT">Prelims CSAT</option>
            <option value="gs1">GS1</option>
            <option value="gs2">GS2</option>
            <option value="gs3">GS3</option>
            <option value="gs4">GS4</option>
            <option value="essay">Essay</option>
            <option value="sociology1">Sociology 1</option>
            <option value="sociology2">Sociology 2</option>
          </select>
          <input
            type="search"
            placeholder="Search questions..."
            defaultValue={search}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                updateFilter("q", e.target.value);
              }
            }}
          />
        </div>
        <div className="practice-list">
          {(data.questions || []).map((q, idx) => (
            <a key={q.id} className="practice-row" href={`#/questions/${q.id}`}>
              <div className="practice-row-left">
                <span className="practice-row-num">{(data.pagination?.page - 1) * 20 + idx + 1}.</span>
                <div>
                  <div className="practice-row-meta">
                    {q.year} · {q.paper} · {q.stage}
                  </div>
                  <div className="practice-row-title">{q.question}</div>
                </div>
              </div>
              <span className="practice-row-badge">{q.status || "todo"}</span>
            </a>
          ))}
          {loading && <div className="practice-empty">Loading...</div>}
          {!loading && (data.questions || []).length === 0 && <div className="practice-empty">No questions</div>}
        </div>
      </section>
    </div>
  );
}

export default Practice;
