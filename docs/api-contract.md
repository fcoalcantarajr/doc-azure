# Azure DevOps REST API Contract

## Authentication

**Personal Access Token (PAT) via HTTP Basic Auth:**

The Authorization header is formed by base64-encoding the string `username:PAT` (where username can be any string or empty).

Example:
```
Authorization: Basic dXNlcm5hbWU6cGF0X3Rva2Vu
```

- Source: https://learn.microsoft.com/en-us/azure/devops/accounts/use-personal-access-tokens-to-authenticate
- Alternative curl format: `curl -u :<PAT> https://dev.azure.com/{org}/...`

**API Version:** The reviewed client forces `api-version=7.1` and discards any
caller-supplied override.

## Semantic read boundary

Read-only is determined by the HTTP method and the exact route together, not by
the method alone. The client permits GET only for the cataloged wiki, process,
and work-item read families. It permits POST only for the two query operations
documented below. Creation POST routes, PUT, PATCH, DELETE, method override,
absolute request URLs, and redirects are rejected before a second request can
occur.

Every real attempt records only its method and normalized route. Query values,
headers, and credentials never enter request receipts. Sensitive query keys or
values, including PAT variants, are rejected before transport. Query values are
copied immutable scalars, and POST bodies are validated from a detached JSON
round-trip before the first await. Exceptions contain only method, a templated
route, safe transport class, and/or HTTP status—never response bodies, query or
body values, credentials, or path identifiers. The client retries at most five
times and only for HTTP 408, 429, 500, 502, 503, and 504; it honors
`Retry-After` and never retries 401 or 403.

## Snapshot publication contract

`out/wiki` and `out/process` remain logical roots. New publications are
immutable directories under `<root>/snapshots/<generation>`; an atomically
replaced `<root>/CURRENT` file selects the complete generation. Writers capture
the selected generation at construction, then re-read it under an interprocess
`flock` and use compare-and-swap before validating, moving, or pointing to a new
generation. Older generations are retained.

Tasks 3–6 must call `resolve_snapshot_root(root)` before reading cached evidence.
If CURRENT exists, the resolver fails closed on a malformed pointer, missing or
symlink target, symlink artifact, incomplete manifest, non-exact artifact set,
or hash mismatch; it never falls back. A flat legacy root is accepted read-only
only when CURRENT is absent and its complete manifest, exact artifact set, and
hashes verify. Task 4 may seed a partial refresh only by reading the resolved
generation and writing each retained artifact through `SnapshotWriter`.

The pointer replacement protects readers from process crashes before CURRENT is
swapped. The implementation does not claim power-loss durability because it
does not fsync files and parent directories. No garbage collection is performed
in this audit; avoiding destructive cleanup preserves prior evidence and keeps
post-publication cleanup failures from changing a successful result.

---

## Endpoints

### Execute a WIQL query (query-only POST)

- Method+URL: `POST https://dev.azure.com/{organization}/{project}/_apis/wit/wiql?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/wiql/query-by-wiql?view=azure-devops-rest-7.1
- Body: exactly one non-empty `query` string.
- Safety classification: reads matching work-item IDs; it does not create a
  stored query or mutate a work item. The superficially similar query-creation
  routes are not allowlisted.

### Read work items in one batch (query-only POST)

- Method+URL: `POST https://dev.azure.com/{organization}/{project}/_apis/wit/workitemsbatch?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/get-work-items-batch?view=azure-devops-rest-7.1
- Body: 1–200 integer `ids`, with only the documented optional `fields`,
  `$expand`, and `errorPolicy` members.
- Safety classification: retrieves existing work items; no creation or update
  route is allowlisted.

