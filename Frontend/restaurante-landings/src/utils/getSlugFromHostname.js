const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1"]);
const RESERVED_SUBDOMAINS = new Set(["www", "api", "admin", "app"]);

const DEFAULT_BASE_DOMAINS = [
  "menly.cl",
  "menly.localhost",
  "localhost",
  "lvh.me",
  "nip.io",
];

const getBaseDomains = () =>
  String(import.meta.env.VITE_PUBLIC_BASE_DOMAINS || "")
    .split(",")
    .map((domain) => domain.trim().toLowerCase())
    .filter(Boolean);

export const getSlugFromHostname = (hostname = window.location.hostname) => {
  const normalizedHostname = String(hostname || "")
    .split(":")[0]
    .toLowerCase();

  if (LOCAL_HOSTNAMES.has(normalizedHostname)) {
    return null;
  }

  const baseDomains = [...getBaseDomains(), ...DEFAULT_BASE_DOMAINS];

  if (baseDomains.includes(normalizedHostname)) {
    return null;
  }

  for (const baseDomain of baseDomains) {
    const suffix = `.${baseDomain}`;

    if (!normalizedHostname.endsWith(suffix)) {
      continue;
    }

    const slug = normalizedHostname.slice(0, -suffix.length).split(".")[0];
    return slug && !RESERVED_SUBDOMAINS.has(slug) ? slug : null;
  }

  return null;
};
