#!/usr/bin/env python3
"""ExcelBaas contentmotor.

Gebruik:  python3 tools/make.py plans/<week>.json
Leest een weekplan, maakt alle beelden (PNG) en reels (MP4) in de
ExcelBaas-huisstijl onder media/<week>/ en schrijft media/<week>/manifest.json
met de openbare links per item. Daarna: git add/commit/push, en inplannen
in Metricool met de links uit het manifest.

Slidetypes feed (1080x1350): cover, bullets, steps, table, statement, compare, cta
Storytypes (1080x1920):      story_question, story_tip, story_post
Reelframes (1080x1920):      reel_title, reel_formula, reel_tip, reel_cta
Tekstopmaak: [[woorden]] wordt groen weergegeven.
"""
import html, json, os, re, subprocess, sys, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
RAW = "https://raw.githubusercontent.com/ai2025dbd-code/excelbaas-media/main/"
GREEN, MID, LIGHT, INK, GREY = "#1B5E35", "#2E8B57", "#D5EBDD", "#111827", "#F3F5F4"

FONTS = [("Oswald", 700, "oswald-latin-700-normal.woff2"),
         ("Inter", 500, "inter-latin-500-normal.woff2"),
         ("Inter", 600, "inter-latin-600-normal.woff2"),
         ("Inter", 800, "inter-latin-800-normal.woff2"),
         ("Caveat", 600, "caveat-latin-600-normal.woff2")]
LOGO = "file://" + os.path.join(TOOLS, "assets", "excelbaas-logo.jpg")

ICONS = {
    "calculator": '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M8 6h8"/><path d="M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15h.01M8 19h.01M12 19h.01M16 19h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
    "users": '<circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-6 7-6s7 2 7 6"/><path d="M16 4a4 4 0 0 1 0 8"/><path d="M22 21c0-3-2-5-4-6"/>',
    "chart": '<path d="M3 20h18"/><path d="M6 20V11"/><path d="M12 20V5"/><path d="M18 20v-6"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "x": '<path d="M18 6L6 18"/><path d="M6 6l12 12"/>',
    "alert": '<path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
    "euro": '<path d="M18 7a7 7 0 1 0 0 10"/><path d="M4 10h10M4 14h10"/>',
    "send": '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>',
}


def esc(t):
    return html.escape(str(t), quote=True)


def rich(t):
    """[[groen]] -> groene span, \n -> <br>."""
    s = esc(t)
    s = re.sub(r"\[\[(.+?)\]\]", rf'<span style="color:{GREEN}">\1</span>', s, flags=re.S)
    return s.replace("\n", "<br>")


def icon(name, size=48, color="#FFFFFF"):
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(name, ICONS["check"])}</svg>')


def page(body, w, h, bg="#FFFFFF"):
    css = "".join(f"@font-face{{font-family:'{n}';font-weight:{wt};src:url('file://{os.path.join(TOOLS, 'fonts', f)}') format('woff2');}}"
                  for n, wt, f in FONTS)
    return (f"<!doctype html><html lang='nl'><head><meta charset='utf-8'><style>{css}"
            f"html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:{bg}}}"
            f"img{{mix-blend-mode:multiply}}*{{box-sizing:border-box}}</style></head><body>{body}</body></html>")


H1 = "font-family:Oswald,Impact,sans-serif;font-weight:700;text-transform:uppercase;margin:0;line-height:1.02"


def frame(inner, n, total, bg="#FFFFFF", w=1080, h=1350, swipe=True, dark=False):
    fg = "#FFFFFF" if dark else INK
    mute = LIGHT if dark else "#4B5563"
    mark = (f'<div style="font-size:34px;font-weight:800"><span style="color:{"#FFFFFF" if dark else GREEN}">Excel</span>'
            f'<span style="color:{fg}">Baas</span></div>')
    count = (f'<div style="font-size:24px;font-weight:600;color:{mute};border:2px solid {"rgba(255,255,255,.5)" if dark else "#D1D5DB"};'
             f'border-radius:999px;padding:8px 22px">{n}/{total}</div>') if total > 1 else "<div></div>"
    right = f'<span style="color:{"#FFFFFF" if dark else GREEN}">Swipe →</span>' if swipe else '<span>Slimmer werken. Minder rekenen.</span>'
    return (f'<div style="width:{w}px;height:{h}px;padding:72px;background:{bg};font-family:Inter,sans-serif;color:{fg};'
            f'display:flex;flex-direction:column;justify-content:space-between;gap:36px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">{mark}{count}</div>'
            f'{inner}'
            f'<div style="display:flex;justify-content:space-between;align-items:center;font-size:28px;font-weight:600;color:{mute}">'
            f'<span>@excelbaas</span>{right}</div></div>')


