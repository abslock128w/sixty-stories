"""Contact sheet of preview/film images: $PY sheet.py OUT.png W cols file1 file2 ..."""
import sys, os
from PIL import Image
out, W, cols = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
fs = sys.argv[4:]
H = round(W * 804 / 1920)
rows = (len(fs) + cols - 1) // cols
S = Image.new('RGB', (cols * (W + 4), rows * (H + 4)), (16, 16, 16))
for k, f in enumerate(fs):
    S.paste(Image.open(f).convert('RGB').resize((W, H), Image.LANCZOS), ((k % cols) * (W + 4), (k // cols) * (H + 4)))
S.save(out)
