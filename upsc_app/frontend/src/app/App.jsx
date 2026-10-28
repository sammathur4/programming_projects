import { useEffect, useState } from "react";
import Shell from "./Shell";
import { parseHash } from "./router";
import Today from "../pages/Today";
import Practice from "../pages/Practice";
import Question from "../pages/Question";
import Mains from "../pages/Mains";
import Settings from "../pages/Settings";
import "./App.css";

function Placeholder({ title }) {
  return (
    <section className="page-card">
      <header className="page-card-header">
        <div>
          <h1>{title}</h1>
          <p>Coming soon / available in full app</p>
        </div>
      </header>
    </section>
  );
}

function App() {
  const [route, setRoute] = useState(parseHash());

  useEffect(() => {
    const handler = () => setRoute(parseHash());
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  const renderPage = () => {
    const path = route.path;
    if (path === "/" || path === "") return <Today />;
    if (path === "/practice" || path === "/questions" || path === "#practice") return <Practice />;
    if (path.startsWith("/questions/")) return <Question />;
    if (path === "/syllabus") return <Practice />;
    if (path === "/quiz") return <Placeholder title="Quiz" />;
    if (path === "/history") return <Placeholder title="History" />;
    if (path === "/bookmarks") return <Placeholder title="Bookmarks" />;
    if (path === "/review") return <Placeholder title="Review" />;
    if (path === "/mains") return <Mains />;
    if (path === "/settings") return <Settings />;
    return <Today />;
  };

  return <Shell>{renderPage()}</Shell>;
}

export default App;
