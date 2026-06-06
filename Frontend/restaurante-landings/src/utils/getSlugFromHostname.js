const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1"]);
const ROOT_HOSTNAMES = new Set(["menly.cl", "www.menly.cl"]);
export const getSlugFromHostname = () => {
  const hostname = window.location.hostname.toLowerCase();

  if (LOCAL_HOSTNAMES.has(hostname)) {
    return null;
  }

  if (ROOT_HOSTNAMES.has(hostname)) {
    return null;
  }

  if (!hostname.endsWith(".menly.cl")) {
    return null;
  }

  const [subdomain] = hostname.split(".");
  return subdomain || null;
};
