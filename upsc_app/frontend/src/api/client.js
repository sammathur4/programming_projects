class ApiError extends Error {
  constructor(message, status, fields) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

async function request(path, options = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Accept": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = res.headers.get("content-type") || "";
  let data = null;
  if (contentType.includes("application/json")) {
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
  } else {
    try {
      data = await res.text();
    } catch (e) {
      data = null;
    }
  }

  if (!res.ok) {
    const message = (data && typeof data === "object" && data.error) || res.statusText || "Request failed";
    const fields = data && typeof data === "object" ? data.fields : null;
    throw new ApiError(message, res.status, fields);
  }

  return data;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) =>
    request(path, {
      method: "POST",
      headers: body instanceof FormData ? {} : { "Content-Type": "application/json" },
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  postForm: (path, formData) =>
    request(path, {
      method: "POST",
      body: formData,
    }),
  delete: (path) =>
    request(path, {
      method: "DELETE",
    }),
  patch: (path, body) =>
    request(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

export { ApiError };
