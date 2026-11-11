"""Title screen (TITLE.XAP/title.tm2): erase the Japanese logo (inpainting the sky) and draw 「우리들의 가족」 (D4).
Built from the original image at build time; no derived art is stored in the repository."""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BOX = (25, 88, 632, 183)          # x0, y0, x1, y1 of the logo band (subtitle starts below y=183)
FONT = ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 1)
TEXT = '우리들의 가족'


def erase(img):
    a = np.array(img.convert('RGB')).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    x0, y0, x1, y1 = BOX
    box = np.zeros(a.shape[:2], bool)
    box[y0:y1, x0:x1] = True
    mask = np.zeros(a.shape[:2], np.uint8)
    mask[box & (((r > 215) & (g > 215) & (b > 215)) | ((b - r > 28) & (r < 175)))] = 255
    mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
    mask[y1:, :] = 0
    bgr = cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2BGR)
    out = cv2.inpaint(bgr, mask, 9, cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)), mask


def make(img):
    clean, _ = erase(img)
    f = ImageFont.truetype(FONT[0], 74, index=FONT[1])
    layer = Image.new('RGBA', clean.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    bb = d.textbbox((0, 0), TEXT, font=f, stroke_width=6)
    x = (clean.width - (bb[2] - bb[0])) // 2 - bb[0]
    y = BOX[1] + 4 - bb[1] + (BOX[3] - BOX[1] - 8 - (bb[3] - bb[1])) // 2
    glow = Image.new('RGBA', clean.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((x, y), TEXT, font=f, fill=(90, 120, 185, 255), stroke_width=7,
                              stroke_fill=(90, 120, 185, 255))
    d.text((x, y), TEXT, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(150, 175, 220, 255))
    out = clean.convert('RGBA')
    out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2)))
    out.alpha_composite(layer)
    out.putalpha(img.convert('RGBA').getchannel('A'))
    return out
