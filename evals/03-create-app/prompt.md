---
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Skill, Read, Glob, Grep, Bash, Write, Edit]
runs: 3
---
This directory is a Coalesce Transform workspace. Build a Coalesce workspace app for it in `apps/node-browser/` so I can open it from the Apps menu in Coalesce Desktop.

The app should list every node in the workspace grouped by storage location, show how many columns each node has, and have a search box that filters the list by node name. Put the server in `apps/node-browser/server.js` and the page in `apps/node-browser/index.html`.

Before you finish, start the app the way Coalesce would start it and show that it serves both the page and the node list with the correct column counts. This sandbox may refuse to let a process listen on a network port; if it does, say so and test the server's request handling another way instead of skipping the check.

You are working alone with no human available, so do not ask questions. Do not change any file outside `apps/node-browser/`, and do not commit or push. In your final message, list the files you created, the exact command you used to start the app, and the node list it returned. If something did not work, say so plainly.
