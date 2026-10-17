Rewrite `md2html-old` from scratch as the smallest, clearest piece of static website glue code that implements the philosophy of a basic Jekyll-like liquid + markdown generator, with the special `@src` directives which make execution of code snippets easy (for easy editing and publication of articles containing many code snippets). Essentially all features in `md2html/readme.md` should be implemented; breaking changes are OK, we don't require backwards compatibility, but should be documented in readme.md (Subject to the [AGENTS.md](../AGENTS.md) guidelines about the readme).

**Aggressively simplify the architecture.** Rewrite md2html from scratch as the smallest, clearest piece of glue around its libraries that you can make.

**Fix the bugs in [REVIEW.md](../md2html-old/REVIEW.md).** Let the simpler architecture eliminate their causes wherever possible. Respect the review's intentional behaviors and use its checks to verify the result. This is a secondary goal in that it could and should be solved in the simplification rewrite. Basically some of these are bugs that hint at issues with the architecture. Things in [REVIEW.md](../md2html-old/REVIEW.md) are old statements about the old codebase, and statements in this document and in agents.md take precedence.

Build from behavior, not by copying files and shrinking them. There are reuse exceptions in `AGENTS.md`, namely that the style templates, and assets, as well as the presentation details of the four math backends, were carefully designed with a lot of back and forth and browser testing, so this stuff is OK to mimic and leave unchanged.

Deliver working code and tests, minimally updated documentation, and a before/after `cloc` comparison.

## Other notes:

**Pay attention to the current order in which md2html builds the document.** While it is flawed, it also solves a lot of bugs. On top of that it's tied up in the way the user should think about the project, with `@` being spiritually like preprocessing directives (so it's not the worst thing in the world if it pays less attention to markdown and liquid syntax). Also note that bugs like the string `{{` being common in Mathematica code have been solved. So in architecture decisions that look strange, ask yourself what bugs the architecture solves first, and when you rewrite make sure that you're really solving all of those problems.

Another example is the directory chosen to build `@src` programs into. If a file outputs a .png result or something, the output location and the directories exposed by custom build options were intentional choices about how the user works with generated files. Understand those choices before changing them; deliberate changes should remain usable and be documented.

**Make sure the variety of configuration options, such as custom commands and the variety of methods to output math code, are well-tested and remain functional.**

A request I forgot to make, this is like an afterthought BTW but it's something to add to configuration: - [ ] Add --host ADDRESS to configure the preview server’s bind address, defaulting to 127.0.0.1. Support --serve --host 0.0.0.0 --port 8000 for Docker previews. Preserve existing behavior: --serve implies watching; --watch alone starts no server. Update CLI help, documentation, and tests.
