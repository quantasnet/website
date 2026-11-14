# website

Source for [www.quantasnet.com](https://www.quantasnet.com), Andrew Landsverk's home page.

Plain HTML and CSS in `site/`, with no build step and no dependencies.

- Preview: `python3 -m http.server -d site 8000`, then open http://localhost:8000
- Test: `python3 -I -m unittest discover -s tests -v`
- Deploy: every push to `main` publishes `site/` to GitHub Pages (`.github/workflows/ci.yml`).

Project Pages sites under the `Quantas` account used to live at `www.quantasnet.com/<repo>/`. Each one keeps its old address through a redirect page at `site/<repo>/index.html` pointing to `https://quantas.github.io/<repo>/`; add one (and an entry in `PROJECT_REDIRECTS` in the tests) for any new project site.

Licensed under Apache-2.0.
