import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Question.css";

function Question() {
  const key = window.location.hash.split("/questions/")[1]?.split("?")[0];
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState(null);
  const [attemptId, setAttemptId] = useState(null);

  useEffect(() => {
    if (!key) return;
    api.get(`/api/questions/${key}/`)
      .then((res) => {
        setData(res);
      })
      .catch((err) => setError(err.message));
  }, [key]);

  const start = async () => {
    const res = await api.post("/api/attempts/start/", { stage: data.question.stage });
    setAttemptId(res.id);
  };

  const submit = async () => {
    if (!attemptId) await start();
    const aid = attemptId || (await api.post("/api/attempts/start/", { stage: data.question.stage })).id;
    if (!attemptId) setAttemptId(aid);
    await api.post(`/api/attempts/${aid}/responses/`, {
      question_key: key,
      question_stage: data.question.stage,
      selected_answer: selected,
    });
    const r = await api.post(`/api/attempts/${aid}/submit/`, {});
    setResult(r);
  };

  if (error) return <div className="page-card">Error: {error}</div>;
  if (!data) return <div className="page-card">Loading...</div>;

  const q = data.question;
  const isMains = q.stage === "mains";

  return (
    <div className="question-grid">
      <section className="page-card">
        <header className="page-card-header">
          <div>
            <h1>Question</h1>
            <p>{q.year} · {q.paper}</p>
          </div>
        </header>
        <div className="question-body">
          <p className="question-text">{q.question}</p>
          {!isMains && q.options && (
            <div className="option-list">
              {Object.entries(q.options).map(([opt, text]) => (
                <button
                  key={opt}
                  className={`option-btn ${selected === opt ? "selected" : ""}`}
                  onClick={() => setSelected(opt)}
                >
                  <span className="option-key">{opt.toUpperCase()}</span>
                  <span>{text}</span>
                </button>
              ))}
            </div>
          )}
          {isMains && (
            <div className="mains-note">Mains/Essay: Use Mains tab to upload your answer.</div>
          )}
          <div className="question-actions">
            {!isMains && <button className="primary-btn" onClick={submit}>Submit</button>}
            {isMains && <a className="primary-btn" href="#/mains">Go to Mains</a>}
          </div>
          {result && <div className="result-pill">Submitted</div>}
        </div>
      </section>
    </div>
  );
}

export default Question;
