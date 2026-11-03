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
