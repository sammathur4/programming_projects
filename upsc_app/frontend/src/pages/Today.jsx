import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Today.css";

function Today() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/daily/")
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return <div className="page-card">Error: {error}</div>;
  }

  if (!data) {
    return <div className="page-card">Loading...</div>;
  }

  return (
    <div className="today-grid">
      <section className="page-card today-hero">
        <header className="page-card-header">
          <div>
            <h1>Today</h1>
            <p>{data.date}</p>
          </div>
          <div className="streak-pill">
            🔥 {data.streak?.current || 0} · Best {data.streak?.longest || 0} · Gold {data.streak?.gold_count || 0}
          </div>
        </header>
        <div className="daily-list">
          {(data.items || []).map((item) => (
            <article key={item.track} className="daily-card">
              <div>
                <div className="daily-card-label">{item.track}</div>
                <div className="daily-card-title">{item.question?.question?.slice(0, 90) || "-"}</div>
              </div>
              <a className="daily-card-action" href={`#/questions/${item.question?.id || ""}`}>
                {item.completed ? "Review" : "Solve"}
              </a>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export default Today;
