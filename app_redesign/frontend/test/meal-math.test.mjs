import assert from "node:assert/strict";
import { test } from "node:test";
import { mealArcs } from "../src/meal-math.mjs";

const breakfast = { kind: "breakfast", label: "Bữa sáng" };
const lunch = { kind: "lunch", label: "Bữa trưa" };

test("meal energy ratio and order match source values", () => {
  const [first, second] = mealArcs([{ ...breakfast, kcal: 400 }, { ...lunch, kcal: 600 }]);
  assert.equal(first.kind, breakfast.kind);
  assert.equal(second.kind, lunch.kind);
  assert.equal(first.start, 0.675);
  assert.equal(second.start, 40.675);
  assert.equal(second.length - first.length, 20);
});

test("does not draw a full circle from a partial or empty record", () => {
  assert.deepEqual(mealArcs([{ ...breakfast, kcal: 400 }, { ...lunch, kcal: null }]), []);
  assert.deepEqual(mealArcs([{ ...breakfast, kcal: 0 }]), []);
  assert.deepEqual(mealArcs([{ ...breakfast, kcal: Infinity }]), []);
});

test("a recorded zero produces no segment without hiding other meals", () => {
  const [only] = mealArcs([{ ...breakfast, kcal: 0 }, { ...lunch, kcal: 400 }]);
  assert.equal(only.kind, lunch.kind);
  assert.equal(only.length, 98.65);
});
