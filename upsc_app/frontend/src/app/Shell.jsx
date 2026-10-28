import { NAV_ITEMS, FOOTER_ITEMS } from "./nav";
import { parseHash } from "./router";
import "./Shell.css";

function Shell({ children }) {
  const { path } = parseHash();
  const current = path || "/";

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand">
          <div className="app-brand-mark">IC</div>
          <div>
            <div className="app-brand-title">IASCode</div>
            <div className="app-brand-subtitle">Local</div>
          </div>
        </div>
        <nav className="app-nav">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.id}
              href={`#${item.path}`}
              className={`app-nav-link ${current === item.path ? "active" : ""}`}
            >
              {item.label}
            </a>
          ))}
        </nav>
        <div className="app-sidebar-footer">
          {FOOTER_ITEMS.map((item) => (
            <a
              key={item.id}
              href={`#${item.path}`}
              className={`app-nav-link ${current === item.path ? "active" : ""}`}
            >
              {item.label}
            </a>
          ))}
        </div>
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <div className="app-breadcrumb">IASCode</div>
        </header>
        <main className="app-content">{children}</main>
        <nav className="app-bottom-nav">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.id}
              href={`#${item.path}`}
              className={`app-bottom-link ${current === item.path ? "active" : ""}`}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
    </div>
  );
}

export default Shell;
