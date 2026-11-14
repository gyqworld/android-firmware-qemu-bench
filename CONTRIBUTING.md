# Contributing

Do not commit firmware, extracted vendor files, APKs, maps, user data, screenshots
or private logs. Use synthetic fixtures in tests.

1. Explain the provenance of new code and third-party files.
2. Review new paths before adding them to `scripts/public-files.json`.
3. Run unit tests, `scripts/audit_public.py` and source packaging.
4. Keep process execution, boot completion, received pixels and visible app state
   separate in reports. Nominal display Hz is not measured FPS.
5. Preserve private local inputs; reuse dependencies before downloading them.

CI requires no firmware and uploads no runtime artifacts. Private runtime results
must be summarized manually rather than publishing original logs.
