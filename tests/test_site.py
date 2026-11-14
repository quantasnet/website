"""Structure, content and link-integrity checks for site/.

Stdlib only, so CI and a fresh laptop run it with no install step:
    python3 -I -m unittest discover -s tests -v
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

REQUIRED_LINKS = [
    "mailto:andrew@quantasnet.com",
    "https://www.linkedin.com/in/andrew-landsverk-12a2b121/",
    "https://github.com/Quantas",
    "https://sharkops.io",
    "https://github.com/sharkops-io",
    "https://github.com/Quantas/shark-ng-table",
]
REQUIRED_TEXT = [
    "Senior Software Engineer", "WIN Technology", "Eau Claire, WI", "2019",
    "Kubernetes", "Ansible", "platform engineering", "SharkOps", "shark-ng-table", "Quantas",
]
FORBIDDEN_TEXT = ["Nelnet", "gitshark", "QLAN", "shark-ci-server", "dbUnit", "QuantasNet"]
SHARK_NG_TABLE_DEMO = "https://quantas.github.io/shark-ng-table/"
# Project Pages sites under the Quantas account used to be served at
# www.quantasnet.com/<repo>/ through the old user site's custom domain. Each
# old path keeps working through a redirect stub to the site's github.io URL.
PROJECT_REDIRECTS = {
    "shark-ng-table": SHARK_NG_TABLE_DEMO,
    "shark-ng-table-samples": "https://quantas.github.io/shark-ng-table-samples/",
    "wow-forever-atlas": "https://quantas.github.io/wow-forever-atlas/",
}

# (tag, attribute) pairs that make the browser fetch something.
RESOURCE_ATTRS = {("link", "href"), ("script", "src"), ("img", "src"), ("source", "src")}
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\(")


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []  # (tag, attrs dict)
        self.text = []
        self._skip = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)

    def visible_text(self):
        return re.sub(r"\s+", " ", " ".join(self.text))

    def find(self, tag):
        return [a for t, a in self.tags if t == tag]


def html_files():
    return sorted(SITE.rglob("*.html"))


def css_files():
    return sorted(SITE.rglob("*.css"))


def parse(path):
    return Page(path.read_text(encoding="utf-8"))


def resource_refs(page):
    """URLs the page fetches (canonical links are metadata, not fetches)."""
    refs = []
    for tag, attrs in page.tags:
        for t, attr in RESOURCE_ATTRS:
            if tag == t and attrs.get(attr):
                if tag == "link" and attrs.get("rel") == "canonical":
                    continue
                refs.append(attrs[attr])
    return refs


def is_external(ref):
    return ref.startswith(("http:", "https:", "//"))


def is_local_anchor(href):
    return not (is_external(href) or href.startswith(("#", "mailto:", "tel:")))


def resolves(base_file, ref):
    path = ref.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return True
    target = (base_file.parent / path).resolve()
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target.is_file()


def strip_token_blocks(css):
    """Remove :root / [data-theme] rules and prefers-color-scheme media blocks."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out, i = [], 0
    while i < len(css):
        m = re.compile(r"(@media[^{]*prefers-color-scheme[^{]*|[^{}]*(?::root|\[data-theme)[^{}]*)\{").search(css, i)
        if not m:
            out.append(css[i:])
            break
        out.append(css[i:m.start()])
        depth, j = 1, m.end()
        while depth and j < len(css):
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        i = j
    return "".join(out)


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index_path = SITE / "index.html"

    def index(self):
        self.assertTrue(self.index_path.is_file(), "site/index.html missing")
        return parse(self.index_path)

    def test_cname(self):
        self.assertEqual((SITE / "CNAME").read_text().strip(), "www.quantasnet.com")

    def test_index_head(self):
        raw = self.index_path.read_text(encoding="utf-8") if self.index_path.is_file() else ""
        page = self.index()
        self.assertEqual(page.find("html")[0].get("lang"), "en")
        self.assertTrue(any("charset" in a for a in page.find("meta")))
        names = {a.get("name"): a.get("content", "") for a in page.find("meta")}
        self.assertIn("viewport", names)
        self.assertTrue(names.get("description", "").strip())
        title = re.search(r"<title>(.*?)</title>", raw, re.S)
        self.assertTrue(title and "Andrew Landsverk" in title.group(1))
        self.assertTrue(any("icon" in (a.get("rel") or "") for a in page.find("link")))

    def test_required_content(self):
        text = self.index().visible_text().lower()
        for s in REQUIRED_TEXT:
            self.assertIn(s.lower(), text, s)

    def test_required_links(self):
        hrefs = {a.get("href") for a in self.index().find("a")}
        for link in REQUIRED_LINKS:
            self.assertIn(link, hrefs)

    def test_forbidden_content(self):
        text = self.index().visible_text()
        for s in FORBIDDEN_TEXT:
            self.assertNotIn(s, text)

    def test_no_external_resources(self):
        self.assertTrue(html_files())
        for f in html_files():
            for ref in resource_refs(parse(f)):
                self.assertFalse(is_external(ref), f"{f.relative_to(SITE)}: {ref}")
        for f in css_files():
            for ref in CSS_URL.findall(f.read_text(encoding="utf-8")):
                self.assertFalse(is_external(ref), f"{f.relative_to(SITE)}: {ref}")

    def test_local_refs_are_relative(self):
        self.assertTrue(html_files())
        for f in html_files():
            page = parse(f)
            refs = resource_refs(page) + [a.get("href", "") for a in page.find("a")]
            for ref in refs:
                if ref and is_local_anchor(ref):
                    self.assertFalse(ref.startswith("/"), f"{f.relative_to(SITE)}: {ref}")
        for f in css_files():
            for ref in CSS_URL.findall(f.read_text(encoding="utf-8")):
                if not ref.startswith("data:"):
                    self.assertFalse(ref.startswith("/"), f"{f.relative_to(SITE)}: {ref}")

    def test_local_refs_resolve(self):
        self.assertTrue(html_files())
        for f in html_files():
            page = parse(f)
            refs = [r for r in resource_refs(page) if not r.startswith("data:")]
            refs += [a["href"] for a in page.find("a") if a.get("href") and is_local_anchor(a["href"])]
            for ref in refs:
                self.assertTrue(resolves(f, ref), f"{f.relative_to(SITE)}: {ref}")
        for f in css_files():
            for ref in CSS_URL.findall(f.read_text(encoding="utf-8")):
                if not ref.startswith("data:"):
                    self.assertTrue(resolves(f, ref), f"{f.relative_to(SITE)}: {ref}")

    def test_images_have_alt(self):
        for f in html_files():
            for img in parse(f).find("img"):
                self.assertIn("alt", img, f"{f.relative_to(SITE)}: {img.get('src')}")

    def test_colors_only_in_tokens(self):
        self.assertTrue(css_files())
        for f in css_files():
            leftover = COLOR_LITERAL.findall(strip_token_blocks(f.read_text(encoding="utf-8")))
            self.assertEqual(leftover, [], f.relative_to(SITE))

    def test_project_redirects(self):
        for name, target in PROJECT_REDIRECTS.items():
            with self.subTest(name=name):
                path = SITE / name / "index.html"
                self.assertTrue(path.is_file())
                page = parse(path)
                refresh = [a for a in page.find("meta") if (a.get("http-equiv") or "").lower() == "refresh"]
                self.assertEqual(refresh[0].get("content"), f"0; url={target}")
                canonical = [a for a in page.find("link") if a.get("rel") == "canonical"]
                self.assertEqual(canonical[0].get("href"), target)
                self.assertIn(target, {a.get("href") for a in page.find("a")})

    def test_404(self):
        path = SITE / "404.html"
        self.assertTrue(path.is_file())
        page = parse(path)
        self.assertIn("https://www.quantasnet.com/", {a.get("href") for a in page.find("a")})
        self.assertFalse([a for a in page.find("link") if a.get("rel") == "stylesheet"])


if __name__ == "__main__":
    unittest.main()
