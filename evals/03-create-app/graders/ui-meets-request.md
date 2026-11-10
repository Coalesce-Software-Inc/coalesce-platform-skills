---
type: llm
focus: {source: file, path: apps/node-browser/index.html}
weight: 1
---
This is the app's page, `apps/node-browser/index.html`. The app runs in a sandboxed iframe on its own origin inside Coalesce. Judge the code that executes, not comments. Score PASS only if ALL hold:

1. The page fetches the node list from its own server with a relative or root-relative URL (for example `/api/nodes`), not a hard-coded `http://localhost:<port>` URL.
2. It shows nodes grouped by storage location and shows each node's column count.
3. It has a search input whose `input`, `change`, `keyup` or submit handler filters the shown nodes by name.
4. Values from the server (node names, locations, file paths) never reach the page as HTML. FAIL only if code assigns or concatenates such a value into `innerHTML`, `outerHTML`, `insertAdjacentHTML`, or `document.write` without escaping it. Setting `textContent`, using `createTextNode`, `append`/`replaceChildren` with strings, or setting plain properties such as `title` or `className` is safe.
5. Errors are shown inside the page. FAIL only if code actually calls `alert(`, `confirm(` or `prompt(`; a comment mentioning them does not count.

If any of 1-5 fails, FAIL and quote the offending line.
