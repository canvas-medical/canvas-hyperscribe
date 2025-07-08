import json, random, pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from hyperscribe.libraries.constants import Constants
from evaluations.cases.synthetic_unit_cases import transcript_generator as tg
from hyperscribe.structures.vendor_key import VendorKey



@pytest.fixture
def fake_profiles_file(tmp_path: Path) -> Path:
    """
    Create a throw-away JSON file with two minimal patient profiles.
    Tests that only need a *path* to a profiles JSON can re-use this.
    """
    fp = tmp_path / "profiles.json"
    (tmp_path).mkdir(exist_ok=True, parents=True)
    json.dump({"Patient 1": "AAA", "Patient 2": "BBB"}, fp.open("w"))
    return fp

def _fake_llm(payload: str) -> MagicMock:
    """Return dummy LLM whose request().response equals *payload*."""
    llm = MagicMock()
    llm.request.return_value.response = payload
    return llm

@pytest.mark.parametrize(
    "src, expect_ok",
    [
        ('[{"speaker":"A","text":"hi"}]', True),
        ('xxx[{"speaker":"A","text":"hi"}]', True),  
        ('[{"speaker":"A","text":"hi",}]', False),  
        ("{bad json}", False),  
    ],
)
def test_safe_json_load(src: str, expect_ok: bool):
    data, err = tg._safe_json_load(src)
    assert (data is not None) == expect_ok
    if expect_ok:
        assert data[0]["speaker"] and data[0]["text"]
    else:
        assert err

def test_safe_json_load_stripped_fixes_json():
    # This input has a trailing comma before closing a dict
    broken = '[{"speaker": "A", "text": "hi",    }]'
    result, err = tg._safe_json_load(broken)
    assert result is not None
    assert result[0]["speaker"] == "A"
    assert result[0]["text"] == "hi"
    assert err is None



@patch.object(random, "uniform")
@patch.object(random, "randint")
@patch.object(random, "choice")
def test_make_spec_deterministic(
    mock_choice, mock_randint, mock_uniform, fake_profiles_file: Path, tmp_path: Path
):
    gen = tg.TranscriptGenerator("KEY", str(fake_profiles_file), str(tmp_path))
    mock_choice.side_effect = (
        ["short"] 
        + ["Clinician"] 
        + ["Patient"] * 9  
        + [tg.TGConstants.MOOD_POOL[0], tg.TGConstants.MOOD_POOL[1]]
        + [tg.TGConstants.PRESSURE_POOL[0]]
        + [tg.TGConstants.CLINICIAN_PERSONAS[0]]
        + [tg.TGConstants.PATIENT_PERSONAS[0]]
    )
    mock_randint.return_value = 3
    mock_uniform.return_value = 1.25

    spec = gen._make_spec()

    assert spec["bucket"] == "short"
    assert spec["turn_total"] == 3
    assert spec["speaker_sequence"] == ["Clinician", "Patient", "Patient"]
    assert spec["ratio"] == 1.25
    # ensure mood / personas are set correctly by checking for how many moods as well as that the moods correspond to the pool.
    assert len(spec["mood"]) == 2
    assert all(m in tg.TGConstants.MOOD_POOL for m in spec["mood"])

@patch.object(tg.TranscriptGenerator, "_create_llm")
def test_generate_transcript_ok(
    mock_llm, fake_profiles_file: Path, tmp_path: Path
):
    good_json = '[{"speaker":"Clinician","text":"Mid-visit note."}]'
    mock_llm.return_value = _fake_llm(good_json)
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    gen = tg.TranscriptGenerator(vendor_key, str(fake_profiles_file), str(tmp_path))
    transcript, spec, raw = gen.generate_transcript_for_profile("stub profile")

    assert transcript == json.loads(good_json)
    
    assert "mid-visit note." in gen.seen_openings
    assert {"turn_total", "ratio", "bucket"} <= spec.keys()
    assert raw == good_json

def test_seen_openings_not_added_if_no_text_key(fake_profiles_file, tmp_path):
    good = '[{"speaker":"Clinician","content":"Hello"}]'  # no "text"
    with patch.object(tg.TranscriptGenerator, "_create_llm", return_value=_fake_llm(good)):
        g = tg.TranscriptGenerator("KEY", str(fake_profiles_file), str(tmp_path))
        g.generate_transcript_for_profile("profile")
        assert not g.seen_openings  # line 184 skipped

