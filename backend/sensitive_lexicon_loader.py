"""
Sensitive-lexicon 词库加载器
从 Sensitive-lexicon 仓库加载敏感词库
"""

import os
from typing import Dict, List, Set


class SensitiveLexiconLoader:
    """Sensitive-lexicon 词库加载器"""

    def __init__(self, lexicon_dir: str = "Sensitive-lexicon/Vocabulary"):
        """
        初始化加载器

        Args:
            lexicon_dir: 词库目录路径
        """
        self.lexicon_dir = lexicon_dir

        # 词库文件映射到内容过滤器的分类
        self.file_category_mapping = {
            # 政治敏感
            "political": [
                "政治类型.txt",
                "反动词库.txt",
                "民生词库.txt",
                "贪腐词库.txt",
                "新思想启蒙.txt",
                "GFW补充词库.txt"
            ],

            # 色情内容
            "sexual": [
                "色情词库.txt",
                "色情类型.txt"
            ],

            # 暴力/恐怖
            "violence": [
                "暴恐词库.txt",
                "涉枪涉爆.txt"
            ],

            # 违法犯罪
            "illegal": [
                "非法网址.txt"
            ],

            # 垃圾信息
            "spam": [
                "广告类型.txt"
            ],

            # 其他
            "other": [
                "补充词库.txt",
                "其他词库.txt",
                "COVID-19词库.txt",
                "网易前端过滤敏感词库.txt",
                "零时-Tencent.txt"
            ]
        }

    def load_file(self, file_path: str) -> Set[str]:
        """
        加载单个词库文件

        Args:
            file_path: 文件路径

        Returns:
            关键词集合
        """
        keywords = set()

        if not os.path.exists(file_path):
            return keywords

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    keyword = line.strip()
                    if keyword and not keyword.startswith("#"):
                        keywords.add(keyword)
        except Exception as e:
            print(f"加载文件失败 {file_path}: {e}")

        return keywords

    def load_category(self, category: str) -> Set[str]:
        """
        加载指定分类的所有词库

        Args:
            category: 分类名称

        Returns:
            该分类的所有关键词集合
        """
        keywords = set()

        if category not in self.file_category_mapping:
            return keywords

        for filename in self.file_category_mapping[category]:
            file_path = os.path.join(self.lexicon_dir, filename)
            keywords.update(self.load_file(file_path))

        return keywords

    def load_all(self) -> Dict[str, List[str]]:
        """
        加载所有词库

        Returns:
            按分类组织的关键词字典
        """
        all_keywords = {}

        for category in self.file_category_mapping.keys():
            keywords = self.load_category(category)
            if keywords:
                all_keywords[category] = list(keywords)
                print(f"加载 {category} 分类: {len(keywords)} 个关键词")

        return all_keywords