# ---------------------------------------------------------------- feed slides
def s_cover(d):
    logo = f'<img src="{LOGO}" style="width:520px;align-self:center">' if d.get("logo") else ""
    return (f'<div style="display:flex;flex-direction:column;gap:28px;justify-content:center;flex:1">{logo}'
            f'<h1 style="{H1};font-size:{d.get("size", 130)}px">{rich(d["headline"])}</h1>'
            + (f'<p style="margin:0;font-size:38px;font-weight:500;color:#374151">{rich(d["sub"])}</p>' if d.get("sub") else "")
            + '</div>')


def s_statement(d):
    return (f'<div style="display:flex;flex-direction:column;gap:30px;justify-content:center;flex:1">'
            f'<h1 style="{H1};font-size:{d.get("size", 104)}px">{rich(d["headline"])}</h1>'
            + (f'<p style="margin:0;font-size:36px;font-weight:500;color:#374151;line-height:1.35">{rich(d["sub"])}</p>' if d.get("sub") else "")
            + '</div>')


def s_bullets(d):
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:30px;padding:24px 28px;background:{GREY};border-radius:24px">'
        f'<div style="flex:none;width:92px;height:92px;border-radius:50%;background:{GREEN};display:flex;align-items:center;justify-content:center">{icon(it.get("icon", "check"))}</div>'
        f'<div style="display:flex;flex-direction:column;gap:4px"><div style="font-size:38px;font-weight:800">{rich(it["title"])}</div>'
        + (f'<div style="font-size:27px;color:#374151">{rich(it["text"])}</div>' if it.get("text") else "")
        + '</div></div>' for it in d["items"])
    return (f'<h1 style="{H1};font-size:{d.get("size", 96)}px">{rich(d["headline"])}</h1>'
            f'<div style="display:flex;flex-direction:column;gap:20px">{rows}</div>')


def s_steps(d):
    parts = []
    for i, it in enumerate(d["items"], 1):
        parts.append(
            f'<div style="display:flex;gap:36px;align-items:flex-start;padding:30px 0;border-top:{"2px solid #D1D5DB" if i > 1 else "0"}">'
            f'<div style="flex:none;width:140px;{H1};font-size:110px;line-height:.9;color:{GREEN}">{i:02d}</div>'
            f'<div style="display:flex;flex-direction:column;gap:10px;padding-top:6px"><div style="font-size:44px;font-weight:800">{rich(it["title"])}</div>'
            + (f'<div style="font-size:29px;color:#374151">{rich(it["text"])}</div>' if it.get("text") else "")
            + '</div></div>')
    return (f'<h1 style="{H1};font-size:{d.get("size", 104)}px">{rich(d["headline"])}</h1>'
            f'<div style="display:flex;flex-direction:column">{"".join(parts)}</div>')


