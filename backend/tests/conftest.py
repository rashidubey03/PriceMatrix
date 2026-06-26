import sys
import os

# Ensure the project root directory (the parent of 'backend') is in sys.path
# so that 'backend' can be imported as a package during tests.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
