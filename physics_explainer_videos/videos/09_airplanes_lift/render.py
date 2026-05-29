from pathlib import Path
import runpy

root = Path(__file__).resolve().parents[2]
script = root / 'tools' / 'render_remaining_videos.py'
runpy.run_path(str(script), run_name='__main__')