def s_table(d):
    cols = d["columns"]
    tmpl = "minmax(0,3fr)" + "".join(" minmax(0,1.3fr)" for _ in cols[1:])
    head = "".join(f'<div style="padding:16px 20px;{"text-align:right" if i else ""}">{esc(c)}</div>' for i, c in enumerate(cols))
    body = ""
    for r, row in enumerate(d["rows"]):
        cells = "".join(f'<div style="padding:16px 20px;{"text-align:right" if i else ""}">{esc(c)}</div>' for i, c in enumerate(row))
        body += f'<div style="display:grid;grid-template-columns:{tmpl};border-bottom:1px solid #E5E7EB;background:{"#FAFBFA" if r % 2 else "#FFFFFF"}">{cells}</div>'
    formula = (f'<div style="display:flex;gap:16px;padding:14px 20px;background:{GREY};border-bottom:2px solid #E5E7EB">'
               f'<span style="font-weight:800;font-style:italic;color:#6B7280">fx</span>'
               f'<span style="font-family:Courier New,monospace;font-weight:700;color:{GREEN}">{esc(d["formula"])}</span></div>') if d.get("formula") else ""
    total = (f'<div style="display:flex;justify-content:space-between;align-items:center;padding:20px;background:{LIGHT}">'
             f'<span style="font-weight:800">{esc(d.get("total_label", "Totaal"))}</span>'
             f'<span style="font-weight:800;font-size:34px;color:{GREEN};outline:4px solid {GREEN};outline-offset:6px;border-radius:4px;padding:0 6px">{esc(d["total"])}</span></div>') if d.get("total") else ""
    return (f'<div style="display:flex;flex-direction:column;gap:20px"><h1 style="{H1};font-size:{d.get("size", 88)}px">{rich(d["headline"])}</h1>'
            + (f'<p style="margin:0;font-size:32px;color:#374151">{rich(d["sub"])}</p>' if d.get("sub") else "")
            + f'</div><div style="border:2px solid #D1D5DB;border-radius:20px;overflow:hidden;box-shadow:0 14px 34px rgba(17,24,39,.12);font-size:26px">'
            f'{formula}<div style="display:grid;grid-template-columns:{tmpl};background:{GREEN};color:#FFF;font-weight:700">{head}</div>{body}{total}</div>')


def s_compare(d):
    def card(label, items, good):
        col = GREEN if good else "#9CA3AF"
        lis = "".join(f'<div style="display:flex;gap:18px;align-items:flex-start;font-size:30px;line-height:1.3">'
                      f'<div style="flex:none;margin-top:2px">{icon("check" if good else "x", 34, col)}</div><div>{rich(t)}</div></div>' for t in items)
        return (f'<div style="flex:1;background:{"#FFFFFF" if good else GREY};border:{"3px solid " + GREEN if good else "2px solid #E5E7EB"};'
                f'border-radius:24px;padding:34px;display:flex;flex-direction:column;gap:22px">'
                f'<div style="{H1};font-size:52px;color:{col}">{esc(label)}</div>{lis}</div>')
    return (f'<h1 style="{H1};font-size:{d.get("size", 92)}px">{rich(d["headline"])}</h1>'
            f'<div style="display:flex;flex-direction:column;gap:24px">{card(d.get("before_label", "Voor"), d["before"], False)}'
            f'{card(d.get("after_label", "Na"), d["after"], True)}</div>')


def s_cta(d):
    return (f'<div style="display:flex;flex-direction:column;gap:28px;flex:1;justify-content:center">'
            f'<h1 style="{H1};font-size:150px;line-height:.98;color:#FFF">Stuur<br>“Excel”</h1>'
            f'<p style="margin:0;font-size:46px;font-weight:600;line-height:1.25;color:#FFF">{esc(d.get("line", "en ontvang een"))} '
            f'<span style="background:#FFF;color:{GREEN};padding:0 12px;border-radius:8px">{esc(d.get("highlight", "gratis voorbeeld"))}</span>.</p>'
            f'<p style="margin:0;font-size:30px;font-weight:500;color:{LIGHT}">{esc(d.get("sub", "Calculatie, urenregistratie en dashboard in één Excel-bestand."))}</p></div>'
            f'<div style="display:flex;align-items:center;gap:20px;background:#FFF;border-radius:999px;padding:18px 18px 18px 40px">'
            f'<span style="flex:1;font-size:40px;font-weight:800;color:{INK};letter-spacing:2px">EXCEL</span>'
            f'<div style="width:84px;height:84px;border-radius:50%;background:{INK};display:flex;align-items:center;justify-content:center">{icon("send", 40)}</div></div>')


FEED = {"cover": s_cover, "statement": s_statement, "bullets": s_bullets, "steps": s_steps,
        "table": s_table, "compare": s_compare, "cta": s_cta}


