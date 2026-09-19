// Shared bootstrap for the multi-tenant pages (login/signup/preferences/jobs).
// Kept dependency-free so any page can load it with a plain <script> tag.

const params = new URLSearchParams(window.location.search);
const DEFAULT_API_BASE = "https://job-scraper-resume-api.onrender.com";
export const API_BASE = params.get("api") || localStorage.getItem("resume_api_base") || DEFAULT_API_BASE;
if (params.get("api")) localStorage.setItem("resume_api_base", params.get("api"));

export async function initSupabase(onError) {
  const configResp = await fetch(`${API_BASE}/api/config`);
  if (!configResp.ok) {
    onError(
      `Could not reach the resume API at ${API_BASE}/api/config. Add ?api=<your-api-url> to the page URL if it runs elsewhere.`
    );
    return null;
  }
  const config = await configResp.json();
  return supabase.createClient(config.supabase_url, config.supabase_publishable_key);
}

export async function currentToken(supabaseClient) {
  const { data: { session } } = await supabaseClient.auth.getSession();
  return session ? session.access_token : null;
}

// Redirects to login.html if there is no session. Returns the session otherwise.
export async function requireSession(supabaseClient, redirectTo = "login.html") {
  const { data: { session } } = await supabaseClient.auth.getSession();
  if (!session) {
    window.location.href = redirectTo;
    return null;
  }
  return session;
}

export async function authedFetch(supabaseClient, path, options = {}) {
  const token = await currentToken(supabaseClient);
  const headers = { ...(options.headers || {}), Authorization: `Bearer ${token}` };
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

export function renderNav(activePage, supabaseClient) {
  const nav = document.getElementById("app-nav");
  if (!nav) return;
  nav.innerHTML = `
    <a href="home.html" class="nav-brand">AI Job Hunter</a>
    <div class="nav-links">
      <a href="preferences.html" class="${activePage === "preferences" ? "active" : ""}">My Resume</a>
      <a href="jobs.html" class="${activePage === "jobs" ? "active" : ""}">Job Matches</a>
      <button id="nav-signout" class="nav-signout" type="button">Sign out</button>
    </div>
  `;
  document.getElementById("nav-signout").addEventListener("click", async () => {
    await supabaseClient.auth.signOut();
    window.location.href = "home.html";
  });
}
