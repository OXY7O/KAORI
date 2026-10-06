from scripts.verify_ui_reuse import _metrics


def test_ui_reuse_ignores_inert_json_bootstrap_script() -> None:
    source = '<script id="bootstrap" type="application/json">{"ready": true}</script>'

    assert _metrics('app/templates/example.html', source)['inline_scripts'] == 0


def test_ui_reuse_still_counts_executable_inline_script() -> None:
    source = '<script>window.kaoriReady = true</script>'

    assert _metrics('app/templates/example.html', source)['inline_scripts'] == 1
