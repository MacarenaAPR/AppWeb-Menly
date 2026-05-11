import { getSlugFromHostname } from "../utils/getSlugFromHostname";

const BASE_URL = import.meta.env.VITE_API_URL;

export const getMenu = async (slug = getSlugFromHostname()) => {
  if (!slug) {
    throw new Error("Slug de restaurante no disponible");
  }

  const res = await fetch(`${BASE_URL}/menu/${slug}/`);

  if (!res.ok) {
    throw new Error("Error cargando menu");
  }

  return res.json();
};
