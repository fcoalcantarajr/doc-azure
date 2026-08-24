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
- Response shape: Returns `ProcessInfo[]` array with fields: `processId` (GUID), `name`, `referenceName`, `type` (system/inherited/custom), `color`, `description`, `url`, etc.
- Notes: To find "Processo-Agil" processTypeId, filter the response array by `name` or `referenceName`.

---

### Work Item Types of a Process
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types/list
- Query params: `api-version`, `$expand`
- Response shape: Returns `WorkItemType[]` array with fields: `referenceName` (e.g., "Microsoft.VSTS.Common.UserStory"), `name` (display name), `description`, `customization`, `color`, `icon`, `url`, `isDisabled`
- Notes: `referenceName` URL-decoded is the identifier used in subsequent endpoints.

---

### States of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes/{witRefName}/states?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/states/list
- Query params: `api-version`
- Response shape: Returns array of `WorkItemStateResultModel[]` with fields: `id` (GUID), `name` (e.g., "New"), `color`, `category` (Proposed/InProgress/Resolved/Completed), `order`, `url`
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
  the modern `required` property, not the legacy `alwaysRequired` fixture key.

---

### Layout of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes/{witRefName}/layout?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/layouts/get?view=azure-devops-rest-7.1
- Query params: `api-version`
- Response shape: Returns the process `FormLayout` with pages, sections,
  groups, and controls.
- Notes: Layout controls form tabs, groups, columns, and controls.

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
- Response shape: Returns object with `count` (integer) and `value` (array of `WorkItemTypeBehavior[]`) with fields: `behavior` (containing `id` and `url`), `isDefault`
- Notes: Behavior `id` format is `Custom.{GUID}` for custom behaviors.

The older preview `work/processdefinitions` layout and behavior routes were
discarded. Keeping them would contradict the forced 7.1 client boundary and
would split collection across two endpoint models without a material claim that
requires the legacy surface.

---

### List Behaviors of a Process (For Backlog Levels)
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/behaviors?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/behaviors/list
- Query params: `api-version`, `$expand` (Fields, CombinedFields)
- Response shape: Returns `Behavior[]` array with fields: `behaviorType`, `referenceName`, `name`, `description`, `url`, `backlogLevel`, `customizationType`
- Notes: Backlog levels include: RequirementsCategories (Epics), PortfolioBacklog (Features), IterationBacklog (Stories), TaskBacklog (Tasks).

---

## Verified learn.microsoft.com URLs

1. https://learn.microsoft.com/en-us/rest/api/azure/devops/wiki/pages/get-page-by-id
2. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/processes/list
3. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types/list
4. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/states/list
5. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/fields/get-work-item-type-fields?view=azure-devops-rest-7.1
6. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/layouts/get?view=azure-devops-rest-7.1
7. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/rules/list
8. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types-behaviors/list?view=azure-devops-rest-7.1
9. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/behaviors/list
10. https://learn.microsoft.com/en-us/azure/devops/accounts/use-personal-access-tokens-to-authenticate
