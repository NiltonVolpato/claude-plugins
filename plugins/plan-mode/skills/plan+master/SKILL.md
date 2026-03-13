---
name: plan+master
description: Create a master plan that decomposes a system into independent modules. Each module will be implemented as a separate plan in its own git worktree.
argument-hint: <description of the system to build>
disable-model-invocation: true
---

# Master Plan Mode

You are creating a **master plan** — a high-level decomposition of a system into
independent modules. Each module will later be implemented as a separate plan
(using `plan+`) in its own git worktree by an autonomous agent.

**Workflow context:** This master plan will not be implemented all at once.
1. First, "Phase 0: Scaffolding" will be implemented to set up the foundation.
2. Then, multiple autonomous AI developer agents will be spun up in parallel.
3. Each agent gets assigned one module, reads its brief from this plan, creates
   its own detailed sub-plan (via `plan+`), and executes the code.

## How master plans differ from regular plans

| | Regular plan (`plan+`) | Master plan (`plan+master`) |
|---|---|---|
| **Granularity** | Implementation steps | Module decomposition |
| **Phases** | Testable code checkpoints | Independent modules |
| **Steps** | Code changes with snippets | Module brief (scope, interfaces, dependencies) |
| **Verification** | `pytest`, build commands | Module implemented and merged |
| **Who implements** | Same agent, same session | Separate agent per module, in its own worktree |
| **Detail level** | Low-level (code snippets, exact files) | High-level (briefs, not step-by-step instructions) |

## Rules

1. **No EnterPlanMode** — Write the plan files directly. Do not use Claude Code's built-in plan mode.
2. **No AskUserQuestion** — Brainstorm step by step. The user will interject when they see something wrong. Think out loud as you explore.
3. **Read-only exploration** — Only edit the plan and appendix files. Do not modify any project code. (Exception: you may write proof-of-concept code in `/tmp` — see Workflow step 2.)
4. **Appendix** — Codebase findings (file paths, API notes, patterns with file:line references) go in the appendix, keeping the plan scannable.
5. **Self-contained** — The plan + appendix must have enough context that a fresh agent in a worktree can implement any single module without re-exploring the entire codebase.
6. **High-level briefs, not implementation plans** — Do not write step-by-step implementation details for modules. Each module brief should give the downstream agent enough context to create its own detailed plan. Keep the master plan concise.

## Plan structure

The master plan has these top-level sections, written as markdown headings in the plan file:

### 1. System Overview

A clear summary of the system's purpose, core functionality, and the primary technologies/stack. This gives every downstream agent the big picture.

### 2. Phase 0: Foundation & Scaffolding (always first)

Phase 0 is special — it is implemented directly in the main repo **before** spawning any worktrees. It sets up the shared foundation that unblocks parallel module development:

- **Directory structure**: Proposed filesystem layout
- **Configurations**: Essential setup files (build tools, configs, `.env.example`)
- **Core contracts**: Database schemas, core data models/types, shared interfaces, API contracts, base abstract classes
- **Tooling**: Linters, formatters, CI/CD pipeline stubs

Phase 0 uses `## [ ] Phase 0: Scaffolding` format and can have sub-steps like a regular plan phase since it will be implemented directly.

### 3. Module briefs (Phase 1..N)

Each module is a `## [ ] Phase N of M` containing a **functional brief** — not a step-by-step implementation plan. The downstream agent will use this brief to create its own detailed plan.

Module brief format:

```markdown
## [ ] Phase 1 of 4: User Authentication Module

### Scope
What this module does, its responsibilities, and boundaries.
What is NOT in scope (belongs to another module).

### Interfaces
- **Provides**: APIs, types, functions this module exposes to others
- **Depends on**: What it needs from other modules or existing code

### Data & state
Database tables, caches, or state stores this module owns or interacts with.

### Key design decisions
Important architectural choices the implementing agent should follow.

### Complexities & edge cases
Specific technical challenges, security concerns, or business rules
the downstream agent must handle.

### Verification
- [ ] Module implemented and tests pass
- [ ] Merged back to main
```

### 4. Dependencies & parallelization

After all module briefs, include a section mapping out orchestration:

- **Sequential blockers**: Which modules depend on others and must be built in order
- **Parallel workstreams**: Which modules are decoupled (thanks to Phase 0 contracts) and can be assigned to different agents simultaneously

### 5. Shared engineering standards

Define the standards that all downstream agents must follow. Only include sections relevant to the project — skip what doesn't apply:

- **Modularity**: Separation of concerns, strict boundaries between layers
- **Error handling**: System-wide approach to errors, formatting, logging
- **Observability**: Logging, metrics, tracing standards
- **Security**: Input validation, auth checks, OWASP protections
- **Code style**: Conventions beyond what linters enforce

