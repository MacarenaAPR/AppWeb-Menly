const DEFAULT_FALLBACK_IMAGE = "/favicon.svg";

export const resolveImageUrl = (image, baseUrl = "", fallbackImage = DEFAULT_FALLBACK_IMAGE) => {
  if (!image) return fallbackImage;

  const value = String(image);

  if (/^https?:\/\//i.test(value) || value.startsWith("/")) {
    return value;
  }

  return `${baseUrl || ""}${value}`;
};

export const optimizeCloudinaryImage = (
  url,
  { width = 800, height = 600, crop = "fill" } = {}
) => {
  if (!url || !String(url).includes("/upload/")) return url;

  const value = String(url);

  if (value.includes("/upload/f_auto") || value.includes("/upload/q_auto")) {
    return value;
  }

  const transformation = `f_auto,q_auto,w_${width},h_${height},c_${crop}`;

  return value.replace("/upload/", `/upload/${transformation}/`);
};

export const getOptimizedImageUrl = (
  image,
  { baseUrl = "", fallbackImage = DEFAULT_FALLBACK_IMAGE, width = 800, height = 600, crop = "fill" } = {}
) => {
  const resolvedUrl = resolveImageUrl(image, baseUrl, fallbackImage);

  return optimizeCloudinaryImage(resolvedUrl, { width, height, crop });
};
