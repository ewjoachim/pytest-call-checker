from __future__ import annotations

import dataclasses
import inspect
from typing import Any, Callable

import pytest


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # set a report attribute for each phase of a call
    if rep.when in ["setup", "call"]:
        setattr(item, "test_status", rep)


class NoMatch(Exception):
    pass


@dataclasses.dataclass
class Match:
    method: str
    match_kwargs: dict
    response_args: dict
    response_kwargs: dict

    def __str__(self):
        method = f".{self.method}" if self.method else ""
        printable_items = [
            (k, "<callable>" if callable(v) else v)
            for k, v in self.match_kwargs.items()
        ]

        return f"{method}({', '.join(f'{k}={v}' for k, v in printable_items)})"


class Checker:
    def __init__(
        self,
        call: Callable | None = None,
        response: Callable | None = None,
        ordered: bool = True,
    ):
        self._matches: list[Match] = []
        self._call = call or getattr(self, "call")
        if not self._call:
            raise NotImplementedError("Missing either a 'call' argument or method")

        self._response: Callable = response or getattr(self, "response")
        if not self._response:
            raise NotImplementedError("Missing either a 'response' argument or method")
        self._response_signature: inspect.Signature = inspect.signature(self._response)

        self.ordered: bool = ordered

    # def call(self, ...):
    # def response(self, ...):

    def __call__(self, *args, **kwargs):
        return self._do_call("", args, kwargs)

    def _do_call(self, method, args, kwargs) -> Any:
        bound = self._signature(method).bind(*args, **kwargs)
        bound.apply_defaults()
        request_kwargs = dict(bound.arguments)
        matches = self._matches

        if self.ordered:
            matches = matches[:1]

        for match in matches:
            try:
                return self._match_and_respond(
                    request_method=method,
                    request_kwargs=request_kwargs,
                    match=match,
                )
            except NoMatch:
                continue

        raise AssertionError(
            f"No response found for arguments {request_kwargs}\n"
            f"Expected argument set(s): {', '.join(str(m) for m in matches) or 'nothing.'}"
        )

    def _match_and_respond(
        self,
        request_method: str,
        request_kwargs: dict,
        match,
    ) -> Any:
        # May raise NoMatch
        self._match(
            request_method=request_method,
            request_kwargs=request_kwargs,
            match=match,
        )

        self.request_kwargs = request_kwargs
        self.match = match

        self._matches.remove(match)
        return self._response(*match.response_args, **match.response_kwargs)

    def __getattr__(self, value):
        return Caller(checker=self, method=value)

    def _signature(self, method: str):
        target = self._call
        if method:
            # Bind the "self" argument
            # Obviously, in 3 months times, I'm never going to understand
            # what happens on this line, so here's a quick recap:
            # https://stackoverflow.com/questions/1015307/python-bind-an-unbound-method
            target = getattr(target, method).__get__(object(), target)

        return inspect.signature(target)

    def _match(self, request_method: str, match: Match, request_kwargs: dict):
        if request_method != match.method:
            raise NoMatch

        for key, match_value in match.match_kwargs.items():
            if key not in request_kwargs:
                raise NoMatch

            request_value = request_kwargs[key]

            if callable(match_value):
                try:
                    assert match_value(request_value)
                except Exception:
                    raise NoMatch
            else:
                if not match_value == request_value:
                    raise NoMatch

        return

    @property
    def register(self):
        return Registerer(checker=self)

    def _register(self, method: str, args: tuple, kwargs: dict):
        bound = self._signature(method).bind(*args, **kwargs)
        match_kwargs = dict(bound.arguments)

        def _(*resp_args, **resp_kwargs):

            self._matches.append(
                Match(
                    method=method,
                    match_kwargs=match_kwargs,
                    response_args=resp_args,
                    response_kwargs=resp_kwargs,
                )
            )

        return _

    def check_no_call_left(self):
        if self._matches:
            raise AssertionError(
                "Some registered calls were not reached:\n"
                + (", ".join(str(m) for m in self._matches) or "nothing.")
            )


class MetaCaller:
    meta_method = ""

    def __init__(self, checker: Checker, method: str = ""):
        self.checker = checker
        self.method = method

    def __call__(self, *args, **kwargs):
        return getattr(self.checker, self.meta_method)(self.method, args, kwargs)

    def __getattr__(self, value):
        if self.method:
            raise AttributeError

        return self.__class__(checker=self.checker, method=value)


class Registerer(MetaCaller):
    meta_method = "_register"


class Caller(MetaCaller):
    meta_method = "_do_call"


@pytest.fixture
def checker(request):
    instances: list[Checker] = []

    def _(checker: Checker):
        instances.append(checker)
        return checker

    _.Checker = Checker
    yield _
    if request.node.test_status.passed:
        for instance in instances:
            instance.check_no_call_left()
