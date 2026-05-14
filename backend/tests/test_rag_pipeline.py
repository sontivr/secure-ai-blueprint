from backend.rag_pipeline import _chunk_text, build_prompt


class TestChunkText:
    def test_empty_string_returns_empty_list(self):
        assert _chunk_text("", source="doc.txt") == []

    def test_whitespace_only_returns_empty_list(self):
        assert _chunk_text("   \n\t  ", source="doc.txt") == []

    def test_short_text_produces_single_chunk(self):
        chunks = _chunk_text("Hello world.", source="doc.txt")
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."

    def test_chunk_source_is_set(self):
        chunks = _chunk_text("Some content", source="policy.txt")
        assert chunks[0].source == "policy.txt"

    def test_chunk_id_starts_with_source(self):
        chunks = _chunk_text("Some content", source="myfile.txt")
        assert chunks[0].chunk_id.startswith("myfile.txt:")

    def test_chunk_id_is_unique_per_chunk(self):
        text = "A" * 3000
        chunks = _chunk_text(text, source="big.txt", max_chars=1000, overlap=100)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_metadata_contains_source_and_chunk_index(self):
        chunks = _chunk_text("text here", source="s.txt")
        assert chunks[0].metadata["source"] == "s.txt"
        assert chunks[0].metadata["chunk_index"] == 0

    def test_chunk_index_increments(self):
        text = "B" * 3000
        chunks = _chunk_text(text, source="s.txt", max_chars=1000, overlap=100)
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_long_text_produces_multiple_chunks(self):
        text = "word " * 600  # ~3000 chars
        chunks = _chunk_text(text, source="long.txt", max_chars=1200, overlap=150)
        assert len(chunks) > 1

    def test_overlap_means_chunks_share_content(self):
        text = "X" * 2500
        chunks = _chunk_text(text, source="t.txt", max_chars=1000, overlap=200)
        for a, b in zip(chunks, chunks[1:]):
            # The tail of chunk A should appear at the start of chunk B
            assert a.text[-100:] in b.text

    def test_base_metadata_is_merged(self):
        chunks = _chunk_text("some text", source="s.txt", base_metadata={"page": 7})
        assert chunks[0].metadata["page"] == 7
        assert chunks[0].metadata["source"] == "s.txt"

    def test_no_chunk_exceeds_max_chars(self):
        text = "Z" * 5000
        max_chars = 1200
        chunks = _chunk_text(text, source="t.txt", max_chars=max_chars, overlap=150)
        for c in chunks:
            assert len(c.text) <= max_chars


class TestBuildPrompt:
    def test_empty_contexts_uses_placeholder(self):
        prompt = build_prompt("What is X?", contexts=[])
        assert "[NO CONTEXT RETRIEVED]" in prompt

    def test_question_is_in_prompt(self):
        prompt = build_prompt("What is the retention period?", contexts=[])
        assert "What is the retention period?" in prompt

    def test_context_text_is_included(self):
        ctx = [{"id": "c1", "source": "policy.txt", "page": None, "text": "Keep records for 7 years."}]
        prompt = build_prompt("How long?", ctx)
        assert "Keep records for 7 years." in prompt

    def test_context_source_is_cited(self):
        ctx = [{"id": "c1", "source": "policy.txt", "page": None, "text": "Some text."}]
        prompt = build_prompt("Q?", ctx)
        assert "policy.txt" in prompt

    def test_context_page_is_cited_when_present(self):
        ctx = [{"id": "c1", "source": "doc.pdf", "page": 5, "text": "Content."}]
        prompt = build_prompt("Q?", ctx)
        assert "page=5" in prompt

    def test_context_page_omitted_when_none(self):
        ctx = [{"id": "c1", "source": "doc.txt", "page": None, "text": "Content."}]
        prompt = build_prompt("Q?", ctx)
        assert "page=" not in prompt

    def test_multiple_contexts_all_included(self):
        ctx = [
            {"id": "c1", "source": "a.txt", "page": None, "text": "Alpha content."},
            {"id": "c2", "source": "b.txt", "page": 2, "text": "Beta content."},
        ]
        prompt = build_prompt("Q?", ctx)
        assert "Alpha content." in prompt
        assert "Beta content." in prompt
