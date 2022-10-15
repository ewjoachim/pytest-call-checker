from __future__ import annotations


def test_fail__missing_calls(pytester):
    pytester.makepyfile(
        """
        import dataclasses
        import pytest

        @dataclasses.dataclass
        class SystemResult:
            baz: int
            qux: str = "nothing"


        def system(foo: int, bar: int = 3):
            assert False, "This point should never be reached"


        @pytest.fixture
        def fake_system(checker):
            class FakeSystem(checker.Checker):
                def call(self, foo: int, bar: int = 4):
                    ...

                def response(self, baz: int, qux="something"):
                    return SystemResult(baz=baz, qux=qux)

            return checker(FakeSystem())

        def test_fail__missing_call(fake_system):
            fake_system.register(foo=1, bar=2)(baz=8)
            fake_system.register(foo=3, bar=4)(baz=9)

            fake_system(foo=1, bar=2)

    """
    )

    # run all tests with pytest
    result = pytester.runpytest()

    result.assert_outcomes(errors=1, passed=1)

    result.stdout.re_match_lines(
        [
            r"E +AssertionError: Some registered calls were not reached:",
            r"E +\(foo=3, bar=4\)",
        ],
        consecutive=True,
    )
