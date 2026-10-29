# Play WAV files (auditions, takes, the mix) on this computer's speakers, so the owner can judge them by ear.
# usage: python3 lib/play.py audio/audition/A_am_michael.wav [more.wav ...]     (each plays to the end in turn)
# macOS plays with afplay; Windows with Python's built-in winsound. Opening the file in Finder or File Explorer
# works too.
import os, subprocess, sys
if len(sys.argv) < 2:
    sys.exit('usage: python3 lib/play.py FILE.wav [FILE.wav ...]')
for f in sys.argv[1:]:
    if not os.path.isfile(f):
        sys.exit('No such file: ' + f)
    print('playing', f, flush=True)
    if os.name == 'nt':
        import winsound
        winsound.PlaySound(f, winsound.SND_FILENAME)
    else:
        subprocess.run(['afplay', f], check=True)
