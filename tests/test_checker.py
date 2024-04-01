from __future__ import annotations

import dataclasses
import re

import pytest

# Tests around a checker subclass


@dataclasses.dataclass
class SystemResult:
    baz: int
    qux: str = "nothing"


def system(foo: int, bar: int = 3):
    assert False, "This point should never be reached"


@pytest.fixture
def fake_system(checker):
    class FakeSystem(checker.Checker):
        def call(self, foo: int, bar: int = 4): ...

        def response(self, baz: int, qux="something"):
            return SystemResult(baz=baz, qux=qux)

    return checker(FakeSystem())


def test_pass__args(fake_system):
    fake_system.register(1, 7)(9, "yay")

    assert fake_system(1, 7) == SystemResult(9, "yay")


def test_pass__kwargs(fake_system):
    fake_system.register(foo=1, bar=7)(baz=9, qux="yay")

    assert fake_system(foo=1, bar=7) == SystemResult(baz=9, qux="yay")


def test_fail__no_register(fake_system):
    with pytest.raises(
        AssertionError,
        match=re.escape(
            "No response found for arguments {'foo': 1, 'bar': 2}\n"
            "Expected argument set(s): nothing."
        ),
    ):
        fake_system(foo=1, bar=2)


def test_fail__wrong_register(fake_system):
    fake_system.register(foo=1, bar=2)(baz=8)

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "No response found for arguments {'foo': 1, 'bar': 3}\n"
            "Expected argument set(s): (foo=1, bar=2)"
        ),
    ):
        fake_system(foo=1, bar=3)

    fake_system(foo=1, bar=2)


def test_pass__multiple(fake_system):
    fake_system.register(foo=1, bar=7)(baz=9, qux="yay")
    fake_system.register(foo=2, bar=16)(baz=20, qux="yo")

    assert fake_system(foo=1, bar=7) == SystemResult(baz=9, qux="yay")
    assert fake_system(foo=2, bar=16) == SystemResult(baz=20, qux="yo")


def test_pass__incomplete(fake_system):
    fake_system.register(foo=1)(baz=9)

    assert fake_system(foo=1) == SystemResult(baz=9, qux="something")


def test_pass__callable(fake_system):
    fake_system.register(foo=1, bar=lambda x: bool(x % 2))(baz=9, qux="something")

    assert fake_system(foo=1, bar=7) == SystemResult(baz=9, qux="something")


def test_fail__callable(fake_system):
    fake_system.register(foo=1, bar=lambda x: bool(x % 2))(baz=9)

    with pytest.raises(AssertionError):
        fake_system(foo=1, bar=6)

    fake_system(foo=1, bar=7)


def test_fail__multiple_wrong_order(fake_system):
    fake_system.register(foo=2, bar=16)(baz=20, qux="yo")
    fake_system.register(foo=1, bar=7)(baz=9, qux="yay")

    with pytest.raises(AssertionError):
        assert fake_system(foo=1, bar=7)

    assert fake_system(foo=2, bar=16) == SystemResult(baz=20, qux="yo")
    assert fake_system(foo=1, bar=7) == SystemResult(baz=9, qux="yay")


@pytest.mark.xfail(strict=True, raises=ZeroDivisionError)
def test_fail__dont_call_finalizer(fake_system):
    fake_system.register(foo=1, bar=lambda x: bool(x % 2))(baz=9)

    # the test should fail (thus xfail) but the finalizer should not fail
    0 / 0


# Tests around a checker without subclassing


@dataclasses.dataclass
class SystemResult2:
    baz: int
    qux: str = "nothing"


def system2(foo: int, bar: int = 3):
    assert False, "This point should never be reached"


@pytest.fixture
def fake_system2(checker):
    return checker(
        checker.Checker(
            call=system2,
            response=SystemResult2,
        )
    )


def test_no_subclass__pass__args(fake_system2):
    fake_system2.register(1, 7)(9, "yay")

    assert fake_system2(1, 7) == SystemResult2(9, "yay")