@patch.object(tg.TranscriptGenerator, "_create_llm")
def test_generate_transcript_bad_json_fallback(
    mock_llm, fake_profiles_file: Path, tmp_path: Path
):
    bad_json = "NOT-JSON"
    mock_llm.return_value = _fake_llm(bad_json)
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    gen = tg.TranscriptGenerator(vendor_key, str(fake_profiles_file), str(tmp_path))
    transcript, spec, raw = gen.generate_transcript_for_profile("stub profile")

    assert transcript[0]["speaker"] == "SYSTEM"
    assert "json_error" in spec
    assert raw == bad_json

@patch.object(tg.TranscriptGenerator, "_create_llm")
def test_run_creates_files(mock_llm, tmp_path):
    # fabricate a tiny profiles.json with two patients
    profiles_path = tmp_path / "profiles.json"
    json.dump({"Patient 1": "AAA", "Patient 2": "BBB"}, profiles_path.open("w"))
    mock_llm.return_value = _fake_llm(
        '[{"speaker":"Clinician","text":"content"}]'
    )
    out_root = tmp_path / "out"
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    gen = tg.TranscriptGenerator(vendor_key, str(profiles_path), str(out_root))
    
    # start at 2 so only Patient 2 is processed
    gen.run(start_index=2, limit=1)

    p2_dir = out_root / "Patient_2"
    assert (p2_dir / "transcript.json").exists()
    assert (p2_dir / "spec.json").exists()
    assert (p2_dir / "raw_transcript.txt").exists()

    #double-check that no p1 directory exists.
    assert not (out_root / "Patient_1").exists()

def test_safe_json_load_happy_path_executes_return():
    good = '[{"speaker":"A","text":"ok"}]'
    data, err = tg._safe_json_load(good)
    assert err is None and data[0]["text"] == "ok"          # line 69-70 executed


def test__create_llm_real_instance(fake_profiles_file, tmp_path):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    gen = tg.TranscriptGenerator(vendor_key, str(fake_profiles_file), str(tmp_path))
    llm = gen._create_llm()
    assert llm.api_key == "MY_KEY" 
    assert llm.model == Constants.OPENAI_CHAT_TEXT_O3


def test_build_prompt_includes_seen_openings(fake_profiles_file, tmp_path):
    gen = tg.TranscriptGenerator("K", str(fake_profiles_file), str(tmp_path))
    gen.seen_openings.add("previous first line")
    spec = gen._make_spec()
    sys_turn, user_turn = gen._build_prompt("stub patient", spec)

    joined = "\n".join(sys_turn.text)
    assert "Avoid starting with any of these previous first lines" in joined

def test_seen_openings_branch(fake_profiles_file, tmp_path):
    good = '[{"speaker":"Clinician","text":"Hello there"}]'
    with patch.object(tg.TranscriptGenerator, "_create_llm", return_value=_fake_llm(good)):
        vendor_key = VendorKey(vendor="vendor", api_key="MY_KEY")
        g = tg.TranscriptGenerator(vendor_key, str(fake_profiles_file), str(tmp_path))
        assert not g.seen_openings                # empty before
        g.generate_transcript_for_profile("profile")
        # after one call the first line must be stored (branch executed)
        assert "hello there" in g.seen_openings


def test_run_without_limit(fake_profiles_file, tmp_path):
    """
    Executes the path where `limit is None` (line-193) and the loop body (195-196).
    """
    # make two profiles so the loop surely runs
    profiles_path = fake_profiles_file
    # stub LLM to return minimal valid transcript
    with patch.object(tg.TranscriptGenerator, "_create_llm",
                      return_value=_fake_llm('[{"speaker":"C","text":"x"}]')):
        out_root = tmp_path / "out_no_limit"
        vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
        tg.TranscriptGenerator(vendor_key, str(profiles_path), str(out_root)).run()
        assert (out_root / "Patient_1").exists()
        assert (out_root / "Patient_2").exists()
