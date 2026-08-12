import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = fs.readFileSync(new URL("../src/lib/route-availability.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const commonJsModule = { exports: {} };
vm.runInNewContext(compiled, { module: commonJsModule, exports: commonJsModule.exports, process: { env: { NODE_ENV: "test" } }, Set });

const { ROUTE_AVAILABILITY, getRouteAvailability, isRouteAvailable, validateRouteManifest } = commonJsModule.exports;
const marketScanner = ROUTE_AVAILABILITY[0];
const marketIntelligence = ROUTE_AVAILABILITY[1];

assert.deepEqual(Array.from(validateRouteManifest()), []);
assert.deepEqual(Array.from(marketScanner.paths), ["/market-scanner"]);
assert.equal(marketScanner.buildSwitch, "NEXT_PUBLIC_ENABLE_MARKET_SCANNER");
assert.deepEqual(Array.from(marketIntelligence.paths), ["/markets"]);
assert.equal(marketIntelligence.buildSwitch, "NEXT_PUBLIC_ENABLE_MARKET_INTELLIGENCE");
assert.equal(marketIntelligence.runtimePolicy, "MARKET_INTELLIGENCE_ENABLED");
assert.equal(getRouteAvailability("/markets/AAPL")?.featureId, "market-intelligence");
assert.equal(isRouteAvailable("/markets/AAPL", "analyst"), true);
assert.equal(isRouteAvailable("/markets/AAPL", "reviewer"), true);
assert.equal(isRouteAvailable("/markets/AAPL", "owner"), true);
assert.equal(isRouteAvailable("/markets/AAPL", "admin"), true);
assert.equal(isRouteAvailable("/markets/AAPL", "viewer"), false);
assert.match(
  validateRouteManifest([marketScanner, { ...marketScanner, featureId: "operations" }]).join("\n"),
  /Duplicate route prefix/,
);
assert.match(
  validateRouteManifest([{ ...marketScanner, roles: new Set() }]).join("\n"),
  /invalid role declaration/,
);
assert.match(
  validateRouteManifest([{ ...marketScanner, dedicatedSwitch: false }]).join("\n"),
  /dedicated exposure switch/,
);
assert.match(
  validateRouteManifest([marketScanner], { NODE_ENV: "production", NEXT_PUBLIC_ENABLE_LABS: "true" }).join("\n"),
  /forbidden in production/,
);

console.log("Route availability manifest tests passed");
