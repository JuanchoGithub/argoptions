"""Smoke: TUI importable sin display (run_test es opcional en CI)."""


def test_tui_import():
    from arg_options.tui_app import ArgOptionsApp, run_interactive

    assert ArgOptionsApp is not None
    assert callable(run_interactive)
