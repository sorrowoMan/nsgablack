// Build in a disposable task cache, then copy the resulting offline assets.
import {build} from "esbuild";
import {readFile, writeFile} from "node:fs/promises";
import {createHash} from "node:crypto";

const result = await build({entryPoints: ["editor.js"], bundle: true, minify: true,
  target: "es2020", legalComments: "eof", outfile: "editor.bundle.js", metafile: true});
const packages = new Set();
for (const name of Object.keys(result.metafile.inputs)) {
  const match = name.match(/node_modules\/((?:@[^/]+\/)?[^/]+)\//);
  if (match) packages.add(match[1]);
}
const versions = {}, licenses = [];
for (const name of [...packages].sort()) {
  const pkg = JSON.parse(await readFile(`node_modules/${name}/package.json`, "utf8"));
  versions[name] = pkg.version;
  let license;
  for (const file of ["LICENSE", "LICENSE.txt", "LICENSE.md"]) {
    try {license = await readFile(`node_modules/${name}/${file}`, "utf8"); break;}
    catch (error) {if (error.code !== "ENOENT") throw error;}
  }
  if (!license) throw new Error(`Missing bundled dependency license: ${name}`);
  licenses.push(`${name}@${pkg.version} (${pkg.license})\n${license.trim()}\n`);
}
const bundle = await readFile("editor.bundle.js");
const assets = {};
for (const name of ["index.html", "editor.css", "editor.js"]) {
  const bytes = await readFile(name);
  assets[name] = {bytes: bytes.byteLength, sha256: createHash("sha256").update(bytes).digest("hex")};
}
await writeFile("THIRD_PARTY_LICENSES.txt", licenses.join("\n--------------------\n\n"));
await writeFile("build-manifest.json", JSON.stringify({
  schema: "nsgablack.workspace-editor-assets/v1", bundle: "editor.bundle.js",
  bytes: bundle.byteLength, sha256: createHash("sha256").update(bundle).digest("hex"),
  build: {esbuild: "0.28.2", target: "es2020", minified: true}, packages: versions,
  assets, presentation: {themes: ["dark", "light", "system"], default: "dark"}
}, null, 2) + "\n");
