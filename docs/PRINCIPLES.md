# Core Principles

1. **Markdown-first.** Plain documentation does not need JSON.
2. **Progressive structuring.** Переводить Markdown в managed structured resource только когда это даёт реальную пользу.
3. **Structured data live with docs.** Canonical structured resources находятся внутри documentation tree.
4. **Mirrored structure.** `docs/_structured/...` зеркалит human-facing paths.
5. **Output path belongs to resource metadata.** Managed JSON сам указывает materialization target path.
6. **JSON contains data, not dependency logic.** Dependency semantics реализуются в code.
7. **Reserved metadata envelope.** Engine metadata живёт отдельно под `$docengine`, domain data — под `data`.
8. **Raw objects are immutable.** Derived values создаются в новых objects.
9. **Generic deserialization.** Поля structured resource автоматически становятся object fields через schema/model adapter.
10. **Code only where logic exists.** Простые stored fields не требуют project-specific code; derived relationships требуют builders/validators.
11. **Dependencies can be granular.** Canonical v0.1 refs address field / resource / whole plain file; many-input aggregation records the exact refs actually read.
    - Для plain Markdown в v0.1 поддерживается whole-file dependency. Если нужна dependency на часть документа, эту часть переводят в structured JSON; section-level Markdown addressing не используется.
    - `collection` is conceptual aggregate semantics in v0.1, not a first-class persisted `collection://` ref. Changing membership must itself be represented by an addressable input when membership affects the result.
12. **Only relevant upstream state is snapshotted.** Baseline хранит dependency slice, не весь мир.
13. **Change != semantic invalidity.** Upstream change автоматически снимает подтверждение актуальности, но не доказывает ошибочность target.
14. **Semantic review is external judgment.** Человек/AI принимает `still-valid` или `updated`.
15. **Runtime state is machine-owned.** Не редактировать dependency state вручную в обычном workflow.
16. **CLI is canonical control surface.** Human-friendly stdout + `--json` for AI/CI.
17. **Generated views are replaceable.** Их можно удалить и clean regenerate.
18. **Release must be reproducible.** Clean rebuild/materialize + verify перед package/release.
19. **History is append-only.** Validation/invalidation/rebuild decisions должны иметь event trail.
20. **Engine is reusable.** Никаких research-specific assumptions в core runtime.
21. **Project code mirrors produced targets.** `docs/<path>.md`, `docs/_structured/<path>.json` and `docengine_project/builders/<path>.py` share the logical target path; semantic rules mirror targets under `dependency_rules/`. Placement still requires explicit project-package registration.
22. **Project Python is trusted/cooperative.** The extension boundary is not a security sandbox; tracked dependency guarantees require mediated reads and do not prevent arbitrary Python side effects.
