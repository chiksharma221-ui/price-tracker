const fields = ["backendUrl", "dashboardUrl", "apiToken"];
const message = document.getElementById("message");

function say(text, isError) {
  message.textContent = text;
  message.className = isError ? "error" : "ok";
}

async function ensurePermission(url) {
  // Localhost is granted in the manifest; any other tracker address needs
  // the user's explicit permission, requested from this click.
  const origin = new URL(url).origin + "/*";
  if (await chrome.permissions.contains({ origins: [origin] })) return true;
  return chrome.permissions.request({ origins: [origin] });
}

(async () => {
  const settings = await getSettings();
  fields.forEach((f) => (document.getElementById(f).value = settings[f] || ""));
  document.getElementById("autoShow").checked = settings.autoShow;
})();

document.getElementById("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const values = Object.fromEntries(fields.map((f) => [f, document.getElementById(f).value.trim()]));
  values.autoShow = document.getElementById("autoShow").checked;
  try {
    if (!(await ensurePermission(values.backendUrl))) {
      say("Permission to reach that address was declined, so it can't be used.", true);
      return;
    }
    await chrome.storage.sync.set(values);
    say("Saved.");
  } catch (err) {
    say(`Couldn't save: ${err.message}`, true);
  }
});

document.getElementById("test").addEventListener("click", async () => {
  const url = document.getElementById("backendUrl").value.trim().replace(/\/+$/, "");
  try {
    await ensurePermission(url);
    const res = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(5000) });
    const body = await res.json();
    say(res.ok ? `Connected. Storage: ${body.store}, token required: ${body.auth_required ? "yes" : "no"}.`
               : `The tracker answered with error ${res.status}.`, !res.ok);
  } catch (_) {
    say("Couldn't connect. Check the address and that the API is running.", true);
  }
});
