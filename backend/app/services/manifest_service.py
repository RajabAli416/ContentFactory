"""Load/save validated production manifests."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.paths import ensure_project_layout, project_dir
from app.schemas.manifest import ProductionManifest, create_initial_manifest


class ManifestService:
    def path_for(self, project_id: str) -> Path:
        return project_dir(project_id) / "manifest.json"

    def project_json_path(self, project_id: str) -> Path:
        return project_dir(project_id) / "project.json"

    def create(
        self,
        project_id: str,
        title: str,
        topic: str,
        **kwargs,
    ) -> ProductionManifest:
        ensure_project_layout(project_id)
        manifest = create_initial_manifest(project_id, title, topic, **kwargs)
        self.save(manifest)
        project_meta = {
            "project_id": project_id,
            "title": title,
            "topic": topic,
            "status": manifest.status,
        }
        self.project_json_path(project_id).write_text(
            json.dumps(project_meta, indent=2), encoding="utf-8"
        )
        return manifest

    def load(self, project_id: str) -> ProductionManifest:
        path = self.path_for(project_id)
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found for project {project_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProductionManifest.model_validate(data)

    def save(self, manifest: ProductionManifest) -> Path:
        manifest.touch()
        ensure_project_layout(manifest.project_id)
        path = self.path_for(manifest.project_id)
        path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return path

    def update(self, project_id: str, patch: dict) -> ProductionManifest:
        manifest = self.load(project_id)
        data = manifest.model_dump(mode="json")
        data = _deep_merge(data, patch)
        updated = ProductionManifest.model_validate(data)
        self.save(updated)
        return updated


def _deep_merge(base: dict, patch: dict) -> dict:
    result = dict(base)
    for key, value in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
