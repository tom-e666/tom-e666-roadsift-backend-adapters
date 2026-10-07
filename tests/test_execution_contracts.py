import pytest
from pydantic import ValidationError

from roadsift_adapters.ports.executor import JobSpec


def test_job_spec_rejects_secret_fields():
    with pytest.raises(ValidationError):
        JobSpec(job_id="j1", job_type="mining", command=["python", "run.py"], config={"api_key": "nope"})


def test_job_spec_rejects_escaping_output():
    with pytest.raises(ValidationError):
        JobSpec(job_id="j1", job_type="mining", command=["python", "run.py"], outputs={"x": "../x.json"})
