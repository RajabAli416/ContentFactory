from app.engines.captions.language import normalize_whisper_language, resolve_whisper_language


def test_normalize_codes():
    assert normalize_whisper_language("English") == "en"
    assert normalize_whisper_language("urdu") == "ur"
    assert normalize_whisper_language("auto") is None
    assert normalize_whisper_language("en-US") == "en"


def test_resolve_english_standard():
    assert (
        resolve_whisper_language(
            content_mode="standard",
            project_language="English",
            configured="auto",
        )
        == "en"
    )


def test_resolve_desi_urdu():
    assert (
        resolve_whisper_language(
            content_mode="desi",
            project_language="Urdu",
            configured="auto",
        )
        == "ur"
    )


def test_resolve_respects_force_en():
    assert (
        resolve_whisper_language(
            content_mode="desi",
            project_language="Urdu",
            configured="auto",
            override="en",
        )
        == "en"
    )


def test_resolve_arabic_script_spoken():
    assert (
        resolve_whisper_language(
            content_mode="standard",
            project_language="English",
            spoken_text="یہ ایک ٹیسٹ ہے",
            configured="auto",
        )
        == "ur"
    )