### Wiki Page By ID With Content
- Method+URL: `GET https://dev.azure.com/{organization}/{project}/_apis/wiki/wikis/{wikiIdentifier}/pages/{id}?includeContent=true&api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wiki/pages/get-page-by-id
- Query params: `includeContent`, `recursionLevel`, `versionDescriptor.*`, `api-version`
- Response shape: Returns `WikiPage` object with fields: `id`, `path`, `title`, `url`, `content` (when `includeContent=true`), `childPath`, `mergedPageContent`, etc.
- Notes: `includeContent=true` returns the page content inline in the `content` field as markdown. Content negotiation via `Accept` header controls format (Markdown, HTML, etc.).

---

### List All Processes
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/processes/list
- Query params: `api-version`, `$expand`
- Response shape: Returns a `count`/`value` envelope. Each process entry uses
  `typeId` as its API identifier and also includes fields such as `name`,
  `referenceName`, `customizationType`, `parentProcessTypeId`, `isEnabled`, and
  `isDefault` when applicable.
- Notes: Discovery requires exactly one entry whose `name` is exactly
  `Processo-Agil`. Zero or multiple matches fail closed. The selected `typeId`
  is the `{processId}` route segment; it is not inferred from array position or
  from an undocumented `processId` alias. The unfiltered response is retained
  as `processes.json`.

### Get the Selected Process

- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/processes/get
- Query params: `api-version`, `$expand`
- Response shape: A process object whose `typeId` and `name` must match the
  exact entry selected from the process list.
- Notes: The complete object is retained as `process.json` before per-WIT
  interpretation.

---

### Work Item Types of a Process
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types/list
- Query params: `api-version`, `$expand`
- Response shape: Returns a `count`/`value` envelope whose work-item entries
  include `referenceName`, `name`, `description`, `customization`, `color`,
  `icon`, `url`, and `isDisabled`.
- Notes: The complete index is retained as `workitemtypes.json`, including
  disabled entries. Every `referenceName` is validated as a collision-free
  route/file segment and used unchanged in subsequent routes. A versioned
  `artifact-map.json` maps it to its five local evidence files.

---

### States of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes/{witRefName}/states?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/states/list
- Query params: `api-version`
- Response shape: Returns a `count`/`value` envelope of
  `WorkItemStateResultModel` objects with fields including `id`, `name`,
  `color`, `stateCategory` (Proposed/InProgress/Resolved/Completed), `order`,
  and `url`.
- Notes: These are the customized states for the process-level WIT, accessible at process definition level.

---

### Fields of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes/{witRefName}/fields?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/fields/get-work-item-type-fields?view=azure-devops-rest-7.1
- Query params: `api-version`
- Response shape: Returns an envelope whose `value` entries are
  `ProcessWorkItemTypeField` objects with fields including `referenceName`,
  `name`, `type`, `required`, `readOnly`, `defaultValue`, `allowGroups`,
  `customization`, and `url`.
- Notes: Contains both system and custom fields. Requiredness comparisons use
  the modern `required` property when Azure returns it, not the legacy
  `alwaysRequired` fixture key. Absence is preserved as undeclared rather than
  normalized to `false`.

---

### Layout of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes/{witRefName}?$expand=layout&api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types/get?view=azure-devops-rest-7.1
- Query params: `api-version`, `$expand=layout`
- Response shape: Returns the complete raw `ProcessWorkItemType`, including
  its identity and nested `layout` property. `layout.pages` contains sections,
  groups, and controls.
- Notes: The direct documented `.../{witRefName}/layout` GET returned HTTP 400
  for the inherited system Test Case WIT in the live organization. The equally
  documented base-WIT GET with `$expand=layout` returned that WIT and its layout
  successfully. The collector therefore uses the latter for every WIT, keeps
  the complete raw response, and verifies `referenceName` before traversing
  `/layout/pages`. This is an observed compatibility choice, not a claim that
  the direct endpoint is undocumented or universally unsupported.

---

### Rules of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes/{witRefName}/rules?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/rules/list
- Query params: `api-version`
- Response shape: Returns object with `count` (integer) and `value` (array of `RuleModel[]`) with fields: `id`, `name`, `conditions`, `actions`, `isDisabled`, `customizationType`, `url`
- Notes: Rules can be custom (user-created), inherited, or system.

---

### Behaviors of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypesbehaviors/{witRefName}/behaviors?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types-behaviors/list?view=azure-devops-rest-7.1
- Query params: `api-version`
- Response shape: Returns an object with `count` and `value`; each
  `WorkItemTypeBehavior` contains `behavior.id` and `isDefault`.
- Notes: Behavior `id` format is `Custom.{GUID}` for custom behaviors.
  `isLegacyDefault` is retained when Azure returns it but is not required by
  the collector because the official response may omit it.

The older preview `work/processdefinitions` layout and behavior routes were
discarded. Keeping them would contradict the forced 7.1 client boundary and
would split collection across two endpoint models without a material claim that
requires the legacy surface.

---

### List Behaviors of a Process (For Backlog Levels)
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/behaviors?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/behaviors/list
- Query params: `api-version`, `$expand` (Fields, CombinedFields)
- Response shape: Returns a `count`/`value` envelope of process behaviors. The
  complete objects, including `referenceName` and integer `rank`, are retained
  without field filtering.
- Notes: Rank is the evidence used to compare backlog hierarchy. No rank is
  inferred from response order.

## Complete process snapshot

A current process snapshot contains four raw global responses
(`processes.json`, `process.json`, `workitemtypes.json`, and `behaviors.json`),
one versioned `artifact-map.json`, and fields, states, rules, layout, and WIT
behavior-association payloads for every indexed work-item type, including
disabled types. Lists must be `count`/`value` envelopes; each layout artifact is
the complete expanded Work Item Type response with matching `referenceName` and
nested `layout.pages`. A 404 or malformed family aborts staging instead of
becoming an empty list. Artifact-map schema 2 distinguishes these expanded raw
responses from the earlier root-`pages` layout shape. A non-refresh run reuses
other valid evidence but refetches stale layout artifacts before publication.

Without `--refresh`, a complete snapshot is returned before settings, PAT,
client, clock, or coroutine creation. A valid partial generation is copied into
a new staging generation byte-for-byte, and only missing raw artifacts are
requested. A second complete-cache check closes the concurrent-publication
race. With `--refresh`, every artifact is requested again. Any failure leaves
the previously selected CURRENT generation unchanged.

---

## Verified learn.microsoft.com URLs

1. https://learn.microsoft.com/en-us/rest/api/azure/devops/wiki/pages/get-page-by-id
2. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/processes/list
3. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types/list
4. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/states/list
5. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/fields/get-work-item-type-fields?view=azure-devops-rest-7.1
6. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types/get?view=azure-devops-rest-7.1
7. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/rules/list
8. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types-behaviors/list?view=azure-devops-rest-7.1
9. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/behaviors/list
10. https://learn.microsoft.com/en-us/azure/devops/accounts/use-personal-access-tokens-to-authenticate
