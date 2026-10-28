import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Mains.css";

function Mains() {
  const [queue, setQueue] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/mains/queue/")
      .then((res) => setQueue(res.questions || res.items || []))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="mains-grid">
      <section className="page-card">
        <header className="page-card-header">
          <div>
            <h1>Mains</h1>
            <p>Upload-only vault</p>
          </div>
        </header>
        {error && <div className="mains-error">{error}</div>}
        <div className="mains-list">
          {queue.map((q) => (
            <article key={q.id} className="mains-row">
              <div>
                <div className="mains-row-meta">{q.year} · {q.paper}</div>
                <div className="mains-row-title">{q.question?.slice(0, 110)}...</div>
              </div>
              <a className="primary-btn" href={`#/questions/${q.id}`}>Upload</a>
            </article>
          ))}
          {queue.length === 0 && <div className="practice-empty">No items in queue</div>}
        </div>
      </section>
    </div>
  );
}

export default Mains;
