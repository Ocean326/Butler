if __name__.startswith("butler_main."):
    from butler_main.runtime_os.process_runtime.session import ArtifactRecord, ArtifactRegistry, ArtifactVisibility
else:  # pragma: no cover - compatibility for top-level package imports
    from runtime_os.process_runtime.session import ArtifactRecord, ArtifactRegistry, ArtifactVisibility

__all__ = ["ArtifactRecord", "ArtifactRegistry", "ArtifactVisibility"]
