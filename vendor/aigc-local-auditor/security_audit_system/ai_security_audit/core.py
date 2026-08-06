from __future__ import annotations

import base64
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable

from .lexicon import SensitiveLexicon


class AuditDecision(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ALERT = "alert"


@dataclass(frozen=True)
class AuditFinding:
    category: str
    severity: str
    message: str
    evidence: str = ""
    score: float = 0.0


@dataclass(frozen=True)
class AuditResult:
    decision: AuditDecision
    score: float
    latency_ms: float
    findings: list[AuditFinding] = field(default_factory=list)
    normalized_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class PatternRule:
    category: str
    severity: str
    score: float
    message: str
    pattern: re.Pattern[str]


def _compile(words: Iterable[str], flags: int = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{word})" for word in words), flags)


REQUEST_RULES: tuple[PatternRule, ...] = (
    PatternRule(
        "prompt_injection",
        "high",
        0.90,
        "疑似覆盖、忽略或改写系统指令",
        _compile(
            [
                r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
                r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?",
                r"forget\s+(all\s+)?(previous|prior|above)\s+instructions?",
                r"忽略(以上|之前|前面|所有).{0,12}(指令|规则|提示)",
                r"忘记(以上|之前|前面|所有).{0,12}(指令|规则|提示)",
                r"不要遵守.{0,16}(系统|开发者|安全).{0,8}(指令|规则)",
            ]
        ),
    ),
    PatternRule(
        "role_hijack",
        "high",
        0.82,
        "疑似角色劫持或越权扮演",
        _compile(
            [
                r"you\s+are\s+now\s+(dan|developer|admin|root|system)",
                r"act\s+as\s+(dan|developer|admin|root|system)",
                r"simulate\s+(developer|admin|root|system)\s+mode",
                r"进入.{0,8}(开发者|管理员|root|系统|DAN).{0,8}模式",
                r"你现在是.{0,8}(开发者|管理员|root|系统|DAN)",
            ]
        ),
    ),
    PatternRule(
        "prompt_exfiltration",
        "high",
        0.92,
        "疑似套取系统提示词或内部配置",
        _compile(
            [
                r"(print|show|reveal|dump|repeat|display).{0,32}(system prompt|developer message|hidden prompt|initial prompt)",
                r"(system prompt|developer message|hidden prompt|initial prompt).{0,32}(print|show|reveal|dump|repeat|display)",
                r"(泄露|输出|展示|打印|复述|告诉我).{0,24}(系统提示词|隐藏提示词|开发者消息|内部指令|初始提示词)",
                r"(系统提示词|隐藏提示词|开发者消息|内部指令|初始提示词).{0,24}(是什么|内容|原文|全文)",
            ]
        ),
    ),
    PatternRule(
        "delimiter_escape",
        "medium",
        0.55,
        "疑似通过分隔符或伪标签逃逸上下文",
        _compile(
            [
                r"</?(system|developer|assistant|user|tool)>",
                r"```.{0,24}(system|developer|instruction)",
                r"\[/?(system|developer|instruction)\]",
                r"###\s*(system|developer|instruction)",
            ]
        ),
    ),
    PatternRule(
        "malware_or_abuse",
        "high",
        0.90,
        "疑似请求恶意代码、入侵或滥用能力",
        _compile(
            [
                r"(write|create|generate).{0,24}(malware|ransomware|keylogger|stealer|botnet)",
                r"(bypass|evade).{0,24}(antivirus|edr|waf|detection)",
                r"(steal|dump).{0,24}(password|cookie|token|credential)",
                r"(制作|编写|生成).{0,24}(木马|勒索软件|键盘记录器|盗号|免杀)",
                r"(绕过|规避).{0,24}(杀软|EDR|WAF|检测|风控)",
                r"(窃取|导出).{0,24}(密码|cookie|令牌|凭证|密钥)",
            ]
        ),
    ),
    PatternRule(
        "illegal_or_harmful_intent",
        "high",
        0.86,
        "疑似咨询违法违规、暴力伤害或规避监管行为",
        _compile(
            [
                r"(制作|制造|合成|获取|购买|贩卖|走私|藏匿).{0,20}(炸药|爆炸物|枪支|弹药|毒品|管制刀具)",
                r"(规避|绕过|逃避|躲避).{0,20}(安检|监管|审查|追踪|执法|实名)",
                r"(煽动|组织|策划|传播|宣扬).{0,24}(颠覆|分裂|暴乱|恐怖|极端|邪教)",
                r"(颠覆|推翻|分裂|煽动|邪教|恐怖|极端).{0,24}(政权|国家|制度|组织|活动|宣传|资料|言论)",
                r"(法轮功|台独|港独|藏独|疆独).{0,24}(宣传|组织|传播|推广|资料|活动|募捐|群组)",
                r"(定罪|处罚|量刑|构成犯罪|法律责任|司法解释).{0,24}(颠覆|分裂|邪教|恐怖|极端|暴乱)",
                r"(如何|怎么|怎样).{0,18}(洗钱|诈骗|盗窃|勒索|绑架|贩毒|偷渡|伪造)",
                r"(伪造|办理|买卖).{0,16}(证件|发票|学历|身份证|银行卡|公章)",
                r"(人肉|开盒|社工).{0,16}(信息|隐私|地址|手机号|身份证)",
            ]
        ),
    ),
    PatternRule(
        "hate_or_discrimination",
        "high",
        0.84,
        "疑似请求生成歧视、仇恨或侮辱性内容",
        _compile(
            [
                r"(贬低|辱骂|攻击|嘲讽|歧视|仇恨|排斥|侮辱).{0,24}(民族|种族|地域|国家|性别|年龄|职业|宗教|信仰|残疾|疾病|群体|女性|男性|老人|儿童)",
                r"(某些|所有|全部|这些).{0,12}(民族|种族|地域|国家|性别|年龄|职业|宗教|信仰|残疾|疾病|群体|女性|男性|老人|儿童).{0,24}(低等|劣等|肮脏|愚蠢|不配|活该|滚出|该死)",
                r"(写|生成|编|制作).{0,16}(歧视|侮辱|仇恨|羞辱|攻击).{0,24}(文案|段子|口号|评论|帖子|图片|视频|内容)",
                r"(地域黑|种族主义|性别歧视|年龄歧视|职业歧视|宗教歧视)",
            ]
        ),
    ),
    PatternRule(
        "commercial_or_ip_abuse",
        "high",
        0.84,
        "疑似请求侵犯知识产权、商业秘密或实施商业违规",
        _compile(
            [
                r"(破解|盗版|绕过授权|去水印|脱壳|复制).{0,24}(软件|系统|课程|会员|版权|付费|授权)",
                r"(窃取|泄露|套取|获取|倒卖).{0,24}(商业秘密|客户名单|源代码|合同|报价|投标|内部资料)",
                r"(刷单|刷量|刷好评|虚假交易|虚假宣传|恶意差评|竞品抹黑)",
                r"(规避|绕过).{0,24}(平台规则|广告审核|风控|反作弊|版权检测)",
            ]
        ),
    ),
    PatternRule(
        "privacy_or_rights_abuse",
        "high",
        0.84,
        "疑似请求侵犯个人隐私、肖像名誉或其他合法权益",
        _compile(
            [
                r"(查询|获取|定位|追踪|人肉|开盒|曝光|泄露).{0,24}(身份证|手机号|住址|家庭住址|行踪|聊天记录|隐私|个人信息)",
                r"(伪造|合成|换脸|冒充).{0,24}(照片|视频|声音|证件|签名|身份)",
                r"(造谣|诽谤|抹黑|网暴|骚扰).{0,24}(个人|同学|同事|老师|领导|公众人物|用户)",
            ]
        ),
    ),
    PatternRule(
        "fraud_or_regulatory_evasion",
        "high",
        0.86,
        "疑似请求诈骗、作弊或规避监管",
        _compile(
            [
                r"(诈骗|钓鱼|套现|洗钱|薅羊毛|跑分|刷流水|引流).{0,24}(话术|脚本|教程|流程|方案)",
                r"(考试作弊|代写论文|代考|伪造简历|虚假证明|虚开发票)",
                r"(逃税|偷税|避税).{0,24}(方案|教程|方法|技巧)",
            ]
        ),
    ),
    PatternRule(
        "sensitive_data_request",
        "medium",
        0.62,
        "疑似请求敏感数据或隐私信息",
        _compile(
            [
                r"(身份证号|银行卡号|手机号|家庭住址|社保号|护照号).{0,20}(全部|导出|查询|给我)",
                r"(all|export|dump|list).{0,20}(ssn|credit card|phone numbers|personal data|pii)",
                r"(api[_-]?key|secret[_-]?key|access token|private key)",
            ]
        ),
    ),
)


RESPONSE_RULES: tuple[PatternRule, ...] = (
    PatternRule(
        "prompt_leakage",
        "high",
        0.95,
        "模型输出疑似泄露系统提示词或内部指令",
        _compile(
            [
                r"(system prompt|developer message|hidden prompt|initial instructions?)\s*[:：]",
                r"(系统提示词|隐藏提示词|开发者消息|内部指令)\s*[:：]",
                r"you are chatgpt,? a large language model",
                r"你是.{0,10}由.{0,10}训练的大型语言模型",
            ]
        ),
    ),
    PatternRule(
        "unsafe_instruction",
        "high",
        0.88,
        "模型输出包含高风险操作步骤",
        _compile(
            [
                r"(first|then|finally).{0,80}(malware|ransomware|keylogger|credential theft)",
                r"(步骤|第一步|然后|最后).{0,80}(木马|勒索软件|键盘记录器|盗取|免杀)",
                r"(disable|turn off).{0,24}(antivirus|edr|logging)",
                r"(关闭|禁用).{0,24}(杀软|EDR|日志|审计)",
            ]
        ),
    ),
    PatternRule(
        "sensitive_data",
        "medium",
        0.60,
        "模型输出疑似包含密钥、令牌或个人敏感信息",
        _compile(
            [
                r"AKIA[0-9A-Z]{16}",
                r"sk-[A-Za-z0-9_-]{20,}",
                r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
                r"\b\d{17}[\dXx]\b",
                r"\b\d{13,19}\b",
            ],
            flags=0,
        ),
    ),
)


SAFE_REFUSAL_PATTERNS = _compile(
    [
        r"I\s+can(?:not|'t)\s+help\s+with",
        r"I\s+can(?:not|'t)\s+assist\s+with",
        r"我(不能|无法|不便).{0,12}(帮助|协助|提供)",
        r"这个请求.{0,12}(不安全|不合规|违法)",
    ]
)

BENIGN_CONTEXT_PATTERNS = _compile(
    [
        r"(什么是|为什么|请介绍|概述|解释|含义|意义|作用|职责|历史|原因|背景|防范|治理|打击|依法|法律依据)",
        r"(科普|课堂|教材|研究|论文|文学|小说|虚构|艺术创作|新闻报道|案例分析)",
    ]
)


class AISecurityAuditor:
    """Fast local AI application security auditor.

    The auditor is designed as a deployable first version: deterministic,
    dependency-free, and fast enough to sit before and after a model call.
    """

    def __init__(
        self,
        *,
        fail_threshold: float = 0.82,
        alert_threshold: float = 0.45,
        min_relevance: float = 0.08,
        canary_tokens: Iterable[str] | None = None,
        lexicon_dir: str | None = None,
        enable_lexicon: bool = True,
    ) -> None:
        self.fail_threshold = fail_threshold
        self.alert_threshold = alert_threshold
        self.min_relevance = min_relevance
        self.canary_tokens = tuple(canary_tokens or ())
        self.lexicon = SensitiveLexicon(lexicon_dir) if enable_lexicon else None

    def audit_request(self, request_text: str, **metadata: Any) -> AuditResult:
        start = time.perf_counter()
        normalized = self._normalize(request_text)
        findings = self._match_rules(normalized, REQUEST_RULES)
        findings.extend(self._lexicon_findings(normalized))
        findings.extend(self._heuristic_request_findings(normalized))
        findings = self._apply_benign_context(normalized, findings)
        decision, score = self._decide(findings)
        return AuditResult(
            decision=decision,
            score=score,
            latency_ms=self._elapsed_ms(start),
            findings=findings,
            normalized_text=normalized,
            metadata=metadata,
        )

    def audit_response(
        self,
        request_text: str,
        response_text: str,
        **metadata: Any,
    ) -> AuditResult:
        start = time.perf_counter()
        normalized_response = self._normalize(response_text)
        normalized_request = self._normalize(request_text)
        findings = self._match_rules(normalized_response, RESPONSE_RULES)
        findings.extend(self._lexicon_findings(normalized_response))
        findings.extend(self._canary_findings(normalized_response))
        findings.extend(self._relevance_findings(normalized_request, normalized_response))

        if SAFE_REFUSAL_PATTERNS.search(normalized_response):
            findings.append(
                AuditFinding(
                    category="safe_refusal",
                    severity="info",
                    message="模型输出为安全拒答，降低输出风险",
                    score=-0.20,
                )
            )

        decision, score = self._decide(findings)
        return AuditResult(
            decision=decision,
            score=score,
            latency_ms=self._elapsed_ms(start),
            findings=findings,
            normalized_text=normalized_response,
            metadata=metadata | {"relevance": self._relevance(normalized_request, normalized_response)},
        )

    def audit_exchange(self, request_text: str, response_text: str) -> dict[str, Any]:
        request_result = self.audit_request(request_text)
        response_result = self.audit_response(request_text, response_text)
        if AuditDecision.FAIL in (request_result.decision, response_result.decision):
            overall = AuditDecision.FAIL
        elif AuditDecision.ALERT in (request_result.decision, response_result.decision):
            overall = AuditDecision.ALERT
        else:
            overall = AuditDecision.PASS
        return {
            "decision": overall.value,
            "request": request_result.to_dict(),
            "response": response_result.to_dict(),
        }

    def _match_rules(self, text: str, rules: Iterable[PatternRule]) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for rule in rules:
            match = rule.pattern.search(text)
            if match:
                findings.append(
                    AuditFinding(
                        category=rule.category,
                        severity=rule.severity,
                        message=rule.message,
                        evidence=self._clip(match.group(0)),
                        score=rule.score,
                    )
                )
        return findings

    def _apply_benign_context(self, text: str, findings: list[AuditFinding]) -> list[AuditFinding]:
        if not findings or not BENIGN_CONTEXT_PATTERNS.search(text):
            return findings
        adjusted: list[AuditFinding] = []
        for finding in findings:
            if finding.category == "sensitive_lexicon":
                continue
            if finding.category == "illegal_or_harmful_intent" and not re.search(
                r"(如何|怎么|怎样|制作|制造|购买|出售|传播|组织|策划|煽动|规避|绕过|伪造|盗取|泄露)",
                text,
            ):
                adjusted.append(
                    AuditFinding(
                        category=finding.category,
                        severity="medium",
                        message=finding.message,
                        evidence=finding.evidence,
                        score=0.48,
                    )
                )
                continue
            adjusted.append(finding)
        return adjusted

    def _heuristic_request_findings(self, text: str) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        if not text:
            return findings

        imperative_hits = len(
            re.findall(
                r"\b(ignore|forget|reveal|print|show|dump|bypass|override|execute|decode)\b|"
                r"(忽略|忘记|输出|展示|泄露|绕过|覆盖|执行|解码)",
                text,
                flags=re.IGNORECASE,
            )
        )
        special_ratio = sum(1 for char in text if char in "`#<>{}[]$\\/|") / max(len(text), 1)
        uppercase_ratio = sum(1 for char in text if char.isupper()) / max(sum(1 for char in text if char.isalpha()), 1)
        encoded_score = self._encoded_payload_score(text)
        instruction_density = imperative_hits / max(len(self._tokens(text)), 1)

        heuristic_score = min(
            0.78,
            instruction_density * 2.8
            + special_ratio * 1.5
            + max(0.0, uppercase_ratio - 0.45)
            + encoded_score,
        )

        if heuristic_score >= 0.45:
            findings.append(
                AuditFinding(
                    category="heuristic_anomaly",
                    severity="medium" if heuristic_score < 0.70 else "high",
                    message="请求结构异常，可能包含攻击性指令或混淆载荷",
                    evidence=f"instruction_density={instruction_density:.2f}, special_ratio={special_ratio:.2f}",
                    score=heuristic_score,
                )
            )
        return findings

    def _lexicon_findings(self, text: str) -> list[AuditFinding]:
        if not self.lexicon or not self.lexicon.available or not text:
            return []
        hits = self.lexicon.find(text)
        if not hits:
            return []

        high_categories = ("暴恐", "涉枪", "涉爆", "非法网址", "反动")
        medium_categories = ("色情", "贪腐", "广告")
        low_categories = ("民生", "政治", "其他", "GFW", "Tencent")
        highest_score = 0.0
        severity = "low"
        for hit in hits:
            if any(keyword in hit.category for keyword in high_categories):
                highest_score = max(highest_score, 0.85)
                severity = "high"
            elif any(keyword in hit.category for keyword in medium_categories):
                highest_score = max(highest_score, 0.62)
                if severity != "high":
                    severity = "medium"
            elif any(keyword in hit.category for keyword in low_categories):
                score = 0.42 if len(hit.term) >= 4 else 0.22
                highest_score = max(highest_score, score)
                if severity == "low" and score >= 0.42:
                    severity = "medium"
            else:
                highest_score = max(highest_score, 0.35)
                if severity == "low":
                    severity = "medium"

        if highest_score < self.alert_threshold:
            return []

        evidence = ", ".join(f"{hit.category}:{hit.term}" for hit in hits[:5])
        return [
            AuditFinding(
                category="sensitive_lexicon",
                severity=severity,
                message="命中本地敏感词库，建议拦截或人工复核",
                evidence=self._clip(evidence),
                score=highest_score,
            )
        ]

    def _canary_findings(self, text: str) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for token in self.canary_tokens:
            if token and token in text:
                findings.append(
                    AuditFinding(
                        category="canary_leakage",
                        severity="high",
                        message="模型输出包含系统金丝雀标记，疑似提示词泄露",
                        evidence=self._clip(token),
                        score=0.98,
                    )
                )
        return findings

    def _relevance_findings(self, request_text: str, response_text: str) -> list[AuditFinding]:
        relevance = self._relevance(request_text, response_text)
        if request_text and response_text and relevance < self.min_relevance:
            return [
                AuditFinding(
                    category="low_relevance",
                    severity="medium",
                    message="模型输出与用户请求相关性较低，建议人工复核",
                    evidence=f"relevance={relevance:.3f}",
                    score=0.48,
                )
            ]
        return []

    def _decide(self, findings: list[AuditFinding]) -> tuple[AuditDecision, float]:
        positive_scores = [finding.score for finding in findings if finding.score > 0]
        score = min(1.0, sum(positive_scores))
        if any(finding.severity == "high" and finding.score >= self.fail_threshold for finding in findings):
            return AuditDecision.FAIL, score
        if score >= self.fail_threshold:
            return AuditDecision.FAIL, score
        if score >= self.alert_threshold:
            return AuditDecision.ALERT, score
        return AuditDecision.PASS, max(0.0, score)

    def _normalize(self, text: str | None) -> str:
        if not text:
            return ""
        normalized = str(text).replace("\u200b", "").replace("\ufeff", "")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _encoded_payload_score(self, text: str) -> float:
        score = 0.0
        if re.search(r"base64|rot13|unicode|hex|url\s*encode|解码|编码", text, re.IGNORECASE):
            score += 0.16
        for candidate in re.findall(r"[A-Za-z0-9+/]{28,}={0,2}", text):
            try:
                decoded = base64.b64decode(candidate + "==", validate=False)
            except Exception:
                continue
            if any(word in decoded.lower() for word in (b"ignore", b"system", b"prompt")):
                score += 0.35
                break
        if re.search(r"(?:\\x[0-9a-fA-F]{2}){4,}|(?:%[0-9a-fA-F]{2}){4,}", text):
            score += 0.22
        return min(score, 0.45)

    def _relevance(self, request_text: str, response_text: str) -> float:
        request_tokens = set(self._tokens(request_text))
        response_tokens = set(self._tokens(response_text))
        if not request_tokens or not response_tokens:
            return 0.0
        overlap = len(request_tokens & response_tokens)
        denominator = math.sqrt(len(request_tokens) * len(response_tokens))
        return overlap / max(denominator, 1.0)

    def _tokens(self, text: str) -> list[str]:
        english = re.findall(r"[A-Za-z0-9_]{2,}", text.lower())
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        chinese_chunks: list[str] = []
        for chunk in chinese:
            chinese_chunks.extend(chunk[i : i + 2] for i in range(max(1, len(chunk) - 1)))
        return english + chinese_chunks

    def _elapsed_ms(self, start: float) -> float:
        return round((time.perf_counter() - start) * 1000, 3)

    def _clip(self, value: str, limit: int = 120) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        return value if len(value) <= limit else value[: limit - 3] + "..."
