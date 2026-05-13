const output = document.getElementById("output");
const refreshButton = document.getElementById("refresh-button");

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

function setOutput(value, isError = false) {
  output.classList.toggle("error", isError);
  output.textContent = typeof value === "string" ? value : formatJson(value);
}

function endpointWithParams() {
  const endpoint = document.body.dataset.endpoint;
  const params = new URLSearchParams();

  for (const input of document.querySelectorAll("[data-query-param]")) {
    const value = input.value.trim();
    if (value) {
      params.set(input.dataset.queryParam, value);
    }
  }

  const query = params.toString();
  return query ? `${endpoint}?${query}` : endpoint;
}

async function loadEndpoint() {
  if (!output) return;
  if (refreshButton) refreshButton.disabled = true;
  setOutput("Loading…");

  try {
    const endpoint = endpointWithParams();
    const response = await fetch(endpoint);
    const text = await response.text();
    let payload;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = text;
    }

    if (!response.ok) {
      setOutput(payload, true);
      return;
    }
    setOutput(payload);
  } catch (error) {
    setOutput(error.message, true);
  } finally {
    if (refreshButton) refreshButton.disabled = false;
  }
}

if (refreshButton) {
  refreshButton.addEventListener("click", loadEndpoint);
}

for (const input of document.querySelectorAll("[data-query-param]")) {
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadEndpoint();
    }
  });
}

loadEndpoint();
