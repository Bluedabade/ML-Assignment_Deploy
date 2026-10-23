"""Community Cloud entrypoint; dependency file is adjacent, UI is shared with local."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skn_app.ui import main

if __name__ == '__main__':
    main()
