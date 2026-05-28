# runtime

- Responsibility: L0 runtime profiles: resources, workers, queues, stores, artifacts and transport.
- Boundary: keep only this layer's concern; avoid cross-layer logic here.
- Context contract (if any):
  - `context_requires` / `context_provides` / `context_mutates` / `context_cache`
- Minimal example: keep one runnable file, or document the entry path.
