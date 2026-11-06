import os
import tempfile

# Tests dürfen nie die echte Datenbank oder echte Sicherungen berühren
os.environ.setdefault("PFALZWERK_LOKAL", tempfile.mkdtemp(prefix="pfalzwerk_test_"))
