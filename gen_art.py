"""
CROWN CLASH art generator (OpenAI gpt-image-1).

Usage:
  python gen_art.py                 generate every card that has no art/<id>.png yet, then pack art.js
  python gen_art.py --one warden    generate a single card (good for a test run)
  python gen_art.py --force         regenerate everything
  python gen_art.py --pack          only rebuild art.js from the PNGs already in art/

Key: OPENAI_API_KEY environment variable, or a line OPENAI_API_KEY=sk-... in a .env file next to this script.
Cost: roughly $0.04 per image at "medium" quality (20 cards + 5 towers + map, about $1.50 total).
"""
import os, sys, json, base64, io, urllib.request, urllib.error, time

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "art")
os.makedirs(OUT, exist_ok=True)

KEY = os.environ.get("OPENAI_API_KEY", "")
envp = os.path.join(ROOT, ".env")
if not KEY and os.path.exists(envp):
    for ln in open(envp, encoding="utf-8"):
        if ln.startswith("OPENAI_API_KEY="):
            KEY = ln.split("=", 1)[1].strip().strip('"').strip("'")

STYLE = ("Stylized 3D cartoon game character in the look of a mobile card-battle arena game: chunky proportions, big head, "
         "glossy toy-like shading, bright saturated colors, thick dark outlines are NOT used, soft studio lighting. "
         "Full body, standing, facing slightly to the right, centered, feet at the bottom. "
         "Isolated on a fully transparent background. No text, no logo, no ground shadow, no frame.")

CARDS = {
 "bone":   "A tiny cheerful skeleton warrior holding a small bone club, bare skull with glowing eye sockets.",
 "grunt":  "A small green goblin with big pointy ears, a wide toothy grin and a rusty dagger, purple vest.",
 "spear":  "A green goblin with pointy ears holding a wooden spear over its shoulder, blue tunic.",
 "warden": "A stout armored knight with a bucket helm, silver plate armor with blue accents, sword and round shield.",
 "sling":  "A hooded elf archer in a green cloak drawing a wooden bow, quiver on the back.",
 "bat":    "A small mischievous purple bat creature with leathery wings, fangs and big yellow eyes, hovering.",
 "bomb":   "A skeleton in a brown hood holding a round black bomb with a lit fuse, mischievous grin.",
 "turret": "A stone-and-wood cannon turret, iron barrel pointing up-right, sitting on a square wooden platform.",
 "valk":   "A fierce warrior woman with a flowing orange ponytail, red leather armor and a huge double-bladed axe held sideways.",
 "musk":   "A sharpshooter woman in a blue coat and wide-brim hat aiming a long brass musket, confident smirk.",
 "wyrm":   "A cute baby dragon, teal scales, small horns, orange belly, wings spread, mouth puffing a tiny flame, flying.",
 "boar":   "A wild mohawk warrior riding a big brown boar at full charge, holding a wooden hammer above his head.",
 "coil":   "A tesla coil defense tower: iron base, copper coil, crackling blue lightning orb at the top.",
 "titan":  "A gigantic gentle giant with a bushy beard, sleeveless yellow vest and huge fists, towering and heavy.",
 "pyro":   "A wizard with a white beard, purple robe and tall pointed hat, holding a staff with a swirling fireball.",
 "sky":    "A hot-air balloon with a red-striped envelope, a wooden basket, and a skeleton pilot dropping a big black bomb.",
 "colo":   "A towering dark armored mech-knight with glowing pink eyes and a massive two-handed greatsword, menacing.",
 "jolt":   "A spell icon: a bright cyan lightning bolt crackling with electricity, sparks flying, glowing.",
 "volley": "A spell icon: a tight bundle of three wooden arrows with red fletching flying downward, motion streaks.",
 "meteor": "A spell icon: a blazing orange fireball meteor with a fiery tail and molten core, glowing hot.",
}
# towers (rendered like the troops, viewed from a high three-quarter angle, front facing)
TOWERS = {
 "_twr_b_p": "A squat stone princess tower with royal blue roof tiles, a blue banner, battlements, and a small cannon slot at the top.",
 "_twr_b_k": "A tall grand stone king tower, wider than a princess tower, royal blue roof, blue banners, a golden crown ornament on top, battlements.",
 "_twr_r_p": "A squat stone princess tower with crimson red roof tiles, a red banner, battlements, and a small cannon slot at the top.",
 "_twr_r_k": "A tall grand stone king tower, wider than a princess tower, crimson red roof, red banners, a golden crown ornament on top, battlements.",
 "_rubble":  "A pile of broken grey stone blocks and splintered wood, the ruins of a collapsed tower, small wisps of smoke.",
}
MAP_PROMPT = ("Straight top-down orthographic view (camera pointing directly downward, no perspective tilt, no horizon) of a 3D "
 "rendered fantasy battle arena for a mobile card-battle game. A lush bright green grass field with subtle mowed checker "
 "stripes fills the entire image edge to edge. A clear blue river runs horizontally across the exact vertical middle of the "
 "image, spanning the full width, about 6% of the image height thick, with small rocks and light ripples. Two wooden plank "
 "bridges cross the river: one centered at 24% of the image width from the left edge, the other centered at 24% from the "
 "right edge, each about 13% of the image width wide, with little wooden posts. Only a thin decorative stone trim along the "
 "outer border. A few small flowers, pebbles and grass tufts scattered sparsely. No characters, no buildings, no towers, "
 "no tents, no text, no UI, no color tinting between the two halves. Clean, bright, glossy stylized cartoon 3D render.")

