from app.schemas.manifest import ProductionManifest, create_initial_manifest


def test_create_initial_manifest_valid():
    m = create_initial_manifest("proj_test", "Title", "Topic about oceans")
    assert m.schema_version == "1.0.0"
    assert m.pipeline_stages[0].stage == "PROJECT_CREATED"
    assert m.pipeline_stages[0].status == "completed"
    # Round-trip
    data = m.model_dump(mode="json")
    m2 = ProductionManifest.model_validate(data)
    assert m2.project_id == "proj_test"


def test_manifest_rejects_bad_scene_status():
    m = create_initial_manifest("proj_x", "T", "topic")
    data = m.model_dump(mode="json")
    data["scenes"] = [
        {
            "scene_id": "scene_001",
            "sequence": 1,
            "generation_status": "not_a_real_status",
        }
    ]
    try:
        ProductionManifest.model_validate(data)
        assert False, "should have raised"
    except Exception:
        pass
