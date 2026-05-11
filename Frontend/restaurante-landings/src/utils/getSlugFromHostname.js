const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1"]);
const ROOT_HOSTNAMES = new Set(["menly.cl", "www.menly.cl"]);
const DEFAULT_LOCAL_SLUG = "la-mechada-real";

export const getSlugFromHostname = () => {
  const hostname = window.location.hostname;

  if (LOCAL_HOSTNAMES.has(hostname)) {
    return DEFAULT_LOCAL_SLUG;
  }

  if (ROOT_HOSTNAMES.has(hostname)) {
    return null;
  }

  const [subdomain] = hostname.split(".");
  return subdomain || null;
};

