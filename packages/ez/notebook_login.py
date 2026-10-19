"""Google sign-in window for NotebookLM, run with the NotebookLM environment's Python.

`notebooklm login` decides that a person is signed in when the page lands on the NotebookLM host.
Since 2026-10 an anonymous visit lands there too (notebook.google.com/trynow, a public page), so
the window closed at once and saved a session without Google's cookies. This script opens the
Google sign-in in the same browser profile and waits until Google's session cookie exists (it
checks the cookie's name, never its value); `notebooklm login` then finds a real session and
saves it.

Standalone on purpose: it imports only the standard library, Playwright and notebooklm, which
live in NotebookLM's environment, not in EZ's.
"""
import json
import sys
import time

SIGN_IN = 'https://accounts.google.com/ServiceLogin?continue='


def main(seconds):
    from playwright.sync_api import sync_playwright
    from notebooklm.paths import get_browser_profile_dir
    from notebooklm._env import get_base_url
    base = get_base_url()
    profile = get_browser_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        # The same options notebooklm uses, so Google treats both windows alike.
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile), headless=False,
            args=['--disable-blink-features=AutomationControlled', '--password-store=basic'],
            ignore_default_args=['--enable-automation'])
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(SIGN_IN + base + '/', wait_until='commit', timeout=60000)
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if not context.pages:
                    return 'browser_closed'
                if any(cookie['name'] == 'SID' for cookie in context.cookies('https://accounts.google.com')):
                    # Visit NotebookLM once signed in so its own cookies exist before notebooklm saves them.
                    page = context.pages[0]
                    page.goto(base + '/', wait_until='commit', timeout=60000)
                    page.wait_for_timeout(5000)
                    return 'signed_in'
                page.wait_for_timeout(2000)
            return 'timeout'
        finally:
            try:
                context.close()
            except Exception:
                pass


def outcome_of(exc):
    """A failure the agent can act on: «failed: Error» hid a missing Chromium on a clean install (2026-10-19)."""
    text = str(exc).casefold()
    if "executable doesn't exist" in text or 'playwright install' in text or isinstance(exc, ImportError):
        return 'browser_missing'
    if 'closed' in text:
        return 'browser_closed'
    return 'failed: ' + type(exc).__name__


if __name__ == '__main__':
    try:
        outcome = main(int(sys.argv[1]) if len(sys.argv) > 1 else 600)
    except Exception as exc:  # the window was closed mid-navigation, Playwright or its browser missing, …
        outcome = outcome_of(exc)
    print(json.dumps({'outcome': outcome}))
    sys.exit(0 if outcome == 'signed_in' else 1)
