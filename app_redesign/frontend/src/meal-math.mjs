const PALETTE = {
  breakfast: "#dced96",
  lunch: "#ffb995",
  dinner: "#99d0c7",
  snack: "#d4bcf2",
};

export const mealColor = (kind) => PALETTE[kind] ?? "#e1c79b";

// Segments describe the energy distribution across recorded meals.
export function mealArcs(meals) {
  if (meals.length === 0 || meals.some(({ kcal }) => !Number.isFinite(kcal) || kcal < 0)) return [];
  const total = meals.reduce((sum, { kcal }) => sum + kcal, 0);
  if (!(total > 0) || !Number.isFinite(total)) return [];
  let offset = 0;
  return meals.map(({ kind, label, kcal }) => {
    const fraction = 100 * kcal / total;
    const gap = Math.min(1.35, fraction / 4);
    const arc = {kind, label, kcal, start: offset + gap / 2, length: fraction - gap, color: mealColor(kind)};
    offset += fraction;
    return arc;
  }).filter(({ length }) => length > 0);
}
