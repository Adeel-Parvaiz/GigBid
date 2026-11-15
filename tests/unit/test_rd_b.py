import sys
import types
from types import SimpleNamespace

import numpy as np

from rag.index.vector import FastEmbedder, HashingEmbedder
from rag.retriever import make_embedder


def test_fastembedder_uses_normalized_local_vectors_and_records_model_fingerprint(monkeypatch, tmp_path):
    artifact = tmp_path / "model.onnx"
    artifact.write_bytes(b"test model artifact")
    description = SimpleNamespace(
        sources=SimpleNamespace(hf="test/model"),
        model_file="model.onnx",
        dim=2,
        license="apache-2.0",
    )

    class FakeTextEmbedding:
        def __init__(self, model_name, **options):
            assert model_name == "test/model"
            self.model = SimpleNamespace(_model_dir=tmp_path, model_description=description)

        def embed(self, texts, batch_size):
            assert texts == ["first", "second"] and batch_size == 4
            return iter([np.array([3.0, 4.0]), np.array([0.0, 2.0])])

    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeTextEmbedding))
    monkeypatch.setattr("rag.index.vector.version", lambda _: "0.test")
    embedder = FastEmbedder("test/model", batch_size=4)
    vectors = embedder.embed(["first", "second"])

    assert vectors.shape == (2, 2)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert embedder.metadata["revision"] == tmp_path.name
    assert embedder.metadata["dimensions"] == 2
    assert embedder.metadata["package_version"] == "0.test"
    assert len(embedder.metadata["model_file_sha256"]) == 64


def test_fastembedder_returns_empty_matrix_for_empty_input(monkeypatch, tmp_path):
    class FakeTextEmbedding:
        def __init__(self, model_name, **options):
            self.model = SimpleNamespace(
                _model_dir=tmp_path,
                model_description=SimpleNamespace(
                    sources=SimpleNamespace(hf="test/model"), model_file="model.onnx",
                    dim=2, license="apache-2.0",
                ),
            )
            (tmp_path / "model.onnx").write_bytes(b"test")

    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeTextEmbedding))
    monkeypatch.setattr("rag.index.vector.version", lambda _: "0.test")
    assert FastEmbedder().embed([]).shape == (0, 0)


def test_embedder_selection_is_explicit_and_backward_compatible():
    assert isinstance(make_embedder({"rag": {"embedder": "hashing"}}), HashingEmbedder)
    try:
        make_embedder({"rag": {"embedder": "unknown"}})
    except ValueError as exc:
        assert "unknown embedder" in str(exc)
    else:
        raise AssertionError("Unknown embedding configuration should fail explicitly")
