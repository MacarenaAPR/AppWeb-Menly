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

const isCloudinaryTransformationSegment = (segment) =>
  String(segment || "")
    .split(",")
    .some((part) => /^(?:a|ar|b|c|dpr|e|f|fl|g|h|q|r|w|x|y|z)_/.test(part));

const removeCloudinaryDeliveryTransformations = (url) => {
  const value = String(url);
  const uploadMarker = "/upload/";
  const uploadIndex = value.indexOf(uploadMarker);

  if (uploadIndex === -1) return value;

  const prefix = value.slice(0, uploadIndex + uploadMarker.length);
  const segments = value.slice(uploadIndex + uploadMarker.length).split("/");
  const versionIndex = segments.findIndex((segment) => /^v\d+$/.test(segment));

  if (versionIndex > 0) {
    const leadingSegments = segments.slice(0, versionIndex);
    if (leadingSegments.every(isCloudinaryTransformationSegment)) {
      return `${prefix}${segments.slice(versionIndex).join("/")}`;
    }
  }

  if (segments[0]?.includes(",") && isCloudinaryTransformationSegment(segments[0])) {
    return `${prefix}${segments.slice(1).join("/")}`;
  }

  return value;
};

const optimizeCloudinaryContainedImage = (url, { width, maxWidth }) => {
  if (!url || !String(url).includes("/upload/")) return url;

  const safeWidth = Math.min(Math.max(Number(width) || maxWidth, 1), maxWidth);
  const sourceUrl = removeCloudinaryDeliveryTransformations(url);
  const transformation = `f_auto,q_auto,w_${safeWidth},c_limit`;

  return sourceUrl.replace("/upload/", `/upload/${transformation}/`);
};

export const optimizeCloudinaryLogo = (url, { width = 800 } = {}) =>
  optimizeCloudinaryContainedImage(url, { width, maxWidth: 800 });

export const getOptimizedLogoUrl = (
  image,
  { baseUrl = "", fallbackImage = "", width = 800 } = {}
) => {
  const resolvedUrl = resolveImageUrl(image, baseUrl, fallbackImage);

  return optimizeCloudinaryLogo(resolvedUrl, { width });
};

export const getOptimizedFormImageUrl = (
  image,
  { baseUrl = "", fallbackImage = DEFAULT_FALLBACK_IMAGE, width = 1200 } = {}
) => {
  const resolvedUrl = resolveImageUrl(image, baseUrl, fallbackImage);

  return optimizeCloudinaryContainedImage(resolvedUrl, { width, maxWidth: 1200 });
};
