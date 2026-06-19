# CHANGELOG


## v3.0.1 (2026-06-18)

### Bug Fixes

- Add authenitkate + tests
  ([`96aac7e`](https://github.com/arkitektio/koherent/commit/96aac7e46e3c13617e6681f95ce8d98fb71539ee))


## v3.0.0 (2026-06-18)

### Features

- Deserailze from new rekuest token
  ([`cc65724`](https://github.com/arkitektio/koherent/commit/cc6572443fe265d04137c32ece65ef3eaadddfe2))


## v2.0.0 (2026-06-12)

### Features

- Batch effective changes across instances and trim task resolution queries
  ([`f823de4`](https://github.com/arkitektio/koherent/commit/f823de42416232c2436c75d1245555d79ca6544e))

Performance: - effectiveChanges now resolves through a per-request DataLoader (one per history
  model), so all instances selected in an operation share a single history_relation_id__in
  sibling-history query instead of one query per instance. Diffs are computed inside the loader's
  sync hop, where diff_against may query for m2m-tracked fields. - get_or_create_task() checks for
  the existing Task row before resolving the assigner, so requests under an already-persisted task
  cost one query instead of two. An existing row is now returned even when the auth context carries
  no organization (the org only guards creation). - KoherentExtension clears the resolved-Task
  contextvar per operation, so a cached row can never leak between operations.

API: - ProvenanceField accepts related_name and bases (defaults unchanged, no migrations needed). -
  The loader registry uses kante's public get_extension/set_extension instead of reaching into
  request._extensions. - New get_current_task() accessor next to get_current_task_payload(), both
  re-exported from the package root. - TaskAdmin gains raw_id_fields, date_hierarchy and
  readonly_fields.

BREAKING CHANGE: ProvenanceEntry.effective_changes is an async resolver now and requires async
  schema execution (schema.execute); execute_sync no longer works for queries selecting
  effectiveChanges.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

### Breaking Changes

- Provenanceentry.effective_changes is an async resolver now and requires async schema execution
  (schema.execute); execute_sync no longer works for queries selecting effectiveChanges.


## v1.0.1 (2026-06-12)

### Bug Fixes

- New tests
  ([`571f1aa`](https://github.com/arkitektio/koherent/commit/571f1aacd160e842527f9d80436d0ac71e0f387f))


## v1.0.0 (2026-06-12)

### Features

- Persist validated rekuest tasks and link history entries to them
  ([`9d74359`](https://github.com/arkitektio/koherent/commit/9d743596f67df6ac82febbaf044dd1714cd75b6f))

Complete reimplementation of the assignation tracking:

- New Task model: one row per rekuest task id, snapshotting the validated Rekuest-Task header
  (assigner resolved to a local user, raw sub kept, app, action, args, organization). -
  ProvenanceEntryModel: the raw assignation_id CharField is replaced by a real task FK, so history
  entries join to the full task context. - KoherentExtension now consumes the validated task that
  authentikate attaches to the request instead of the unvalidated x-assignation-id header (which is
  gone, along with all backward compatibility). - get_or_create_task() lazily persists the task once
  per request (contextvar-cached); the history signal calls it so every change made during a task is
  attributed even without explicit wiring. - Websocket mutation rejection now checks the parsed
  operation type in on_execute (operation_name never equalled "mutation"). - Test rig migrated to
  authentikate 2 static tokens; e2e tests cover task snapshotting, row reuse, cross-user assigners
  and rejection of non-member assigners.

BREAKING CHANGE: requires authentikate>=2.0.1 (release it first; uv.lock must be regenerated once it
  is on PyPI). Consuming services must migrate (assignation_id is dropped from historical tables)
  and stamp created_through FKs themselves where they want direct links.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

### Breaking Changes

- Requires authentikate>=2.0.1 (release it first; uv.lock must be regenerated once it is on PyPI).
  Consuming services must migrate (assignation_id is dropped from historical tables) and stamp
  created_through FKs themselves where they want direct links.


## v0.2.0 (2025-05-06)

### Features

- Add date field to provenance tracking test
  ([`ca6f7f9`](https://github.com/arkitektio/koherent/commit/ca6f7f9bcefe36f69e993abf7515a9a891ac193f))


## v0.1.1 (2025-05-06)


## v0.1.0 (2025-05-06)

### Bug Fixes

- Add pytest-cov
  ([`7f0647f`](https://github.com/arkitektio/koherent/commit/7f0647f7ae716db553df5ff0b04a7a190d323390))

- Add semantic release
  ([`0871375`](https://github.com/arkitektio/koherent/commit/0871375e1bc775a8eddb6634dccdbd2886462b76))

### Features

- Refactor code structure for improved readability and maintainability
  ([`eb19b74`](https://github.com/arkitektio/koherent/commit/eb19b742c52dda9cbe507435dcafc49c6b699309))

- Restructure workflows and improve code quality with updated tests and coverage
  ([`ab61c33`](https://github.com/arkitektio/koherent/commit/ab61c3375ede4ea52345cac6a17367cc4f3d2093))
