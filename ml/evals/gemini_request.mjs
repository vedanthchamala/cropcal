// Bridges the eval harness (Python) to the hosted proxy's request builder so
// the harness sends byte-for-byte what production sends to Gemini.
// stdin: {"images": {...}, "ctx": {...}, "settings": {...}}  stdout: {url, headers, body}
import { buildRequest } from "../../proxy/src/gemini.js";

let input = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) input += chunk;
const { images, ctx, settings } = JSON.parse(input);
process.stdout.write(JSON.stringify(buildRequest(images, ctx, settings)));
