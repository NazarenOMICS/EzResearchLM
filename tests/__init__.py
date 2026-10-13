import os

# Tests drive ez in-process: long commands run in the foreground unless a test asks for the detached worker.
os.environ.setdefault('EZRESEARCH_FOREGROUND', '1')
# A sign-in that never finishes in a test must not hold it for the seconds a real one gets to close by itself.
os.environ.setdefault('EZRESEARCH_LOGIN_WAIT_SECONDS', '0')
# Tests never renew a real NotebookLM session (it would run the notebooklm on PATH and may open a window).
os.environ.setdefault('EZRESEARCH_NO_SESSION_RENEWAL', '1')