# ---------------------------------------------------------------- stories / reel frames (1080x1920)
def tall(inner, bg="#FFFFFF", dark=False):
    fg = "#FFFFFF" if dark else INK
    return (f'<div style="width:1080px;height:1920px;padding:150px 80px 200px;background:{bg};font-family:Inter,sans-serif;color:{fg};'
            f'display:flex;flex-direction:column;justify-content:space-between;gap:40px">'
            f'<div style="font-size:40px;font-weight:800"><span style="color:{"#FFFFFF" if dark else GREEN}">Excel</span><span>Baas</span></div>'
            f'<div style="flex:1;display:flex;flex-direction:column;justify-content:center">{inner}</div>'
            f'<div style="font-size:32px;font-weight:600;color:{LIGHT if dark else "#4B5563"}">@excelbaas</div></div>')


def t_question(d):
    opts = "".join(f'<div style="background:#FFF;color:{INK};border-radius:28px;padding:34px 40px;font-size:46px;font-weight:800;display:flex;gap:26px;align-items:center">'
                   f'<span style="flex:none;width:80px;height:80px;border-radius:50%;background:{GREEN};color:#FFF;display:flex;align-items:center;justify-content:center">{chr(65 + i)}</span>{esc(o)}</div>'
                   for i, o in enumerate(d["options"]))
    return tall(f'<div style="display:flex;flex-direction:column;gap:44px"><div style="font-size:40px;font-weight:600;color:{LIGHT}">{esc(d.get("kicker", "Vraag van de dag"))}</div>'
                f'<h1 style="{H1};font-size:{d.get("size", 120)}px;color:#FFF">{esc(d["question"])}</h1>{opts}'
                f'<div style="font-size:38px;font-weight:600;color:{LIGHT}">{esc(d.get("hint", "Reageer met de letter van jouw antwoord"))}</div></div>', GREEN, True)


def t_tip(d):
    return tall(f'<div style="display:flex;flex-direction:column;gap:44px"><div style="align-self:flex-start;font-size:36px;font-weight:800;color:#FFF;background:{GREEN};border-radius:999px;padding:12px 30px">{esc(d.get("kicker", "Tip"))}</div>'
                f'<h1 style="{H1};font-size:{d.get("size", 130)}px">{rich(d["headline"])}</h1>'
                + (f'<p style="margin:0;font-size:46px;font-weight:500;line-height:1.35;color:#374151">{rich(d["text"])}</p>' if d.get("text") else "")
                + '</div>', GREY)


def t_post(d, thumb):
    img = f'<img src="file://{thumb}" style="width:100%;max-height:1000px;object-fit:cover;object-position:top;border-radius:28px;box-shadow:0 20px 50px rgba(0,0,0,.35);mix-blend-mode:normal">' if thumb else ""
    return tall(f'<div style="display:flex;flex-direction:column;gap:44px"><h1 style="{H1};font-size:110px;color:#FFF">{esc(d.get("headline", "Nieuwe post staat online"))}</h1>'
                f'<div style="padding:0 60px">{img}</div><div style="font-size:42px;font-weight:600;color:{LIGHT}">{esc(d.get("text", "Bekijk hem in de feed →"))}</div></div>', GREEN, True)


def t_reel_title(d):
    return tall(f'<div style="display:flex;flex-direction:column;gap:44px;flex:1;justify-content:center"><h1 style="{H1};font-size:{d.get("size", 150)}px">{rich(d["headline"])}</h1>'
                + (f'<p style="margin:0;font-size:52px;font-weight:600;color:#374151">{rich(d["sub"])}</p>' if d.get("sub") else "") + '</div>')


def t_reel_formula(d):
    return tall(f'<div style="display:flex;flex-direction:column;gap:50px;flex:1;justify-content:center">'
                f'<div style="font-size:44px;font-weight:700;color:#374151">{rich(d.get("label", "Typ dit:"))}</div>'
                f'<div style="background:{INK};border-radius:28px;padding:50px 44px;font-family:Courier New,monospace;font-weight:700;font-size:{d.get("fsize", 52)}px;color:#7CC79A;line-height:1.4;word-break:break-word">{esc(d["formula"])}</div>'
                + (f'<p style="margin:0;font-size:50px;font-weight:600;line-height:1.35">{rich(d["text"])}</p>' if d.get("text") else "") + '</div>', GREY)


