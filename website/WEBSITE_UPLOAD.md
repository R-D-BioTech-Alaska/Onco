# OncoForge Website Upload

This folder is the handoff for the agent building `https://rdbiotech.org/lab/oncoforge/`.

## Runtime Shape

The website and OncoForge have separate responsibilities:

```text
browser -> website login/session -> website server proxy -> OncoForge Python API
```

The browser must never receive `ONCOFORGE_API_KEY`. The website server verifies the user's login and role, then adds this header when it proxies a mission request:

```text
Authorization: Bearer <ONCOFORGE_API_KEY>
```

Account creation, password storage, email verification, password reset, rate limits, and user roles belong to the website. OncoForge does not store passwords or patient records.

## Files To Use

```text
oncoforge-client.js             browser-side API client
mission-request.example.json    complete first-mission request
oncoforge.env.example           private Python service configuration
../docs/WEBPAGE_BUILD_PACKET.md page routes, components, controls, and safety copy
```

## Python Service

The deployable WSGI application is:

```text
oncoforge.web_api:application
```

For a local connection test only:

```powershell
$env:ONCOFORGE_API_KEY="local-test-key"
python run_oncoforge.py serve-api --host 127.0.0.1 --port 8765
```

Production must run the WSGI application behind HTTPS using the hosting provider's Python process manager. Do not expose the standard-library development server directly to the internet.

Set these private server variables:

```text
ONCOFORGE_API_KEY=<long random secret shared only with the website server>
ONCOFORGE_OUTPUT_DIR=<private writable mission directory>
ONCOFORGE_ALLOWED_ORIGINS=https://rdbiotech.org
```

## Proxy Routes

Keep these routes on the same website origin:

```text
GET  /lab/oncoforge/api/health
GET  /lab/oncoforge/api/profiles
GET  /lab/oncoforge/api/profiles/{profile_id}
POST /lab/oncoforge/api/portal/missions
GET  /lab/oncoforge/api/portal/missions/{mission_id}
```

The health and profile routes are public. Mission creation and retrieval require the private API key. The website proxy must also require a valid user session before forwarding either mission route.

## Portal Connection

Copy `oncoforge-client.js` into the website source and import only the calls the portal uses:

```javascript
import {
  listOncoForgeProfiles,
  runOncoForgeMission,
} from "./oncoforge-client.js";

const profileData = await listOncoForgeProfiles();
const result = await runOncoForgeMission(missionFormValues);
```

Render `result.stage_cards` first. The detailed panels use:

```text
result.initial_interpretation
result.initial_recommendation
result.qsa_result
result.simulation
result.post_run_interpretation
result.research_loop_plan
result.hypothesis_index
```

Show `result.scope_notice` beside every scientific result panel.

## Required Server Controls

The Python API already rejects oversized bodies, unbounded cell-step workloads, unsafe output paths, oversized QSA requests, missing authentication, and malformed fields. The website must also apply per-account rate limits and prevent one account from retrieving another account's mission ID.

Do not add patient medical records, treatment instructions, clinical predictions, or claims that a simulation found a cure.

