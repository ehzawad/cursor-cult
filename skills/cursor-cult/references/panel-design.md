# Panel design

A useful panel maximizes independent information, not headcount.

## Add a role when

- it has a distinct evidence source;
- it owns a different failure model;
- it can run a decisive check another role cannot;
- the task needs domain knowledge beyond general code reasoning; or
- independence is valuable because the implementation narrative may bias review.

## Do not add a role when

- its prompt is merely a synonym for another role;
- the task is too small to amortize delegation overhead;
- all roles would inspect the same five lines and return the same conclusion;
- the role would become a second writer in the same worktree; or
- the parent can perform the step mechanically without an extra model call.

## Dynamic specialist examples

The parent can invoke multiple `cursor-cult-specialist` instances with mandates such as:

- “Assess PostgreSQL migration and locking behavior.”
- “Verify the current Cursor SDK signature and deprecations from official sources.”
- “Audit Kubernetes rollout and rollback semantics.”
- “Evaluate accessibility and keyboard behavior for this UI flow.”
- “Trace model-serving latency and observability implications.”

The specialist name stays stable; the delegated lens is dynamic.
