import assert from "node:assert/strict";
import test from "node:test";

import { mapLimit } from "../src/pool.js";

test("mapLimit preserves order and enforces concurrency", async () => {
  let active = 0;
  let peak = 0;
  const result = await mapLimit([1, 2, 3, 4, 5], 2, async (value) => {
    active += 1;
    peak = Math.max(peak, active);
    await new Promise((resolve) => setTimeout(resolve, 5));
    active -= 1;
    return value * 10;
  });
  assert.deepEqual(result, [10, 20, 30, 40, 50]);
  assert.equal(peak, 2);
});
