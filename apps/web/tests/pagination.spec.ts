import { expect, test } from "@playwright/test";
import { chainCursor, mergeUniqueById } from "../lib/pagination";

test("cursor chains stay exhausted once the final page reports no cursor", () => {
  expect(chainCursor(undefined, "first-page")).toBe("first-page");
  expect(chainCursor(undefined, null)).toBeNull();
  expect(chainCursor(undefined, undefined)).toBeNull();
  expect(chainCursor("page-2", "first-page")).toBe("page-2");
  expect(chainCursor(null, "first-page")).toBeNull();
});

test("mergeUniqueById preserves order and drops duplicates", () => {
  const first = [{ id: "a" }, { id: "b" }];
  const extra = [{ id: "b" }, { id: "c" }];
  expect(mergeUniqueById(first, extra, (item) => item.id).map((item) => item.id)).toEqual(["a", "b", "c"]);
  expect(mergeUniqueById(first, [], (item) => item.id).map((item) => item.id)).toEqual(["a", "b"]);
});
