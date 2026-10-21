"""Sous-processus isolé pour Playwright, compatible avec les boucles Streamlit."""
import json
import math
import os
from pathlib import Path
import sys
from .html_export import export_html


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        settings = {"headless": True}
        if os.getenv("BPMN_CHROMIUM_EXECUTABLE"):
            settings["executable_path"] = os.environ["BPMN_CHROMIUM_EXECUTABLE"]
        with pw.chromium.launch(**settings) as browser:
            if sys.argv[1] == "--check":
                return
            folder = Path(sys.argv[1])
            model = json.loads((folder / "model.json").read_text(encoding="utf-8"))
            direction = sys.argv[2]
            html = folder / "diagram.html"
            html.write_text(export_html(model, direction), encoding="utf-8")
            context = browser.new_context(offline=True, viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
            page = context.new_page()
            page.set_default_timeout(30000)
            page.goto(html.resolve().as_uri())
            page.wait_for_function("document.querySelector('#diagram svg') || document.querySelector('#status').textContent")
            error = page.locator("#status").inner_text()
            if error:
                raise ValueError(error[:1000])
            await_fonts = "() => document.fonts.ready.then(() => true)"
            page.evaluate(await_fonts)
            size = page.locator("#diagram svg").evaluate("""svg => {
                const v=svg.viewBox.baseVal;
                return {width:Math.ceil(v.width),height:Math.ceil(v.height)};
            }""")
            width, height = size["width"], size["height"]
            if not all(math.isfinite(n) and 0 < n <= 12000 for n in (width, height)) or width * height > 24000000:
                raise ValueError("Diagramme trop grand pour une comparaison lisible (24 mégapixels maximum)")
            page.add_style_tag(content="""body{margin:0;background:white}header,.toolbar,.editor,details,main>p,#status{display:none}
                main{padding:0;max-width:none;margin:0}.grid{display:block}.panel{padding:0;border:0}
                #diagram{overflow:visible;min-height:0}#diagram svg{max-width:none!important}""")
            page.locator("#diagram svg").evaluate("""(svg,size)=>{
                svg.setAttribute('width',size.width);svg.setAttribute('height',size.height);
                svg.style.width=size.width+'px';svg.style.height=size.height+'px';
            }""", size)
            page.set_viewport_size({"width": max(320, width + 10), "height": max(240, height + 10)})
            labels_visible = page.locator("#diagram svg p").evaluate_all("""labels => labels.every(el => {
                if(!el.textContent.trim()) return true;
                const box=el.getBoundingClientRect();
                return box.width>0 && box.height>0;
            })""")
            if not labels_visible:
                raise ValueError("Le rendu masque des libellés Mermaid; capture refusée")
            svg = page.locator("#diagram").inner_html()
            (folder / "diagram.svg").write_text(svg, encoding="utf-8")
            page.locator("#diagram svg").screenshot(path=str(folder / "diagram.png"), animations="disabled")
            context.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc)[:1500], file=sys.stderr)
        sys.exit(1)