def t_reel_cta(d):
    return tall(f'<div style="display:flex;flex-direction:column;gap:40px;flex:1;justify-content:center">'
                f'<h1 style="{H1};font-size:170px;color:#FFF">Stuur<br>“Excel”</h1>'
                f'<p style="margin:0;font-size:56px;font-weight:600;color:#FFF">{esc(d.get("text", "en ontvang een gratis voorbeeld."))}</p></div>', GREEN, True)


TALL = {"story_question": t_question, "story_tip": t_tip, "reel_title": t_reel_title,
        "reel_formula": t_reel_formula, "reel_tip": t_tip, "reel_cta": t_reel_cta}


# ---------------------------------------------------------------- rendering
def shot(html_str, out, w, h):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_str)
        p = f.name
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    "--allow-file-access-from-files", "--virtual-time-budget=3000", f"--window-size={w},{h}",
                    f"--screenshot={out}", "file://" + p], check=True, capture_output=True)
    os.unlink(p)


def make_reel(frames, out, secs=3.0, fade=0.5):
    n = len(frames)
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for fr in frames:
        args += ["-loop", "1", "-t", str(secs), "-i", fr]
    args += ["-f", "lavfi", "-t", str(n * secs - (n - 1) * fade), "-i", "anullsrc=r=44100:cl=stereo"]
    chain, last = [], "0:v"
    for i in range(1, n):
        lab = f"v{i}"
        chain.append(f"[{last}][{i}:v]xfade=transition=fade:duration={fade}:offset={i * (secs - fade):.2f}[{lab}]")
        last = lab
    chain.append(f"[{last}]format=yuv420p,scale=1080:1920,fps=30[vout]")
    args += ["-filter_complex", ";".join(chain), "-map", "[vout]", "-map", f"{n}:a",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-shortest",
             "-movflags", "+faststart", out]
    subprocess.run(args, check=True)


def main(plan_path):
    plan = json.load(open(plan_path, encoding="utf-8"))
    week = plan["week"]
    outdir = os.path.join(ROOT, "media", week)
    os.makedirs(outdir, exist_ok=True)
    manifest = []
    feed_thumbs = {}
    for item in plan["items"]:
        iid, kind = item["id"], item["kind"]
        d = os.path.join(outdir, iid)
        os.makedirs(d, exist_ok=True)
        files = []
        if kind == "carousel":
            slides = item["slides"]
            for n, s in enumerate(slides, 1):
                last = n == len(slides)
                is_cta = s["type"] == "cta"
                body = frame(FEED[s["type"]](s), n, len(slides), GREEN if is_cta else s.get("bg", "#FFFFFF"),
                             swipe=not last, dark=is_cta)
                out = os.path.join(d, f"{n:02d}.png")
                shot(page(body, 1080, 1350), out, 1080, 1350)
                files.append(out)
            feed_thumbs[iid] = files[0]
        elif kind == "story":
            s = item["story"]
            if s["type"] == "story_post":
                body = t_post(s, feed_thumbs.get(s.get("of")))
            else:
                body = TALL[s["type"]](s)
            out = os.path.join(d, "story.png")
            shot(page(body, 1080, 1920), out, 1080, 1920)
            files.append(out)
        elif kind == "reel":
            tmp = []
            for n, s in enumerate(item["frames"], 1):
                out = os.path.join(d, f"frame{n:02d}.png")
                shot(page(TALL[s["type"]](s), 1080, 1920), out, 1080, 1920)
                tmp.append(out)
            mp4 = os.path.join(d, "reel.mp4")
            make_reel(tmp, mp4, item.get("secs", 3.0))
            files.append(mp4)
            feed_thumbs[iid] = tmp[0]
            cover = os.path.join(d, "cover.jpg")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp[0], "-q:v", "3", cover], check=True)
            item["cover"] = RAW + os.path.relpath(cover, ROOT)
        rel = [RAW + os.path.relpath(f, ROOT) for f in files]
        manifest.append({k: v for k, v in {"id": iid, "kind": kind, "when": item["when"], "media": rel,
                                            "caption": item.get("caption", ""), "first_comment": item.get("first_comment", ""),
                                            "cover": item.get("cover")}.items() if v is not None})
        print(iid, len(files), "bestand(en)")
    json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("manifest:", os.path.join(outdir, "manifest.json"))


if __name__ == "__main__":
    main(sys.argv[1])
