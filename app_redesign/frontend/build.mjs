import { build } from "esbuild";
import { execFile } from "node:child_process";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const root = fileURLToPath(new URL(".", import.meta.url));
const dist = join(root, "dist");
await mkdir(dist, { recursive: true });
const tailwind = join(root, "node_modules/@tailwindcss/cli/dist/index.mjs");
const { stdout: utilities } = await promisify(execFile)(
  process.execPath, [tailwind, "-i", "src/shadcn.css", "--minify"],
  { cwd: root, maxBuffer: 2 ** 20 },
);
for (const name of ["meal-studio", "sidebar"]) {
  const styles = await readFile(join(root, `src/${name}.css`), "utf8");
  await writeFile(join(dist, `${name}.css`), utilities + "\n" + styles);
}

await build({
  absWorkingDir: root,
  entryPoints: ["src/meal-studio.tsx", "src/sidebar.tsx"],
  bundle: true,
  jsx: "automatic",
  format: "esm",
  target: ["chrome120", "firefox121"],
  minify: true,
  legalComments: "inline",
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  alias: { "@": join(root, "src") },
  loader: { ".jpg": "dataurl" },
  outdir: dist,
});

const fontRoot = join(root, "node_modules/@fontsource/be-vietnam-pro");
const css = [];
for (const weight of [400, 600, 800]) {
  const source = await readFile(join(fontRoot, `${weight}.css`), "utf8");
  const faces = source.match(/@font-face\s*\{[^}]+\}/g) ?? [];
  for (const face of faces) {
    const file = face.match(/files\/(be-vietnam-pro-(?:latin|latin-ext|vietnamese)-\d+-normal\.woff2)/)?.[1];
    if (!file) continue;
    const base64 = (await readFile(join(fontRoot, "files", file))).toString("base64");
    css.push(face.replace(/src:[^;]+;/, `src:url("data:font/woff2;base64,${base64}") format("woff2");`));
  }
}
if (css.length !== 9) throw new Error("Expected local Latin, Latin Extended and Vietnamese font faces.");
await writeFile(join(dist, "fonts.css"), css.join("\n"));

// Keep the redistribution notices beside the generated bundle.
const notices = ["### shadcn/ui\n\n" + await readFile(join(root, "SHADCN-LICENSE.md"), "utf8")];
const lock = JSON.parse(await readFile(join(root, "package-lock.json"), "utf8"));
for (const [path, meta] of Object.entries(lock.packages)) {
  if (!path || meta.dev || meta.optional || meta.inBundle) continue;
  const folder = join(root, path);
  const names = await readdir(folder);
  const noticesForPackage = names.filter((name) => /^(licen[cs]e|notice|ofl)(\.|$)/i.test(name));
  const texts = await Promise.all(noticesForPackage.map((name) => readFile(join(folder, name), "utf8")));
  notices.push(`### ${path} · ${meta.version} · ${meta.license ?? "see below"}\n\n${texts.join("\n\n")}`);
}
await writeFile(join(dist, "THIRD_PARTY_NOTICES.txt"), notices.join("\n\n"));
