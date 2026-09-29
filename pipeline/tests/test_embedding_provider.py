import os
import unittest

from pipeline.embed import resolve_embedding


class EmbeddingProviderTests(unittest.TestCase):
    def setUp(self):
        self._saved = {
            key: os.environ.get(key)
            for key in ("EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "VOYAGE_API_KEY")
        }

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_refuses_openai_embeddings(self):
        os.environ["EMBEDDING_PROVIDER"] = "openai"
        os.environ["EMBEDDING_MODEL"] = "text-embedding-3-small"
        os.environ["VOYAGE_API_KEY"] = "present"
        with self.assertRaises(RuntimeError) as caught:
            resolve_embedding()
        self.assertIn("will not be used as a fallback", str(caught.exception))

    def test_missing_voyage_key_does_not_imply_another_provider(self):
        os.environ.pop("EMBEDDING_PROVIDER", None)
        os.environ.pop("EMBEDDING_MODEL", None)
        os.environ.pop("VOYAGE_API_KEY", None)
        with self.assertRaises(RuntimeError) as caught:
            resolve_embedding()
        self.assertIn("will not switch", str(caught.exception))

    def test_default_is_voyage_3(self):
        os.environ.pop("EMBEDDING_PROVIDER", None)
        os.environ.pop("EMBEDDING_MODEL", None)
        os.environ["VOYAGE_API_KEY"] = "present"
        self.assertEqual(resolve_embedding(), ("voyage", "voyage-3"))
