#!/usr/bin/env bash
# دانلود کتابخانه‌های فرانت‌اند برای اجرای آفلاین
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/frontend/vendor"
FONTS="$VENDOR/fonts/vazir"
mkdir -p "$VENDOR" "$FONTS"

download() {
  local url="$1" dest="$2"
  if [ -f "$dest" ] && [ -s "$dest" ]; then
    echo "✓ $(basename "$dest")"
    return 0
  fi
  echo "↓ $(basename "$dest")"
  curl -fsSL "$url" -o "$dest"
}

# Chart.js
download "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" \
  "$VENDOR/chart.umd.min.js"

# SheetJS
download "https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js" \
  "$VENDOR/xlsx.full.min.js"

# Jalali datepicker
download "https://unpkg.com/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.css" \
  "$VENDOR/jalalidatepicker.min.css"
download "https://unpkg.com/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.js" \
  "$VENDOR/jalalidatepicker.min.js"

# Vazir font
for variant in "Regular" "Bold" "Medium" "Light"; do
  download "https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/Vazir-${variant}.woff2" \
    "$FONTS/Vazir-${variant}.woff2"
done

cat > "$FONTS/font-face.css" <<'CSS'
@font-face {
  font-family: Vazir;
  src: url('Vazir-Regular.woff2') format('woff2');
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: Vazir;
  src: url('Vazir-Bold.woff2') format('woff2');
  font-weight: bold;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: Vazir;
  src: url('Vazir-Medium.woff2') format('woff2');
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: Vazir;
  src: url('Vazir-Light.woff2') format('woff2');
  font-weight: 300;
  font-style: normal;
  font-display: swap;
}
CSS

# Tailwind CSS — standalone CLI
TW_BIN="$ROOT/.tools/tailwindcss"
TW_SRC="$ROOT/frontend/css/tailwind-src.css"
TW_OUT="$VENDOR/tailwind.css"

if [ ! -f "$TW_SRC" ]; then
  cat > "$TW_SRC" <<'CSS'
@tailwind base;
@tailwind components;
@tailwind utilities;
CSS
fi

if [ ! -f "$TW_BIN" ]; then
  mkdir -p "$ROOT/.tools"
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64) TW_URL="https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.1/tailwindcss-linux-x64" ;;
    aarch64|arm64) TW_URL="https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.1/tailwindcss-linux-arm64" ;;
    *) echo "⚠ معماری $ARCH — tailwind از CDN در نصب بعدی ساخته می‌شود"; TW_URL="" ;;
  esac
  if [ -n "$TW_URL" ]; then
    curl -fsSL "$TW_URL" -o "$TW_BIN"
    chmod +x "$TW_BIN"
  fi
fi

if [ -x "$TW_BIN" ]; then
  echo "⚙ ساخت tailwind.css (کامل + ریسپانسیو) ..."
  "$TW_BIN" -c "$ROOT/frontend/tailwind.config.js" -i "$TW_SRC" -o "$TW_OUT" --minify
  echo "✓ tailwind.css ($(wc -c < "$TW_OUT" | tr -d ' ') bytes)"
else
  echo "⚠ tailwind.css ساخته نشد — اتصال اینترنت یا معماری را بررسی کنید"
fi

echo ""
echo "✓ vendor assets در $VENDOR"