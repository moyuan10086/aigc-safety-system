import unittest
from unittest.mock import patch

from services import kb_service
from services.official_knowledge_sources import OFFICIAL_KNOWLEDGE_SOURCES


class FakeEmbedder:
    def encode(self, documents, normalize_embeddings=True):
        class Encoded(list):
            def tolist(self):
                return list(self)
        return Encoded([[0.1, 0.2] for _ in documents])


class FakeCollection:
    def __init__(self):
        self.rows = {
            "user-file:0": {
                "document": "用户自己的资料",
                "metadata": {
                    "file_id": "user-file", "filename": "user.txt",
                    "category": "用户资料", "chunk_index": 0,
                },
            }
        }

    def get(self, where=None, include=None):
        items = list(self.rows.items())
        if where:
            items = [item for item in items if all(item[1]["metadata"].get(k) == v for k, v in where.items())]
        return {
            "ids": [item[0] for item in items],
            "documents": [item[1]["document"] for item in items],
            "metadatas": [item[1]["metadata"] for item in items],
        }

    def add(self, ids, documents, metadatas, embeddings):
        for row_id, document, metadata in zip(ids, documents, metadatas):
            self.rows[row_id] = {"document": document, "metadata": metadata}

    def delete(self, ids):
        for row_id in ids:
            self.rows.pop(row_id, None)


class OfficialKnowledgeSourceTests(unittest.TestCase):
    def test_source_ids_and_urls_are_unique_and_stable(self):
        ids = [source["source_id"] for source in OFFICIAL_KNOWLEDGE_SOURCES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(source["source_url"].startswith("https://") for source in OFFICIAL_KNOWLEDGE_SOURCES))

    def test_seed_is_idempotent_and_preserves_user_documents(self):
        collection = FakeCollection()
        with patch.object(kb_service, "_init"), \
                patch.object(kb_service, "_collection", collection), \
                patch.object(kb_service, "_embedder", FakeEmbedder()):
            first = kb_service.seed_official_sources()
            second = kb_service.seed_official_sources()
        self.assertEqual(first["added_sources"], len(OFFICIAL_KNOWLEDGE_SOURCES))
        self.assertEqual(second["added_sources"], 0)
        self.assertEqual(second["skipped_sources"], len(OFFICIAL_KNOWLEDGE_SOURCES))
        self.assertIn("user-file:0", collection.rows)

    def test_list_files_exposes_source_metadata_and_chunk_count(self):
        collection = FakeCollection()
        source = OFFICIAL_KNOWLEDGE_SOURCES[0]
        collection.add(
            ids=["official:0", "official:1"],
            documents=["a", "b"], embeddings=[[0], [0]],
            metadatas=[kb_service._source_metadata(source, 0), kb_service._source_metadata(source, 1)],
        )
        with patch.object(kb_service, "_init"), patch.object(kb_service, "_collection", collection):
            files = kb_service.list_files(source["category"])
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["publisher"], source["publisher"])
        self.assertEqual(files[0]["source_url"], source["source_url"])
        self.assertEqual(files[0]["chunk_count"], 2)

    def test_managed_source_cannot_be_deleted(self):
        collection = FakeCollection()
        source = OFFICIAL_KNOWLEDGE_SOURCES[0]
        collection.add(
            ids=["official:0"], documents=["a"], embeddings=[[0]],
            metadatas=[kb_service._source_metadata(source, 0)],
        )
        with patch.object(kb_service, "_init"), patch.object(kb_service, "_collection", collection):
            self.assertFalse(kb_service.delete_file(f"official:{source['source_id']}"))
        self.assertIn("official:0", collection.rows)


if __name__ == "__main__":
    unittest.main()
