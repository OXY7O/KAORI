import { readFile } from "node:fs/promises";

const outputPath = new URL("../app/static/css/output.css", import.meta.url);
const requiredFragments = [
  "--kaori-brand-primary",
  ".bg-kaori-primary",
  ".bg-surface-card",
  ".border-outline-default",
  ".text-content-primary",
];

let css;
try {
  css = await readFile(outputPath, "utf8");
} catch (error) {
  console.error("KAORI CSS validation failed: app/static/css/output.css is missing.");
  console.error(error.message);
  process.exit(1);
}

const missingFragments = requiredFragments.filter(
  (fragment) => !css.includes(fragment),
);

if (missingFragments.length > 0) {
  console.error(
    "KAORI CSS validation failed: the compiled stylesheet is missing required design tokens/utilities:",
  );
  for (const fragment of missingFragments) {
    console.error(`- ${fragment}`);
  }
  console.error(
    "Build from frontend/styles.css. Do not use the obsolete frontend/src/input.css entrypoint.",
  );
  process.exit(1);
}

console.log(
  "KAORI CSS validation passed: Violet Infrastructure tokens and utilities are present.",
);
