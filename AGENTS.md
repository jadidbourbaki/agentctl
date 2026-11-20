# AGENTS.md

Agent Energy runs local commands under a suspendable process supervisor and
includes a Pydantic AI example. Conduct inference through an existing endpoint.

The guidance below comes from Orla, Braid, Shared Cache World Model, and
Éire Society. Apply the excerpts to this Python project.

## Quality gate

Run `just check` before committing. Keep tests focused on observable process
behavior and use real child processes for lifecycle regressions.

## Reuse before implementation

Before writing nontrivial logic, inspect the standard library, existing
dependencies, mature packages, and managed services. Prefer an existing
solution when the solution meets the requirement with less total burden.
Explain a consequential choice briefly in the relevant change or README.

Good dependencies are welcome. Evaluate focused scope, maintenance,
documentation, adoption, and compatibility. Adding a dependency to avoid
substantial custom code can simplify the system. Adding a dependency for a
trivial operation can complicate the system. Choose on total cost.

## Writing prose

The following style rules apply to all prose in the repo: README,
docs, design notes, commit message bodies, code comments.

### Hard rules

- **No em-dashes.** The character `—` does not appear in prose. If
  you would normally use an em-dash, split into two sentences or use
  a comma. The same goes for en-dashes (`–`) in prose.
- **No semicolons in prose.** Use a period and start a new sentence.
- **No unnecessary parentheses.** Parenthetical asides that pause the
  reader for a thought you could have put in its own sentence should
  go in its own sentence. A one-word gloss such as an abbreviation on
  first use is fine. Anything longer is a sentence you have not
  written yet, and parens are never a substitute for a comma or a
  period.
- **Don't pack settings into parentheses.** A run of
  `NAME (default X), OTHER (default Y)` is unreadable, and a second
  clause tacked on after a semicolon makes it worse. Put environment
  variables, flags, and their defaults in a table with a column for
  the name, the default, and the meaning.
- **No ASCII diagrams.** Describe relationships in prose. ASCII boxes
  and arrows are hard to maintain and rarely earn their space.
- **No emoji** unless the user explicitly asks for them.
- **Don't define a thing by what it is not.** "X, not Y" and its
  variants, "X rather than Y", "X and never Y", tell the reader what
  to erase instead of what to hold. Say what the thing does and stop.
  "The audit is a visibility aid, not an access gate" becomes "The
  audit records every write and lets all of them through." State a
  limit outright when it is load-bearing, as its own sentence, in
  terms of what happens: "Orla still serves the request."
- **No vague back-references.** Do not open a sentence with "This",
  "That", "These", "Those", "Their", or "It" pointing at a noun from
  an earlier sentence. Name the noun again. "This is the wrong
  baseline" becomes "The best region in hindsight is the wrong
  baseline." The reader should never have to look backward to resolve
  what a pronoun stands for.

### Soft rules

- Write short, direct sentences. If a sentence has more than one
  comma, consider whether it should be two sentences.
- Lead with the noun, not the qualifier. "The proxy looks up the
  stage" beats "When a request arrives, the proxy looks up the
  stage."
- Define jargon on first use, even if you think the reader knows it.
- Do not write in fragments or in a punchy, aphoristic style. Short
  clipped clauses strung together read like a parable, not like
  documentation. "No key, no cost, runs on a laptop" is wrong.
  "Ollama runs models locally, so it needs no API key and costs
  nothing to call" is right.
- Don't write multi-paragraph code docstrings. One short paragraph
  per exported identifier is the ceiling.

### Examples

Wrong:

> The proxy auto-creates a default stage record (empty backend, empty
> everything) on first sighting; the request then falls back to
> `req.Model` for that one call.

Right:

> The proxy auto-creates a default stage record on first sighting.
> The request falls back to `req.Model` for that one call.

Wrong:

> Cost comes from the generic Rates map, with the tool reporting
> matching usage at dispatch time. ToolKind is required, ModelID is
> unused.

Right:

> Cost comes from the generic Rates map, with the tool reporting
> matching usage at dispatch time. ToolKind is required. ModelID is
> unused.

## Writing comments

The rules under "Writing prose" apply, plus:

- **Default to writing no comment.** A well-named identifier and a
  short function explain themselves. Only comment when the why is
  non-obvious: a hidden constraint, a subtle invariant, a workaround
  for a specific upstream bug, behavior that would surprise a reader.
