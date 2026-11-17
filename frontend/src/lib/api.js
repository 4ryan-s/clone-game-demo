function messageFrom(body, status) {
  const detail = body && body.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || String(item)).join(" ");
  return `Request failed (${status})`;
}

const OFFLINE = "Start the demo server, then try again.";

export async function api(path, opts) {
  let response;
  try {
    response = await fetch(path, opts);
  } catch {
    throw new Error(OFFLINE);
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    if (!body && response.status >= 500) throw new Error(OFFLINE);
    throw new Error(messageFrom(body, response.status));
  }
  return body;
}
