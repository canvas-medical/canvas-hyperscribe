// BMI from imperial inputs: (lbs / in^2) * 703. Returns a one-decimal number or null.
// Suppresses display when inputs (or the resulting BMI) are outside plausible bounds
// to avoid flashing absurd values while the user is mid-keystroke.
export function computeBmi(heightIn, weightLbs) {
  const h = typeof heightIn === 'string' ? parseFloat(heightIn) : heightIn;
  const w = typeof weightLbs === 'string' ? parseFloat(weightLbs) : weightLbs;
  if (h == null || w == null || !isFinite(h) || !isFinite(w) || h <= 0 || w <= 0) return null;
  const bmi = Math.round(((w / (h * h)) * 703) * 10) / 10;
  if (bmi < 5 || bmi > 100) return null;
  return bmi;
}