- **Don't describe what the code does.** The code does that.
- **Say what is done and why, not what was avoided.** Frame a comment
  around the present behavior and its reason, not a rejected
  alternative. "The input stays visible so there is always a place to
  type" beats "we do not hide the input". Name the road taken, not the
  ones not taken.
- **Don't reference the past.** "Renamed from X", "formerly Y" all
  rot. Comments describe the present state.
- **Don't reference callers or PRs.** They rot as the code evolves.
- **Don't write multi-line comment banners.** One short comment per
  declaration.

## Python style

Type every function, fail loudly, prefer the standard library, and let the tooling enforce the rules.

### Tooling

The toolchain is Astral's, and it is not optional.

- **uv** for environments and dependencies. Not pip, not poetry, not a
  bare `requirements.txt`. Use `uv add`, `uv lock`, `uv run`.
- **ruff** for both linting and formatting. It replaces black, isort,
  and flake8.
- **ty** for type checking. It is Astral's checker and still young,
  but it is the house checker. Not mypy or pyright.
- **just** for task running, with the same recipe names across
  subprojects: `run`, `fmt`, `lint`, `typecheck`, and a `check` that
  runs the read-only trio the way CI would.

### Project layout and dependencies

Each Python subproject is a self-contained uv project with its own
`pyproject.toml` and `uv.lock`.

- Runtime dependencies go in `[project].dependencies`. Dev tools like
  ruff and ty go in `[dependency-groups].dev` per PEP 735, so `uv run`
  installs them by default.
- Pin every direct dependency to an exact version with `==` and commit
  `uv.lock`. The lockfile resolves the full tree with hashes, so installs
  are both reproducible and verified against supply-chain tampering. A
  demo or PoC is something you run, not a library someone imports, so
  pinning beats flexibility.
- The lockfile is committed and never hand-edited. `.gitignore` covers
  `.venv/`, `__pycache__/`, `.ruff_cache/`, and `.ty_cache/`.

### Types

Type every function signature, both parameters and return. `ty check`
runs in the gate, so an untyped surface is a failing build.

- Put `from __future__ import annotations` at the top of every module.
- Use built-in generics, `list[int]` and `dict[str, T]`, not
  `typing.List`. Use `X | None`, not `Optional[X]`.
- Reach for a `TypeVar` when a return type depends on a type handed
  in. A function that returns the base type forces every caller to
  narrow it back.
- Model structured data that crosses a boundary with a Pydantic model
  or a dataclass. Do not pass bare dicts whose shape lives only in
  your head. A signature like `list[dict[str, Any]]` is the warning
  sign: the rows have a shape, so give the shape a model and the
  signature the model's name.

### Imports

Every import goes at the top of the module. A function-level import
hides a dependency from both the reader and the tooling, and it defers
an ImportError from startup to call time. Import inside a function only
to break a genuine circular import or to keep an optional dependency
optional, and name the reason in a comment.

### Naming and errors

- `snake_case` for functions and variables, `PascalCase` for classes,
  `UPPER_SNAKE` for module constants. A leading underscore marks a
  name module-private. Do not uppercase acronyms the way Go does, PEP
  8 wins: `HTTPClient` as a class, but `url` and `id` lowercase.
- Raise exceptions, do not return sentinel values to signal failure.
- Catch narrowly. A broad `except Exception` belongs only at a
  top-level boundary where you log and carry on. A bare `except:` is
  never correct. Use `raise ... from err` to preserve the cause.

### Don't reinvent the wheel

Prefer something already built, the standard library or a
well-maintained dependency, over code you write yourself. A vetted
package or a stdlib helper is almost always more correct and better
tested than a version written under deadline. A good external
dependency is welcome. What is not welcome is hand-rolling logic that
a mature library already solves. Reach for your own implementation
only when nothing fits, or when the dependency would weigh far more
than the problem it solves.

## Code readability

- One assignment per line. No tuple packing such as `a, b = 1, 2`.
- Descriptive names: `tiles_per_frame`, `history_steps`, `gap_steps`.
  A single letter is acceptable only as a comprehension index.
- Name intermediate results. Do not chain calls.
- Type every function signature, parameters and return.
- Delete code that no current result depends on. When an approach is
  abandoned or reverted, remove its functions, settings, tests, and
  comments in the same change.
- Fail hard. No `try/except: pass`. No silent fallbacks. A malformed
  recording or an unknown setting raises with a message that names the
  offending value.
