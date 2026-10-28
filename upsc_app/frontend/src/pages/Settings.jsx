import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Settings.css";

function Settings() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.get("/api/health/").then(setHealth).catch(() => {});
  }, []);

  const exportData = async () => {
    try {
      const res = await api.get("/api/export/");
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "iascode-export.json";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message);
    }
  };

  return (
    <div className="settings-grid">
      <section className="page-card">
        <header className="page-card-header">
          <div>
            <h1>Settings</h1>
            <p>Local, single user</p>
          </div>
        </header>
        <div className="settings-list">
          <div className="settings-row">
            <div>
              <div className="settings-row-title">Learner</div>
              <div className="settings-row-sub">{health?.learner?.username || "-"}</div>
            </div>
          </div>
          <div className="settings-row">
            <div>
              <div className="settings-row-title">Dataset</div>
              <div className="settings-row-sub">
                Prelims {health?.counts?.prelims || 0} · Mains {health?.counts?.mains || 0}
              </div>
            </div>
          </div>
          <div className="settings-row">
            <div>
              <div className="settings-row-title">Export</div>
              <div className="settings-row-sub">Download JSON backup</div>
            </div>
            <button className="primary-btn" onClick={exportData}>Export</button>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Settings;
