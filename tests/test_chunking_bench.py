from __future__ import annotations

from eval.chunking_bench import compare_configs, find_needles, make_document, run_config


class TestBenchFixtures:
    def test_make_document_embeds_needles(self) -> None:
        text = make_document(words_per_section=200, sections=5)
        needles = find_needles(text)
        assert len(needles) == 5
        assert all("NEEDLE-MARKER" in n for n in needles)

    def test_needles_are_recoverable(self) -> None:
        text = make_document(sections=5)
        rows = [run_config(text, 512, ov, find_needles(text)) for ov in (0, 50)]
        assert rows[0]["needles"] == 5
        assert rows[1]["needles"] == 5


class TestOverlapSweep:
    def test_overlap_improves_preservation(self) -> None:
        rows = compare_configs(chunk_size=512, overlaps=[0, 50, 100])
        by_overlap = {int(r["overlap"]): r for r in rows}
        # overlap 0 can drop boundary-straddling needles...
        assert by_overlap[0]["preservation"] <= by_overlap[50]["preservation"]
        # ...while any overlap fully preserves them.
        assert by_overlap[50]["preservation"] == 1.0
        assert by_overlap[100]["preservation"] == 1.0

    def test_overlap_adds_redundancy(self) -> None:
        rows = compare_configs(chunk_size=512, overlaps=[50, 100])
        by_overlap = {int(r["overlap"]): r for r in rows}
        assert by_overlap[100]["overhead"] > by_overlap[50]["overhead"]

    def test_overlap_50_is_best_tradeoff(self) -> None:
        """Overlap 50 reaches full preservation at the lowest overhead."""
        rows = compare_configs(chunk_size=512, overlaps=[50, 64, 100])
        by_overlap = {int(r["overlap"]): r for r in rows}
        assert by_overlap[50]["preservation"] == 1.0
        assert by_overlap[50]["overhead"] <= by_overlap[64]["overhead"]
        assert by_overlap[50]["overhead"] < by_overlap[100]["overhead"]