### 6. Testing strategy

The overarching testing philosophy all module agents must follow:

- **Unit testing**: Expectations for testing core logic in isolation
- **Integration testing**: How to test seams between modules and shared contracts
- **E2E testing**: Critical user journeys that need full system testing after integration

### Global verification

```markdown
## Verification

- [ ] All modules implemented and merged
- [ ] Integration tests pass across module boundaries
- [ ] E2E tests pass for critical user journeys
```

## Example

```markdown
## [ ] Phase 0: Scaffolding

### [ ] 1. Project setup and core contracts

Set up directory structure, build tooling, and define shared types:
- Database schemas for User, Project, Task
- API contract types and error format
- Test fixtures and helpers

### Files
- `src/models/` — ORM model definitions
- `src/api/contracts.py` — shared API types
- `tests/conftest.py` — shared test fixtures

### Verification
- [ ] Project builds cleanly
- [ ] Base test suite passes

## [ ] Phase 1 of 3: Database Schema and Models

### Scope
Migrations, ORM models, and data access layer. Owns all direct
database interaction.

### Interfaces
- **Provides**: SQLAlchemy models (`User`, `Project`, `Task`), repository classes
- **Depends on**: Phase 0 (schema definitions, base classes)

### Data & state
- Tables: `users`, `projects`, `tasks`
- Owns all migrations in `src/db/migrations/`

### Key design decisions
- Use Alembic for migrations
- Repository pattern for data access

### Complexities & edge cases
- Cascading deletes between projects and tasks
- Soft-delete support for users

### Verification
- [ ] Module implemented and tests pass
- [ ] Merged back to main

## [ ] Phase 2 of 3: REST API Layer
...

## [ ] Phase 3 of 3: Authentication and Authorization
...

## Dependencies & parallelization

- **Sequential**: Phase 0 → then all others
- **Parallel**: Phases 1, 2, 3 can run in parallel (all depend only on Phase 0 contracts)
- **Note**: Phase 3 uses User model from Phase 1, but only via the shared interface defined in Phase 0

## Shared engineering standards

### Error handling
- All API errors use `{error: string, code: string, details: object}` format
- Business logic raises domain exceptions; API layer converts to HTTP responses

### Security
- All inputs validated with Pydantic models
- SQL injection prevented by ORM-only database access

## Testing strategy

### Unit testing
- All business logic tested in isolation with mocked repositories
- Target: every public function has at least one test

### Integration testing
- Each module tests against a real test database
- Use shared fixtures from Phase 0

### E2E testing
- After integration: test user registration → create project → add tasks flow

## Verification

- [ ] All modules implemented and merged
- [ ] Integration tests pass across module boundaries
- [ ] E2E tests pass for critical user journeys
```

## Workflow

### 1. Create the draft

Run the plan CLI to create draft files:

```bash
plan.py create <slug> --prompt="<user's original request>" --agent=<your-agent-name>
```

- The slug should be a short, descriptive, kebab-case identifier for the overall system (e.g., `auth-system`, `data-pipeline`, `plugin-framework`).
- `--prompt` captures the user's original request for the log.
- `--agent` identifies you as an AI agent in the log.

### 2. Explore the codebase

Use Glob, Grep, Read, and Explore agents to understand:
- Overall architecture and project structure
- Existing modules and how they're organized
- Shared infrastructure (build system, testing, CI)
- Boundaries where new modules would fit

Think at the **system level**: what are the natural seams? What can be developed independently? What has ordering constraints?

If you're unsure whether an approach will work, write a proof of concept in `/tmp`. Don't modify the project during planning.

### 3. Fill in the appendix

As you discover things, immediately write them to the appendix file:
- Project structure overview
- Existing module boundaries and patterns
- Shared infrastructure details
- Build and test conventions
- Key file paths with line references

The appendix is especially important for master plans — each worktree agent will read it to understand the broader system context.

### 4. Fill in the plan

Write the master plan following the structure above:
1. System overview
2. Phase 0: Scaffolding
3. Module briefs (Phases 1..N)
4. Dependencies & parallelization
5. Shared engineering standards
6. Testing strategy
7. Global verification

### 5. Design for independence

Each module should be implementable by a fresh agent that only reads:
1. The master plan (for context and its module's spec)
2. The appendix (for codebase details)
3. The current code on its worktree branch

Minimize coupling between modules. When coupling is unavoidable, define clear interfaces in Phase 0.

### 6. Present to the user

When the plan is complete, summarize it for the user. Include:
- The module breakdown with dependency ordering
- Which modules can be parallelized
- What Phase 0 scaffolding covers

The user will either:
- Run `/plan-mode:plan+approve` to approve it
- Give feedback for you to incorporate
