import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";

const root = resolve(__dirname, "..");

it("uses the BorderCart AI cross-border storefront brand", () => {
  const index = readFileSync(resolve(root, "index.html"), "utf8");
  const app = readFileSync(resolve(root, "src/App.tsx"), "utf8");
  const workspace = readFileSync(resolve(root, "src/components/ContextWorkspace.tsx"), "utf8");

  expect(index).toContain("BorderCart AI");
  expect(index).toContain("跨境智选助手");
  expect(app).toContain("BorderCart AI");
  expect(workspace).toContain("BorderCart AI");
  expect(index).not.toContain("Globex 环球好物");
});
