// norm-bar.js – Apple Health Style Normbereich-Balken
// Rendert einen farbigen Balken: grün = Normbereich, rot/orange = außerhalb, Punkt = aktueller Wert

/**
 * Parst einen Normbereich-String in {min, max}
 * Formate: "3.7-10.0", "< 0.50", "<0.50", "0.1-0.6", "-0.49", "> 60"
 * Returns null wenn nicht parsebar
 */
export function parseNormbereich(normStr) {
  if (!normStr || typeof normStr !== "string") return null;
  const s = normStr.trim().replace(",", ".");

  // Ungültige Strings
  if (/^(abs|aut%?|rel%?|%)$/i.test(s)) return null;

  // Format: "< X" oder "<X" (nur Obergrenze)
  let m = s.match(/^<\s*-?\s*([\d.]+)$/);
  if (m) return { min: null, max: parseFloat(m[1]) };

  // Format: "> X" oder ">X" (nur Untergrenze)
  m = s.match(/^>\s*-?\s*([\d.]+)$/);
  if (m) return { min: parseFloat(m[1]), max: null };

  // Format: "X-Y" oder "X - Y" (Bereich) – Achtung: "-0.49" ist kein Bereich!
  m = s.match(/^([\d.]+)\s*[-–]\s*([\d.]+)$/);
  if (m) {
    const min = parseFloat(m[1]), max = parseFloat(m[2]);
    // Ungültig wenn min == max (z.B. "0.0-0.0" oder "0.00-0.00")
    if (min === max) return null;
    return { min, max };
  }

  // Format: "-X" (nur Obergrenze, z.B. "-0.49")
  m = s.match(/^-\s*([\d.]+)$/);
  if (m) return { min: null, max: parseFloat(m[1]) };

  // Format: Einzelne Zahl "200" → interpretiere als Obergrenze "< 200"
  m = s.match(/^([\d.]+)$/);
  if (m) return { min: null, max: parseFloat(m[1]) };

  return null;
}

/**
 * Rendert einen Norm-Bar als HTML-String
 * @param {number|string} wert - Aktueller Messwert
 * @param {string} normStr - Normbereich-String (z.B. "3.7-10.0")
 * @param {string} flag - "H", "L" oder ""
 * @returns {string} HTML-String des Balkens oder leerer String
 */
export function renderNormBar(wert, normStr, flag) {
  const norm = parseNormbereich(normStr);
  if (!norm) return "";

  // Wert parsen
  let val = typeof wert === "number" ? wert : parseFloat(String(wert).replace(",", ".").replace(/^[<>]\s*/, ""));
  if (isNaN(val)) return "";

  const normMin = norm.min;
  const normMax = norm.max;

  // Skala berechnen: Balken zeigt einen erweiterten Bereich um den Normbereich
  let scaleMin, scaleMax;

  if (normMin !== null && normMax !== null) {
    // Bereich: min-max
    const range = normMax - normMin;
    const padding = range * 0.4;
    scaleMin = Math.max(0, normMin - padding);
    scaleMax = normMax + padding;
  } else if (normMax !== null) {
    // Nur Obergrenze (< X)
    scaleMin = 0;
    scaleMax = normMax * 3;
  } else if (normMin !== null) {
    // Nur Untergrenze (> X)
    scaleMin = 0;
    scaleMax = normMin * 2;
  } else {
    return "";
  }

  // Wert muss in die Skala passen – erweitern wenn nötig
  if (val < scaleMin) scaleMin = val * 0.8;
  if (val > scaleMax) scaleMax = val * 1.1;

  const totalRange = scaleMax - scaleMin || 1;

  // Position des Werts auf dem Balken (0-100%)
  const valPos = Math.max(0, Math.min(100, ((val - scaleMin) / totalRange) * 100));

  // Position des Normbereichs auf dem Balken
  const normStartPos = normMin !== null ? Math.max(0, ((normMin - scaleMin) / totalRange) * 100) : 0;
  const normEndPos = normMax !== null ? Math.min(100, ((normMax - scaleMin) / totalRange) * 100) : 100;

  // Farbe des Punkts
  const dotColor = flag === "H" || flag === "L" ? "var(--red)" : "var(--green)";

  return `<div class="norm-bar" title="Wert: ${val} | Norm: ${normStr}">
    <div class="norm-bar-track">
      <div class="norm-bar-low" style="width:${normStartPos}%"></div>
      <div class="norm-bar-ok" style="left:${normStartPos}%;width:${normEndPos - normStartPos}%"></div>
      <div class="norm-bar-high" style="left:${normEndPos}%;width:${100 - normEndPos}%"></div>
      <div class="norm-bar-dot" style="left:${valPos}%;background:${dotColor}"></div>
    </div>
  </div>`;
}
