import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import career, catalog, indexing, literature, profile_taxonomy, relations


class CareerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / "profile"
        self.items = self.root / "items"
        self.applications = self.root / "applications"
        self.taxonomy = self.root / "profile-taxonomy.yaml"
        self.literature_items = Path(self.tempdir.name) / "literature" / "items"
        specs = {name: dict(spec) for name, spec in catalog.SPECS.items()}
        specs["profile"]["dir"] = self.items
        self.patchers = [
            mock.patch.object(career, "CAREER", self.root),
            mock.patch.object(career, "ITEMS", self.items),
            mock.patch.object(career, "APPLICATIONS", self.applications),
            mock.patch.object(career, "TAXONOMY", self.taxonomy),
            mock.patch.object(profile_taxonomy, "TAXONOMY", self.taxonomy),
            mock.patch.object(catalog, "SPECS", specs),
            mock.patch.object(literature, "LITERATURE_ITEMS", self.literature_items),
            mock.patch.object(relations, "RELATIONS", self.root / "relations"),
            mock.patch.object(indexing, "INDEX", self.root / "search" / "index.sqlite"),
            mock.patch.object(catalog.project, "existing_project_names", return_value=[]),
            mock.patch.object(career.anatomy, "rebuild_profile", return_value={"by-type": 0}),
        ]
        for patcher in self.patchers:
            patcher.start()
        root_parser = argparse.ArgumentParser()
        sub = root_parser.add_subparsers(dest="domain", required=True)
        career.add_parser(sub, "profile")
        create_cmd = sub.add_parser("create")
        create_sub = create_cmd.add_subparsers(dest="create_kind", required=True)
        career.attach_create_parser(create_sub, name="profile")
        self.parser = root_parser

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def invoke(self, *parts):
        # Minting is verb-first (`ws create profile ...`); the profile domain
        # keeps only its specialists.
        if parts[0] == "create":
            argv = ["create", "profile", *parts[1:]]
        else:
            argv = ["profile", *parts]
        args = self.parser.parse_args(argv)
        with contextlib.redirect_stdout(io.StringIO()):
            args.func(args)

    def init(self):
        self.invoke("init")

    def make_cv(self, **overrides):
        out = Path(self.tempdir.name) / "application"
        parts = [
            "make-cv", "--out", str(out), "--no-build",
            "--no-dob", "--no-post-nominals",
        ]
        if overrides.get("spec"):
            parts += ["--spec", str(overrides["spec"])]
        if overrides.get("force"):
            parts.append("--force")
        self.invoke(*parts)
        return out / "cv.tex"

    def create_identity(self):
        self.invoke(
            "create", "Test Person", "--type", "identity",
            "--email", "test@example.org", "--address", "Test College",
            "--headline", "Quantum researcher",
        )

    def test_init_scaffolds_object_store_without_enforcing_application_layout(self):
        self.init()
        self.assertTrue(self.items.is_dir())
        self.assertTrue(self.applications.is_dir())
        self.assertTrue(self.taxonomy.exists())
        self.assertTrue((self.root / ".git").is_dir())
        self.assertFalse((self.root / "cv").exists())
        self.assertFalse((self.applications / "templates").exists())
        self.assertEqual(profile_taxonomy.type_ids(), list(profile_taxonomy.DEFAULTS["type"]))
        marker = self.root / "README.md"
        marker.write_text("custom\n", encoding="utf-8")
        self.init()
        self.assertEqual(marker.read_text(encoding="utf-8"), "custom\n")

    def test_objects_render_into_one_comprehensive_cv(self):
        self.init()
        self.create_identity()
        self.invoke(
            "create", "DPhil Physics", "--type", "education",
            "--subtitle", "Example City & Sons", "--start", "2024-10",
            "--end", "present", "--bullet", "Built a shuttling simulator.",
        )
        text = self.make_cv().read_text(encoding="utf-8")
        self.assertIn("Test Person", text)
        self.assertIn("Test College", text)
        self.assertIn("test@example.org", text)
        self.assertIn(r"\begin{center}", text)
        self.assertIn(r"\end{center}", text)
        self.assertIn(r"\\[2pt]", text)
        self.assertIn(r"\\[5pt]", text)
        self.assertIn("DPhil Physics", text)
        self.assertIn(r"Example City \& Sons", text)
        self.assertIn("Built a shuttling simulator.", text)
        self.assertIn(r"\end{document}", text)

    def test_cv_spec_selects_orders_and_tailors_profile_objects(self):
        self.init()
        self.create_identity()
        self.invoke(
            "create", "DPhil Physics", "--type", "education",
            "--subtitle", "Example City", "--start", "2024-10",
            "--end", "present", "--bullet", "Canonical research bullet.",
        )
        self.invoke(
            "create", "Older Degree", "--type", "education",
            "--subtitle", "Elsewhere", "--start", "2020-10", "--end", "2021-06",
        )
        self.invoke(
            "create", "Electromagnetism", "--type", "teaching",
            "--subtitle", "Example City", "--year", "2025",
        )
        spec = Path(self.tempdir.name) / "cv-spec.yaml"
        spec.write_text(
            "schema_version: 1\n"
            "headline: Tailored theoretical physicist\n"
            "summary: Application-specific opening summary.\n"
            "sections:\n"
            "  - type: teaching\n"
            "    title: Relevant Teaching\n"
            "    items:\n"
            "      - ref: profile:electromagnetism\n"
            "  - type: education\n"
            "    title: Selected Education\n"
            "    items:\n"
            "      - ref: profile:dphil-physics\n"
            "        name: DPhil in Quantum Technologies\n"
            "        bullets: []\n",
            encoding="utf-8",
        )

        text = self.make_cv(spec=spec).read_text(encoding="utf-8")

        self.assertIn("Tailored theoretical physicist", text)
        self.assertNotIn("Quantum researcher", text)
        self.assertIn("Application-specific opening summary.", text)
        self.assertIn("Relevant Teaching", text)
        self.assertIn("Selected Education", text)
        self.assertLess(text.index("Relevant Teaching"), text.index("Selected Education"))
        self.assertIn("DPhil in Quantum Technologies", text)
        self.assertNotIn("Canonical research bullet.", text)
        self.assertNotIn("Older Degree", text)

    def test_cv_spec_rejects_unknown_profile_ref(self):
        self.init()
        self.create_identity()
        spec = Path(self.tempdir.name) / "cv-spec.yaml"
        spec.write_text(
            "schema_version: 1\n"
            "sections:\n"
            "  - type: education\n"
            "    items:\n"
            "      - ref: profile:missing\n",
            encoding="utf-8",
        )
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.make_cv(spec=spec)

    def test_qualification_status_and_readable_dates_render(self):
        self.init()
        self.create_identity()
        self.invoke(
            "create", "MSc Physics", "--type", "education",
            "--start", "2021-10", "--end", "2023-08",
            "--qualification-status", "programme not completed",
        )
        text = self.make_cv().read_text(encoding="utf-8")
        self.assertIn("Oct 2021--Aug 2023", text)
        self.assertIn("programme not completed", text)

    def test_education_keeps_institution_and_status_plain_and_details_as_bullets(self):
        entry = catalog.ObjectRef(
            id="profile:test-degree",
            type="profile",
            title="MSc Physics",
            data={
                "type": "education",
                "subtitle": "Test University",
                "qualification_status": "programme not completed",
                "description": "Advanced coursework in theoretical physics.",
                "bullets": ["Master's thesis on quantum dynamics."],
            },
            key="test-degree",
        )

        rendered = "\n".join(career._entry_lines(entry))

        self.assertIn(r"Test University\par", rendered)
        self.assertNotIn(r"\item Test University", rendered)
        self.assertIn(r"{\small\itshape programme not completed}\par", rendered)
        self.assertNotIn(r"\item programme not completed", rendered)
        self.assertIn(r"\item Advanced coursework in theoretical physics.", rendered)
        self.assertIn(r"\item Master's thesis on quantum dynamics.", rendered)

    def test_publication_is_explicitly_related_to_library_source(self):
        self.init()
        self.create_identity()
        source = self.literature_items / "Mine2026"
        source.mkdir(parents=True)
        (source / "citation.bib").write_text(
            "@article{Mine2026,\n  title = {A Related Paper},\n"
            "  author = {Person, Test},\n  journal = {Journal of Tests},\n"
            "  year = {2026},\n}\n",
            encoding="utf-8",
        )
        self.invoke("create", "Publication record", "--type", "publication")
        publication = next(
            ref for ref in catalog.stored_objects("profile")
            if (ref.data or {}).get("type") == "publication"
        )
        # Relations come exclusively from `ws relate`, never creation flags.
        relations.create(publication.id, "literature:Mine2026", "represents")
        edges = relations.for_object(publication.id)
        self.assertEqual(edges[0]["relation"], "represents")
        self.assertEqual(edges[0]["object"], "literature:Mine2026")
        self.assertIn("A Related Paper", self.make_cv().read_text(encoding="utf-8"))

    def test_publication_rendering_normalizes_html_from_citation_providers(self):
        rendered = career.format_publication({
            "author": "Person, Test",
            "title": "A result <i>via</i> simulation",
            "journal": "Research &amp; Development",
            "year": "2026",
        })
        self.assertIn("via", rendered)
        self.assertIn(r"Research \& Development", rendered)
        self.assertNotIn("<i>", rendered)
        self.assertNotIn("&amp;", rendered)

    def test_entry_does_not_repeat_organisation_already_in_title(self):
        entry = catalog.ObjectRef(
            id="profile:test",
            type="profile",
            title="Vice President, Example Society",
            data={"type": "volunteering", "start": "2026", "end": "present"},
            key="test",
        )
        organisation = catalog.ObjectRef(
            id="organisation:example-society",
            type="organisation",
            title="Example Society",
            key="example-society",
        )
        with mock.patch.object(career, "_related", return_value=[("at", organisation)]):
            lines = career._entry_lines(entry)
        self.assertNotIn("Example Society" + r"\par", lines)

    def test_entry_does_not_repeat_organisation_inside_richer_subtitle(self):
        entry = catalog.ObjectRef(
            id="profile:test",
            type="profile",
            title="Electromagnetism",
            data={
                "type": "teaching",
                "subtitle": "Prelims tutorials, Example College, Example University",
            },
            key="test",
        )
        organisation = catalog.ObjectRef(
            id="organisation:example-university",
            type="organisation",
            title="Example University",
            key="example-university",
        )
        with mock.patch.object(career, "_related", return_value=[("at", organisation)]):
            rendered = "\n".join(career._entry_lines(entry))
        self.assertEqual(rendered.count("Example University"), 1)

    def test_only_one_active_identity_is_allowed(self):
        self.init()
        self.create_identity()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.invoke("create", "Second Person", "--type", "identity")

    def test_ensure_is_idempotent_within_a_profile_type(self):
        self.init()
        self.invoke("create", "Python", "--type", "education", "--ensure")
        self.invoke("create", "Python", "--type", "skill", "--ensure")
        self.invoke("create", "Python", "--type", "skill", "--ensure")
        self.create_identity()
        self.invoke("create", "Test Person", "--type", "identity", "--ensure")
        self.assertEqual(len(catalog.stored_objects("profile")), 3)

    def test_make_cv_refuses_overwrite_without_force(self):
        self.init()
        self.create_identity()
        self.make_cv()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.make_cv()
        self.make_cv(force=True)

    def test_make_cv_builds_pdf_beside_tex_by_default(self):
        self.init()
        self.create_identity()
        out = Path(self.tempdir.name) / "application"

        def fake_build(tex_path):
            pdf_path = tex_path.with_suffix(".pdf")
            pdf_path.write_bytes(b"%PDF-1.4\n")
            return pdf_path

        with mock.patch.object(career, "build_pdf", side_effect=fake_build) as build:
            self.invoke("make-cv", "--out", str(out))

        self.assertTrue((out / "cv.tex").is_file())
        self.assertTrue((out / "cv.pdf").is_file())
        build.assert_called_once_with(out / "cv.tex")

    def test_build_pdf_copies_deliverable_beside_tex(self):
        folder = Path(self.tempdir.name) / "application"
        folder.mkdir()
        tex_path = folder / "cv.tex"
        tex_path.write_text("test", encoding="utf-8")

        def fake_run(*_args, **_kwargs):
            built = folder / "out" / "cv.pdf"
            built.parent.mkdir()
            built.write_bytes(b"%PDF-1.4\ncompiled\n")
            return career.subprocess.CompletedProcess([], 0)

        with mock.patch.object(career.shutil, "which", return_value="/usr/bin/latexmk"), \
             mock.patch.object(career.subprocess, "run", side_effect=fake_run):
            result = career.build_pdf(tex_path)

        self.assertEqual(result, folder / "cv.pdf")
        self.assertEqual(result.read_bytes(), b"%PDF-1.4\ncompiled\n")


if __name__ == "__main__":
    unittest.main()
