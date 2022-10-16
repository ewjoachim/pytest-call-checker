# pytest-call-checker

[![Deployed to PyPI](https://img.shields.io/pypi/pyversions/pytest-call-checker?logo=pypi&logoColor=white)](https://pypi.org/pypi/pytest-call-checker)
[![GitHub Repository](https://img.shields.io/github/stars/ewjoachim/pytest-call-checker?logo=github)](https://github.com/ewjoachim/pytest-call-checker/)
[![Continuous Integration](https://img.shields.io/github/workflow/status/ewjoachim/pytest-call-checker/CI?logo=github)](https://github.com/ewjoachim/pytest-call-checker/actions?workflow=CI)
[![Coverage](https://raw.githubusercontent.com/ewjoachim/pytest-call-checker/python-coverage-comment-action-data/badge.svg)](https://github.com/ewjoachim/pytest-call-checker/tree/python-coverage-comment-action-data)
[![MIT License](https://img.shields.io/github/license/ewjoachim/pytest-call-checker?logo=open-source-initiative&logoColor=white)](https://github.com/ewjoachim/pytest-call-checker/blob/main/LICENSE)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-v1.4%20adopted-ff69b4.svg)](https://github.com/ewjoachim/pytest-call-checker/blob/main/LICENSE/CODE_OF_CONDUCT.md)


`pytest-call-checker` is a pytest plugin providing a `checker` fixture
that allows creating test doubles with interesting properties.

## Stating the problem

Imagine you're writing a library that makes HTTP calls to an API. If you follow
usual practices of separating I/O from logic, chances are you will use some
form of dependency injection: the functions you will write will receive a HTTP
client object and will route HTTP calls to this object. The idea being that in
real context, they will receive a real HTTP client, and in test code, they will
receive a fake client that will not actually perform HTTP calls.

This fake client is a test double. What you'll usually want to check is that:

- The function made exactly as many calls as expected;
- The arguments of each call are correct.

Additionally, you want to be able to control the output of each call given the
input and/or the order of the call.

The usual way to do this is with mocks or specialized libs such as
[requests-mock](https://requests-mock.readthedocs.io/en/latest/),
[responses](https://github.com/getsentry/responses), etc.

This library provides another way, that can also work in other contexts: for
example, maybe you call subprocesses and you would like to not call them
in your unit tests.

## The idea

This library provides a low-level fixture named `checker` that you can use
as a foundation for your own specialized fixtures.

When defining your `checker` fixture, you will tell it what the calls you're
expecting look like, and how to create appropriate responses.

In your tests, you'll register one or more expected calls using
`checker.register`, each with the corresponding response.

When you call the function under test, you'll pass it the `checker` instance.
Each time the instance is called, we'll check that the call arguments match one
of the expected calls you registered, and answer with the corresponding response.

At the end of the test, if all the expected calls were not received, we will
ensure the test fails.

You'll find concrete examples below.

## Code

### Installation

```console
$ pip install pytest-call-checker
```

### Simple usage: Http client

In this example, we create a test double for `httpx.Client`.
In the test, we register a call to the `get` method of the
client.
We then run our function. We can be sure that:
- Our function called the get method
- With the right arguments
- And nothing else on the client
- And when it called the method, it received a fake response that looked like
  what we wanted.

```python
import httpx
import pytest

def get_example_text(client: httpx.Client):
    return client.get("https://example.com").text

@pytest.fixture
def http_client(checker):
    class FakeHttpClient(checker.Checker):

    return checker(checker.Checker(
        call=httpx.Client.request,
        response=httpx.Response
    ))

def test_get_example_text(http_client):
    http_client.register.get("https://example.com")(text="foo")

    assert get_example_text(client=http_client) == "foo"

```

### More advanced usage: Subprocess


In this example, we create a test double not for an object but for a callable
(`subprocess.run`). This usage is slightly more advanced because in order to
instantiate our response object, `subprocess.CompletedProcess` object, we need
to know the command `args` that were passed to the `subprocess.run` call. This
could be slightly annoying if we needed to repeat the `args` both in the call
and the `response` so we'll introduce a technique here that will let us keep
our tests as simple as possible.


```python

def get_date(run: Callable):
    return run(["date"]).stdout


@pytest.fixture
def subprocess_run(checker):
    class SubprocessRun(checker.Checker):
        call = subprocess.run

        def response(self, returncode, stdout=None, stderr=None):
            # When the response is implemented as a method of a `checker.Checker`
            # subclass, you can access `self.match`. This lets you construct
            # the output object using elements from the input kwargs, see
            # the `args` argument below.
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

```

As you can see, in the code above, there are two ways to create you
`checker.Checker` instance:

- You can create an instance directly
- Or subclass `checker.Checker`. In this case, instead of passing `call` and
  `response` in the constructor, you can also define them as methods.

In case you go the subclass route, this lets you access additional elements
through `self` if you need it. This is an advanced usage, we'll do our best to
avoid breaking this, but it touches the inner workings of our objects so if you
really do complicated things, it might break.

The most useful attributes of `checker.Checker` that you can access in
`def reponse(self, ...)` should be:

- `self.match`: The `Match` object that was associated with the response we're
  building.
- `self.request_kwargs`: The keyword arguments with which the test double
  was called

### Other interesting features

#### Matching with functions

Sometimes, you can't perform an exact match on the input parameters, but you
still want to check some properties in order to perform the match.

In this case, use a callable instead of the value for the argument you want
to check.

```python

import uuid

def create_object(client: ApiClient) -> ApiResponse:
    # Create object with a random ID
    return client.create(id=uuid.uuid4())


@pytest.fixture
def api_client(checker):
    class FakeAPIClient(checker.Checker):

    return checker(checker.Checker(
        call=ApiClient,
        response=ApiResponse
    ))


def test_get_date(api_client):
    def is_uuid(value):
        return isinstance(value, uuid.UUID)

    api_client.register(id=is_uuid)()

    assert create_object(client=api_client) == ApiResponse()

```


#### Allowing calls in different order

By default, it's expected that the calls will be done in the same order as
they were registered. You can actually change that by passing `ordered=False`
when creating the fixture.

```python

import uuid

def fetch_objects(client: ApiClient, ids: set[int]) -> set[ApiResponse]:
    # Because it's in a set, we can't be sure of the call order
    return {
        client.get(id=id)
        for id in ids
    }


@pytest.fixture
def api_client(checker):
    class FakeAPIClient(checker.Checker):

    return checker(checker.Checker(
        call=ApiClient,
        response=ApiResponse,
        ordered=False,
    ))


def test_get_date(api_client):

    api_client.register(id=1)(id=1)
    api_client.register(id=2)(id=2)

    responses = fetch_objects(client=api_client, ids={1, 2})
    assert responses == {ApiResponse(id=1), ApiResponse(id=2)}

```

## Caveats

Some things are not ideal, and could be improved:

- There is no way to mark one call as optional. It's assumed that if the
  tests are reproducible, then we should always know whether they'll do
  calls or not.
- It's probably not possible yet to create test doubles for modules. The usual
  way of doing dependency injection is through functions or class instances.
