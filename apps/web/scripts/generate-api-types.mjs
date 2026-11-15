import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const schemaUrl = pathToFileURL(resolve("openapi.json")).href;
const outputPath = resolve("src/lib/api/schema.d.ts");
const schema = await openapiTS(schemaUrl);

await writeFile(outputPath, astToString(schema));
console.log(`Generated ${outputPath}`);
