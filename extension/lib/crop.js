const MAX_DIM = 1400; // long-edge cap keeps image tokens (and latency) down

// Downscales the full capture — sent alongside the crop as surrounding context
// so the model can resolve details the user cropped out (year, org, venue).
export async function downscaleDataUrl(dataUrl, maxDim = MAX_DIM) {
  const blob = await (await fetch(dataUrl)).blob();
  const full = await createImageBitmap(blob);
  const scale = Math.min(1, maxDim / Math.max(full.width, full.height));
  const w = Math.max(1, Math.round(full.width * scale));
  const h = Math.max(1, Math.round(full.height * scale));
  const canvas = new OffscreenCanvas(w, h);
  canvas.getContext("2d").drawImage(full, 0, 0, w, h);
  full.close();
  const png = await canvas.convertToBlob({ type: "image/png" });
  return blobToBase64(png);
}

// Crops a captureVisibleTab data URL to the CSS-pixel rect the user selected.
// The capture is at device resolution, so the rect is scaled by devicePixelRatio.
export async function cropDataUrl(dataUrl, rect, dpr) {
  const blob = await (await fetch(dataUrl)).blob();
  const full = await createImageBitmap(blob);

  const sx = Math.max(0, Math.round(rect.x * dpr));
  const sy = Math.max(0, Math.round(rect.y * dpr));
  const sw = Math.min(full.width - sx, Math.round(rect.w * dpr));
  const sh = Math.min(full.height - sy, Math.round(rect.h * dpr));
  if (sw < 8 || sh < 8) throw new Error("Selected region is too small");

  const scale = Math.min(1, MAX_DIM / Math.max(sw, sh));
  const w = Math.max(1, Math.round(sw * scale));
  const h = Math.max(1, Math.round(sh * scale));

  const canvas = new OffscreenCanvas(w, h);
  canvas.getContext("2d").drawImage(full, sx, sy, sw, sh, 0, 0, w, h);
  full.close();

  const png = await canvas.convertToBlob({ type: "image/png" });
  return blobToBase64(png);
}

async function blobToBase64(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}
