// Bridges the eval harness (Python) to the Gemini extension's request builder
// so the harness sends byte-for-byte what extension-gemini sends.
// stdin: {"images": {...}, "ctx": {...}, "settings": {...}}  stdout: {url, headers, body}
import { buildRequest } from "../../extension-gemini/lib/providers/gemini.js";

let input = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) input += chunk;
const { images, ctx, settings } = JSON.parse(input);
process.stdout.write(JSON.stringify(buildRequest(images, ctx, settings)));