def test_no_subclass__pass__kwargs(fake_system2):
    fake_system2.register(foo=1, bar=7)(baz=9, qux="yay")

    assert fake_system2(foo=1, bar=7) == SystemResult2(baz=9, qux="yay")


def test_no_subclass__fail(fake_system2):
    with pytest.raises(
        AssertionError,
        match=re.escape(
            "No response found for arguments {'foo': 1, 'bar': 2}\n"
            "Expected argument set(s): nothing."
        ),
    ):
        fake_system2(foo=1, bar=2)


# Tests around multiple calls & order


@dataclasses.dataclass
class SystemResult3:
    baz: int
    qux: str = "nothing"


def system3(foo: int, bar: int = 3):
    assert False, "This point should never be reached"


@pytest.fixture
def fake_system3(checker):
    return checker(
        checker.Checker(
            call=system3,
            response=SystemResult3,
            ordered=False,
        )
    )


def test_unordered__pass__multiple(fake_system3):
    fake_system3.register(foo=1, bar=7)(baz=9, qux="yay")
    fake_system3.register(foo=2, bar=16)(baz=20, qux="yo")

    assert fake_system3(foo=1, bar=7) == SystemResult3(baz=9, qux="yay")
    assert fake_system3(foo=2, bar=16) == SystemResult3(baz=20, qux="yo")


def test_unordered__pass__multiple_wrong_order(fake_system3):
    fake_system3.register(foo=2, bar=16)(baz=20, qux="yo")
    fake_system3.register(foo=1, bar=7)(baz=9, qux="yay")

    assert fake_system3(foo=1, bar=7) == SystemResult3(baz=9, qux="yay")
    assert fake_system3(foo=2, bar=16) == SystemResult3(baz=20, qux="yo")


# Tests around using methods


@dataclasses.dataclass
class SystemResult4:
    baz: int
    qux: str = "nothing"


class System4:
    def get(self, foo: int, bar: int = 3):
        assert False, "This point should never be reached"

    def post(self, foo: int, bar: int = 3):
        assert False, "This point should never be reached"


@pytest.fixture
def fake_system4(checker):
    return checker(
        checker.Checker(
            call=System4,
            response=SystemResult4,
        )
    )


def test_methods__pass__kwargs(fake_system4):
    fake_system4.register.get(foo=1, bar=7)(baz=9, qux="yay")

    assert fake_system4.get(foo=1, bar=7) == SystemResult4(baz=9, qux="yay")


def test_methods__fail__no_register(fake_system4):
    with pytest.raises(
        AssertionError,
        match=re.escape(
            "No response found for arguments {'foo': 1, 'bar': 2}\n"
            "Expected argument set(s): nothing."
        ),
    ):
        fake_system4.get(foo=1, bar=2)


def test_methods__fail__wrong_method(fake_system4):
    fake_system4.register.get(foo=1, bar=7)(baz=9, qux="yay")

    with pytest.raises(
        AssertionError,
        match=re.escape(
            "No response found for arguments {'foo': 1, 'bar': 2}\n"
            "Expected argument set(s): .get(foo=1, bar=7)"
        ),
    ):
        fake_system4.post(foo=1, bar=2)

    fake_system4.get(foo=1, bar=7)


def test_methods__fail__register_unknown_method(fake_system4):
    with pytest.raises(
        AttributeError,
        match=re.escape("'System4' has no attribute 'put'"),
    ):
        fake_system4.register.put(foo=1, bar=7)


def test_methods__fail__call_unknown_method(fake_system4):
    fake_system4.register.get(foo=1, bar=7)(baz=2, qux="yay")
    with pytest.raises(
        AttributeError,
        match=re.escape("'System4' has no attribute 'put'"),
    ):
        fake_system4.put(foo=1, bar=2)

    fake_system4.get(foo=1, bar=7)
