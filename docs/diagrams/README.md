# Diagrams

Diagrams are stored as Mermaid source (`.mmd`), not as pre-rendered
images, so they diff cleanly in pull requests and stay easy to update as
the architecture evolves. Any Markdown renderer with Mermaid support
(GitHub, GitLab, most static-site generators) renders them directly from
source — copy the file's contents into a ```mermaid fence to preview
elsewhere.

## Index

- [`layer-diagram.mmd`](layer-diagram.mmd) — the Application → Adapters →
  ContextShift Library → Core Types dependency direction described in
  [`../architecture.md`](../architecture.md), plus the current internal
  dependency shape of the `contextshift/` subpackages.
