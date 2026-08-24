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
values are rejected before transport. The client retries at most five times and
only for HTTP 408, 429, 500, 502, 503, and 504; it honors `Retry-After` and never
retries 401 or 403.

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
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes/{witRefName}/fields?api-version=4.1-preview.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/fields/get-work-item-type-fields
- Query params: `api-version`
- Response shape: Returns `FieldModel[]` array with fields: `referenceName`, `name`, `helpText`, `alwaysRequired`, `url`
- Notes: Uses `api-version=4.1-preview.1` (no 7.1 version available). Contains both system and custom fields. For `System.Title`, check `alwaysRequired=true`.

---

### Layout of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processdefinitions/{processId}/workItemTypes/{witRefName}/layout?api-version=4.1-preview.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processdefinitions/layout/get
- Query params: `api-version`
- Response shape: Returns `FormLayout` object with `xmlForm` (XAML layout string), `pageLayouts` array
- Notes: Uses `processdefinitions` API (not `processes`). Layout controls form tabs, groups, columns, and controls. System ID = `de0f680b-1280-4732-814c-96a006ac1d3a`. Uses `api-version=4.1-preview.1`.

---

### Rules of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processes/{processId}/workitemtypes/{witRefName}/rules?api-version=7.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/rules/list
- Query params: `api-version`
- Response shape: Returns object with `count` (integer) and `value` (array of `RuleModel[]`) with fields: `id`, `name`, `conditions`, `actions`, `isDisabled`, `customizationType`, `url`
- Notes: Rules can be custom (user-created), inherited, or system.

---

### Behaviors of a Work Item Type
- Method+URL: `GET https://dev.azure.com/{organization}/_apis/work/processdefinitions/{processId}/workitemtypes/{witRefName}/behaviors?api-version=4.1-preview.1`
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/processdefinitions/work-item-types/get-behaviors-for-work-item-type
- Query params: `api-version`
- Response shape: Returns object with `count` (integer) and `value` (array of `WorkItemTypeBehavior[]`) with fields: `behavior` (containing `id` and `url`), `isDefault`
- Notes: Uses `processdefinitions` API. Behavior `id` format: `Custom.{GUID}`. For latest behaviors list:

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
5. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/fields/get-work-item-type-fields
6. https://learn.microsoft.com/en-us/rest/api/azure/devops/processdefinitions/layout/get
7. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/rules/list
8. https://learn.microsoft.com/en-us/rest/api/azure/devops/processdefinitions/work-item-types/get-behaviors-for-work-item-type
9. https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/behaviors/list
10. https://learn.microsoft.com/en-us/azure/devops/accounts/use-personal-access-tokens-to-authenticate
