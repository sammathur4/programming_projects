export function parseHash() {
  const hash = window.location.hash.slice(1) || "/";
  const [pathPart, queryPart] = hash.split("?");
  const path = pathPart || "/";
  const params = new URLSearchParams(queryPart || "");
  return { path, params };
}

export function navigate(path, params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  const qs = new URLSearchParams(entries).toString();
  window.location.hash = qs ? `${path}?${qs}` : path;
}

export function setParam(key, value) {
  const { path, params } = parseHash();
  if (value === undefined || value === null || value === "") {
    params.delete(key);
  } else {
    params.set(key, value);
  }
  navigate(path, Object.fromEntries(params.entries()));
}
