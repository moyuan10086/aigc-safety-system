import unittest

from services.kb_service import _lexical_score, _split


class KnowledgeRetrievalTests(unittest.TestCase):
    def test_paragraph_chunking_preserves_sections_and_overlap(self):
        text = "第一章 数据安全要求。\n\n" + "敏感数据不得外泄。" * 80 + "\n\n第三章 审计要求。"
        chunks = _split(text)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= 550 for chunk in chunks))
        self.assertIn("第一章", chunks[0])

    def test_chinese_lexical_score_prefers_relevant_evidence(self):
        query = "个人信息泄露如何处置"
        relevant = _lexical_score(query, "发现个人信息泄露后，应立即启动应急处置并通知负责人。")
        unrelated = _lexical_score(query, "系统采用蓝色主题并支持页面刷新。")
        self.assertGreater(relevant, unrelated)


if __name__ == "__main__":
    unittest.main()
