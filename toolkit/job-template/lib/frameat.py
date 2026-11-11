# usage: python3 lib/frameat.py TAKE SECONDS  -> path of the recorded frame at/before that recording time
import json, sys, bisect
from common import rec_t0
def frame_at(rec, t):
    L = json.load(open('capture/rec/%s/log.json' % rec)); t0 = rec_t0(L); ts = [f['t'] - t0 for f in L['frames']]
    i = max(0, bisect.bisect_right(ts, t) - 1); return 'capture/rec/%s/%s' % (rec, L['frames'][i]['f'])
if __name__ == '__main__': print(frame_at(sys.argv[1], float(sys.argv[2])))
