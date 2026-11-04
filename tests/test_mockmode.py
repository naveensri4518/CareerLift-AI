"""Local MOCK model mode: full FairScore workflow without Bedrock/AWS. No network, no model.

Every test forces CAREERLIFT_MODEL_MODE=mock. A guard also asserts boto3 is never used to create a
client/session during mock scoring (zero AWS calls)."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def mock_mode(monkeypatch):
    monkeypatch.setenv('CAREERLIFT_MODEL_MODE', 'mock')


# ---- config / initialization ----

def test_mode_defaults_to_bedrock(monkeypatch):
    monkeypatch.delenv('CAREERLIFT_MODEL_MODE', raising=False)
    from agent import config
    assert config.model_mode() == 'bedrock'
    assert config.is_mock() is False


def test_mock_mode_selected(mock_mode):
    from agent import config
    assert config.model_mode() == 'mock'
    assert config.is_mock() is True


def test_invalid_mode_raises(monkeypatch):
    monkeypatch.setenv('CAREERLIFT_MODEL_MODE', 'banana')
    from agent import config
    with pytest.raises(config.ModelUnavailableError):
        config.model_mode()


# ---- deterministic extractors ----

def test_mock_technical_claim_extraction_supported(mock_mode):
    from agent import mockmodel
    answer = 'A hash table lookup is O(1) on average but O(n) in the worst case under collisions.'
    claims = mockmodel.extract_claims(answer, ['C-HASH-AVG'])
    c = claims.claims[0]
    assert c.concept_id == 'C-HASH-AVG'
    assert c.status in ('supported', 'partial')
    assert c.evidence_span and c.evidence_span.lower() in answer.lower()  # grounded, real quote


def test_mock_technical_claim_absent(mock_mode):
    from agent import mockmodel
    answer = 'I spoke about something completely unrelated to the topic.'
    claims = mockmodel.extract_claims(answer, ['C-HASH-AVG'])
    assert claims.claims[0].status == 'absent'


def test_mock_detects_grounded_incorrect_assertion(mock_mode):
    from agent import mockmodel
    answer = 'A hash map lookup is always O(1), it is never O(n).'
    claims = mockmodel.extract_claims(answer, ['C-HASH-AVG'])
    assert claims.claims[0].status == 'incorrect'
    assert claims.claims[0].evidence_span  # grounded quote of the wrong statement


def test_mock_communication_observations(mock_mode):
    from agent import mockmodel
    obs = mockmodel.observe('A hash map is fast on average, but slow with many collisions, so we size it well.')
    assert obs.clarity == 'present'
    assert obs.relevance == 'present'
    assert isinstance(obs.evidence, list) and obs.evidence  # grounded sentences


def test_mock_communication_empty_answer(mock_mode):
    from agent import mockmodel
    obs = mockmodel.observe('')
    assert obs.clarity == 'absent'


# ---- end-to-end run() through the REAL FairScore logic ----

def test_mock_run_supported_answer_scores(mock_mode):
    from agent import app
    out = app.run({'text': 'A hash table lookup is O(1) on average but O(n) in the worst case.',
                   'expected_concepts': ['C-HASH-AVG']})
    plan, meta = out['plan'], out['meta']
    assert meta['model_mode'] == 'mock' and meta.get('mock') is True
    assert plan['technical_band'] in ('Partial', 'Solid', 'Strong')  # a real band from fairscore
    assert plan['abstained_technical'] is False
    assert mockmodel_label() in plan['message']


def test_mock_run_abstains_on_thin_answer(mock_mode):
    from agent import app
    out = app.run({'text': 'idk', 'expected_concepts': ['C-HASH-AVG', 'C-BINSEARCH']})
    plan = out['plan']
    # too little coverage -> deterministic verifier abstains (fail-closed), not a guessed band
    assert plan['abstained_technical'] is True
    assert plan['technical_band'] is None


def test_mock_run_detects_misconception(mock_mode):
    from agent import app
    out = app.run({'text': 'A hash map lookup is always O(1), it is never O(n).',
                   'expected_concepts': ['C-HASH-AVG']})
    plan = out['plan']
    assert 'M-HASH-ALWAYS-O1' in plan['misconception_tags']


def test_mock_run_pii_rejected_without_model(mock_mode):
    from agent import app
    out = app.run({'text': 'call me on 9876543210', 'expected_concepts': ['C-HASH-AVG']})
    assert out['meta']['path'] == 'rejected_input'
    assert out['plan']['abstained_technical'] is True


# ---- zero AWS calls guarantee ----

def test_mock_makes_zero_aws_calls(mock_mode, monkeypatch):
    import boto3
    calls = {'session': 0, 'client': 0}

    real_session = boto3.Session

    def spy_session(*a, **k):
        calls['session'] += 1
        return real_session(*a, **k)

    def spy_client(*a, **k):
        calls['client'] += 1
        raise AssertionError('mock mode must not create a boto3 client')

    monkeypatch.setattr(boto3, 'Session', spy_session)
    monkeypatch.setattr(boto3, 'client', spy_client)

    from agent import app
    app.run({'text': 'A hash table lookup is O(1) on average.', 'expected_concepts': ['C-HASH-AVG']})
    assert calls['client'] == 0
    assert calls['session'] == 0  # mock path never even constructs a boto3 Session


# ---- bedrock mode stays separate and fails clearly without creds ----

def test_bedrock_mode_without_credentials_raises_clear_error(monkeypatch):
    monkeypatch.setenv('CAREERLIFT_MODEL_MODE', 'bedrock')
    import boto3
    from agent import app, config

    class NoCredSession:
        def get_credentials(self):
            return None

    monkeypatch.setattr(boto3, 'Session', lambda *a, **k: NoCredSession())
    with pytest.raises(config.ModelUnavailableError) as ei:
        app._model()
    assert 'mock' in str(ei.value).lower()  # the error points the user to mock mode


def mockmodel_label():
    from agent import mockmodel
    return mockmodel.MOCK_LABEL


# ---- language fairness: plain English must be ASSESSED, never dropped to 'Not assessed' ----
# Regression for the production bug where a correct answer in plain English returned technical
# "Not assessed" while communication still scored, because the mock only matched textbook vocabulary.

# A genuinely correct hashing explanation that uses NONE of the curated aliases (hash map, O(1), ...).
PLAIN_CORRECT_HASH = (
    "When I store things by a key, looking one up is basically instant most of the time, but if lots "
    "of them land in the same spot it slows down and has to walk through all of them."
)


def test_plain_english_correct_answer_is_recognised_not_absent(mock_mode):
    """A correct plain-English answer must be at least 'partial' (addressed), never 'absent'."""
    from agent import mockmodel
    claims = mockmodel.extract_claims(PLAIN_CORRECT_HASH, ['C-HASH-AVG'])
    c = claims.claims[0]
    assert c.status == 'partial'  # cue match -> addressed, capped at partial (not inflated to supported)
    assert c.evidence_span and c.evidence_span.lower() in PLAIN_CORRECT_HASH.lower()  # grounded real quote


def test_plain_english_correct_answer_is_assessed_not_abstained(mock_mode):
    """End-to-end: the technical axis must produce a band, not 'Not assessed', for plain English."""
    from agent import app
    out = app.run({'text': PLAIN_CORRECT_HASH, 'expected_concepts': ['C-HASH-AVG']})
    plan = out['plan']
    assert plan['abstained_technical'] is False       # the core fairness fix
    assert plan['technical_band'] in ('Partial', 'Solid', 'Strong')


def test_cue_match_is_capped_at_partial_never_supported(mock_mode):
    """Honesty: a cue-only match shows the concept was ADDRESSED, not that it is correct.
    It must never read as 'supported' on its own."""
    from agent import mockmodel
    claims = mockmodel.extract_claims(PLAIN_CORRECT_HASH, ['C-HASH-AVG'])
    assert claims.claims[0].status != 'supported'


def test_cues_never_override_a_grounded_wrong_assertion(mock_mode):
    """A plain-English answer that is WRONG must still be 'incorrect', not softened to 'partial' by a cue."""
    from agent import mockmodel
    answer = "Hash maps are always constant time, so you never have to worry about it being slow."
    claims = mockmodel.extract_claims(answer, ['C-HASH-AVG'])
    assert claims.claims[0].status == 'incorrect'


def test_empty_answer_still_abstains_after_cue_fix(mock_mode):
    """The fix must NOT fabricate recognition for empty answers: honest abstain is preserved."""
    from agent import app
    out = app.run({'text': '', 'expected_concepts': ['C-HASH-AVG']})
    assert out['plan']['abstained_technical'] is True
    assert out['plan']['technical_band'] is None


def test_plain_english_not_penalised_below_wrong_jargon(mock_mode):
    """Fairness invariant: a correct plain-English answer must read at least as high as a WRONG answer
    that happens to use the textbook vocabulary."""
    from agent import app
    ord_ = {None: -1, 'Weak': 0, 'Partial': 1, 'Solid': 2, 'Strong': 3}
    plain_ok = app.run({'text': PLAIN_CORRECT_HASH, 'expected_concepts': ['C-HASH-AVG']})['plan']
    wrong_jargon = app.run({'text': 'A hash map is always O(1), it is never O(n).',
                            'expected_concepts': ['C-HASH-AVG']})['plan']
    assert ord_[plain_ok['technical_band']] >= ord_[wrong_jargon['technical_band']]


def test_every_concept_has_curated_cues():
    """Guard: the language-fairness fix depends on each concept carrying curated plain-language cues."""
    from agent import fairscore
    for c in fairscore.concepts()['concepts']:
        cues = c.get('cues', [])
        assert isinstance(cues, list) and len(cues) >= 3, f"{c['id']} needs >=3 curated cues"
