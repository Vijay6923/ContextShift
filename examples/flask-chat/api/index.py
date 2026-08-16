import os
import sys

# Add the parent directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Export the app for Vercel
# Vercel's Python runtime expects a variable named 'app'
# which is why we import it as 'app'. The import itself is the point --
# pyflakes has no way to know that and will call it unused, which is
# why this file is deliberately excluded from this repo's pyflakes
# invocation (see README.md's "Running the Tests" section).
