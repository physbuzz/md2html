# md2html implementation brief

## Status and objective

This repository contains preparation only: a package skeleton and the intended user documentation. There is no converter, CLI, or installed executable yet. Begin implementation only when the user requests the implementation run. No implementation work is required to complete the preparation task.

Build a fresh, simpler md2html with the main capabilities described in [readme.md](readme.md), correct behavior, and low architectural complexity. Breaking interface and precedence changes are allowed where they simplify the system. Do not treat backward compatibility or a line-count reduction as the objective.

## Non-negotiable working rules

- Read `../AGENTS.md` and `../md2html-old/REVIEW.md` when working in the preparation workspace. The review is evidence, not a blueprint to port. This brief also records the essential requirements so they remain with the repository.
- Design from behavior before inspecting implementation details. Do not copy the old codebase wholesale or file by file, then shrink it. Do not reproduce its structure through renamed equivalents. Do not delegate that migration strategy to other agents. Read reference code selectively for specific questions; write a coherent implementation afresh. Suitable external libraries may be reused.
- Preserve the README's exact language wherever possible, especially its opening three paragraphs. It is the explicit exception to the prohibition on copying implementation. Make small, justified corrections for actual behavior and clarity; do not replace it with generic documentation.
- Production code, comments, docstrings, messages, and the README MUST be timeless and standalone. They MUST NOT mention earlier codebases, documentation versions, review conversations, or AI exchanges. Explain the current design on its own terms. Historical context belongs in development records only.
- Maintain the principal capabilities: Markdown and Liquid, templates and layouts, site/Jekyll output, posts and pagination, directives and included sources, opt-in snippet execution, highlighting, math choices, asset placement, and watch/serve. Simplify their interaction; do not silently remove capabilities to meet a size target.

## Decisions to make before implementation

Write a short design describing the data flow and ownership of a command's settings, inputs, rendered pages, execution results, workers, and assets. Organize by responsibilities rather than by files in the reference project. Avoid speculative frameworks and premature module stubs.

Resolve options once, preferably defaults → configuration → CLI. State which front-matter fields are metadata or template choices and which, if any, affect rendering. Resolve paths against their documented origins. Decide whether redundant force/font switches are needed; intentional changes must be reflected in the README.

Use one build plan for all inputs and one preprocessing path for all Markdown fragments. Preserve each fragment's directory for relative includes and sources. State the ordering of include/directive expansion, document Liquid, Markdown, and template/layout rendering. Keep source code and TeX intact through stages that must not interpret them. HTML/HTM/XML and Jekyll Markdown need explicit, understandable behavior rather than accidental extra passes.

Directives are preprocessing, including inside Markdown fences. Accept trailing `#` annotations on directive lines. Preserve source-block bodies intact, including C/C++ `#include`, comments, and directive-looking code. Only the documented source-block delimiter ends a block. Use simple delimiter checks, not separate competing parsers.

Collect asset requirements across all pages and write shared assets under one owner. Use consistent npm package discovery for all supported MathJax modes. Distinguish build-time Node.js rendering from browser rendering; verify the dependency and asset promises in the README. Consider whether asset mode alone can determine font placement.

Prefer making watch rerun the ordinary build: render on startup, debounce changes, rediscover inputs, and render using cached execution output. Measure before adding incremental machinery. Watch referenced files outside the input tree, exclude generated outputs, and recover from ordinary build errors. A set of watched dependencies need not become a reverse graph selecting individual pages.

## Required behavior and accepted limits

HTML rebuilding and execution caching are separate. Reuse successful output for unchanged snippet text, even after a watch restart. Language and workspace distinctions may be part of identity, but timestamps, line numbers, positions, imported modules/headers, and command-definition fingerprints must not expand invalidation. Changed snippet text reruns; explicit forced execution reruns unchanged snippets when execution is enabled. A force flag does not imply automatic discovery of untracked dependency changes.

Timeouts must terminate and reap the process tree. If cleanup cannot complete, stop the build instead of silently continuing. A frozen executable must select an actual Python interpreter for Python snippets, not invoke itself as Python.

Within one command, shared assets must survive every input and site listings must reflect updated metadata regardless of the math backend. Detect output collisions within that command. Independent commands writing to the same output directory need no coordination or locks.

Settings stay fixed until command restart. Deleted pages may leave generated HTML. Recursive copying of `node_modules` is accepted; explicit exclusions remain available. Do not introduce cleanup manifests, automatic dependency tracking, or mandatory exclusions to change these accepted limits.

## Acceptance checks

Use focused tests of user-visible behavior. Select tooling and dependencies when the implementation needs them; the scaffold intentionally contains no runtime dependencies or test suite.

- Build a single file and a directory, with working templates, styles, copied references, includes, and output collision errors. Exercise representative site/Jekyll features, posts, pagination, and output modes retained in the interface.
- Edit a referenced Racket source during single-file serve and directory serve, including after restarting serve. Both displayed code and program results must update. Watch an included file outside the source tree and verify output changes without an output-triggered rebuild loop.
- Use a snippet with an observable counter to prove unchanged successful code is not rerun on HTML rebuild or watcher restart. Changed code reruns. Explicit force reruns unchanged code only when execution is enabled. Cover both inline and file-backed snippets.
- Apply the same directives in main documents, includes, and Markdown fences. Exercise trailing directive annotations and source blocks containing `#include`, comments, Liquid-like text, and directive-looking code; verify intact displayed and executed source and clear mismatched-delimiter errors.
- Run a real subprocess tree that attempts a delayed side effect. Timeout must leave no surviving descendant or delayed side effect. Verify that inability to complete cleanup stops the build.
- Build multiple inputs in one invocation with mixed math requirements. Every page's shared assets must remain available regardless of input order. Exercise standalone, shared, and CDN behavior for the supported math backends.
- Edit a post title and verify a `site.posts` listing updates, including with raw math. Correctness must not rely on a math backend forcing a rebuild.
- Test npm discovery in every documented location, including a parent of the notes directory. Exercise build-time and browser math assets through the same discovery contract.
- Build and run the actual packaged executable from outside the checkout. Verify Python and Racket execution output and default static math. Do not substitute assertions about makefile text for this check.
- Verify documented settings precedence, relative path origins, errors, and opt-in execution. Update tests for deliberate behavior changes rather than retaining obsolete assertions about internal helpers or incidental URLs.
- Check README commands and examples against the finished interface. Verify packaging claims and dependencies, replace or remove unverified size measurements, and document any supported browser-MathJax standalone limitation accurately. Do not advertise an unimplemented image-embedding flag. Keep the author's wording wherever the facts still fit.
- Measure representative cold and warm builds with cached execution enabled. Record enough context to judge whether full rendering is acceptable; optimize only from evidence.

Do not depend on temporary review reproductions or a particular user's notes checkout. Create small self-contained fixtures. Any optional integration checks that cannot run must be reported explicitly rather than counted as passes.

## Completion

Deliver the implementation, suitable tests, packaging, and minimally revised standalone documentation. Summarize architectural decisions, deliberate interface changes, validation results, and unresolved limitations. Do not claim completion solely because code is shorter or unit tests pass.
