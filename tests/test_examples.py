from __future__ import annotations

import subprocess

import httpx
import pytest


def get_example_text(client: httpx.Client):
    return client.get("https://example.com").text


@pytest.fixture
def http_client(checker):
    return checker(
        checker.Checker(
            call=httpx.Client,
            response=httpx.Response,
        )
    )


def test_get_example_text(http_client):
    http_client.register.get("https://example.com")(status_code=200, text="foo")

    assert get_example_text(client=http_client) == "foo"


# subprocess


def get_date(run: callable):
    return run(["date"]).stdout


@pytest.fixture
def subprocess_run(checker):
    class SubprocessRun(checker.Checker):
        call = subprocess.run

        def response(self, returncode, stdout=None, stderr=None):
            return subprocess.CompletedProcess(
                args=self.match.match_kwargs["popenargs"],
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )

    return checker(SubprocessRun())


def test_get_date(subprocess_run):
    subprocess_run.register(["date"])(returncode=0, stdout="2022-01-01")

    assert get_date(run=subprocess_run) == "2022-01-01"