def gen(cid, prompt, size="1024x1024", transparent=True, raw=False):
    body = json.dumps({"model": "gpt-image-1", "prompt": (prompt if raw else STYLE + " " + prompt), "size": size,
                       "background": "transparent" if transparent else "opaque", "quality": "medium",
                       "output_format": "png", "n": 1}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body,
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                j = json.load(r)
            png = base64.b64decode(j["data"][0]["b64_json"])
            open(os.path.join(OUT, cid + ".png"), "wb").write(png)
            return True
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            print("  HTTP", e.code, msg[:300])
            if e.code in (401, 403, 400):
                return False
            time.sleep(4)
        except Exception as e:
            print("  error:", e); time.sleep(4)
    return False

def warp_map(im):
    """Piecewise-linear remap: river band -> tiles 15..17, bridge centres -> x 3.5 / 14.5, output 720x1280 (40 px/tile)."""
    from PIL import Image
    W, H = im.size; px = im.load()
    def isblue(c): r, g, b = c; return b > 150 and b > r + 60 and b > g + 20
    def iswood(c): r, g, b = c; return 110 < r < 200 and 60 < g < 140 and b < 90 and r > g + 25
    xs = range(int(W * .2), int(W * .8), 4)
    rows = [y for y in range(H) if sum(isblue(px[x, y]) for x in xs) / len(xs) > .35]
    if rows and rows[-1] - rows[0] < H * .2:
        ra, rb = rows[0], rows[-1]
    else:
        ra, rb = round(H * 15 / 32), round(H * 17 / 32)
    yc = (ra + rb) // 2
    cols = [x for x in range(W) if sum(iswood(px[x, y]) for y in range(yc - 8, yc + 8)) >= 8]
    cl = []
    for c in cols:
        if cl and c - cl[-1][1] <= 20: cl[-1][1] = c
        else: cl.append([c, c])
    cl = [c for c in cl if c[1] - c[0] > W * .05]
    tw = H * 18 / 32; x0 = (W - tw) / 2; x1 = x0 + tw
    if len(cl) >= 2:
        bl, br = (cl[0][0] + cl[0][1]) / 2, (cl[-1][0] + cl[-1][1]) / 2
    else:
        bl, br = x0 + tw * 3.5 / 18, x0 + tw * 14.5 / 18
    print("  map river rows %d-%d, bridges x %.0f / %.0f" % (ra, rb, bl, br))
    D = 40; xs_src = [x0, bl, br, x1]; xs_dst = [0, 3.5 * D, 14.5 * D, 18 * D]
    ys_src = [0, ra, rb, H]; ys_dst = [0, 15 * D, 17 * D, 32 * D]
    mesh = []
    for i in range(3):
        for j in range(3):
            box = (int(xs_dst[i]), int(ys_dst[j]), int(xs_dst[i + 1]), int(ys_dst[j + 1]))
            quad = (xs_src[i], ys_src[j], xs_src[i], ys_src[j + 1], xs_src[i + 1], ys_src[j + 1], xs_src[i + 1], ys_src[j])
            mesh.append((box, quad))
    return im.transform((18 * D, 32 * D), Image.MESH, mesh, Image.BICUBIC)

def pack():
    """Downscale to 320px and write art.js as data URLs so the game (and the Desktop copy) needs only one sidecar file."""
    try:
        from PIL import Image
    except ImportError:
        Image = None
    art = {}
    mp = os.path.join(OUT, "_map.png")
    if os.path.exists(mp):
        data = open(mp, "rb").read()
        if Image:  # 1024x1536 render; warp it so the river and bridges land exactly on the arena grid
            im = warp_map(Image.open(mp).convert("RGB"))
            buf = io.BytesIO(); im.save(buf, "JPEG", quality=88); data = buf.getvalue()
            art["_map"] = "data:image/jpeg;base64," + base64.b64encode(data).decode()
        else:
            art["_map"] = "data:image/png;base64," + base64.b64encode(data).decode()
    for cid in list(CARDS) + list(TOWERS):
        p = os.path.join(OUT, cid + ".png")
        if not os.path.exists(p):
            continue
        data = open(p, "rb").read()
        if Image:
            im = Image.open(p).convert("RGBA")
            # crop to the opaque bounding box so sprites sit tight, then scale to 320 tall
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
            h = 320; w = max(1, round(im.width * h / im.height))
            im = im.resize((w, h), Image.LANCZOS)
            buf = io.BytesIO(); im.save(buf, "PNG", optimize=True); data = buf.getvalue()
        art[cid] = "data:image/png;base64," + base64.b64encode(data).decode()
    js = "window.CC_ART=" + json.dumps(art) + ";\n"
    open(os.path.join(ROOT, "art.js"), "w", encoding="utf-8").write(js)
    print("packed", len(art), "sprites into art.js (%d KB)" % (len(js) // 1024))

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--pack" in args:
        pack(); sys.exit()
    if not KEY:
        sys.exit("No OPENAI_API_KEY found. Set the environment variable or put OPENAI_API_KEY=sk-... in crownclash/.env")
    force = "--force" in args
    todo = [args[args.index("--one") + 1]] if "--one" in args else list(CARDS) + list(TOWERS) + ["_map"]
    for cid in todo:
        p = os.path.join(OUT, cid + ".png")
        if os.path.exists(p) and not force:
            print("skip", cid); continue
        print("generating", cid, "...")
        if cid == "_map":
            ok = gen(cid, MAP_PROMPT, size="1024x1536", transparent=False, raw=True)
        else:
            ok = gen(cid, CARDS.get(cid) or TOWERS[cid])
        print("  ", "ok" if ok else "FAILED")
    pack()
