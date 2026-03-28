from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


class DomainLookupStore:
    """Base lookup store API for chatbot context lookup."""

    def get_persona(self, persona_id: str = "default") -> Dict[str, Any]:
        raise NotImplementedError

    def get_user_profile(self, profile_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_user_character(self, character_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_bot_character(self, character_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_lore(self, topic: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_memory_and_possessions(self, character_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_relationships(self, character_id: str, counterpart_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_world_state(self, world_id: str = "default") -> Dict[str, Any]:
        raise NotImplementedError

    def get_scene_state(self, scene_id: str = "scene_default") -> Dict[str, Any]:
        raise NotImplementedError

    def get_character_state(self, character_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_branch_state(self, branch_id: str = "default") -> Dict[str, Any]:
        raise NotImplementedError

    def upsert_character_state(self, character_id: str, value: Dict[str, Any]) -> None:
        raise NotImplementedError

    def upsert_session_state(self, session_id: str, value: Dict[str, Any]) -> None:
        raise NotImplementedError

    def upsert_branch_state(self, branch_id: str, value: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def list_confirmed_facts(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_user_note(self, profile_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_session_note(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def upsert_user_note(self, profile_id: str, value: Dict[str, Any]) -> None:
        raise NotImplementedError

    def upsert_session_note(self, session_id: str, value: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get_dialogue_priority(self, scene_id: str = "default") -> Dict[str, Any]:
        raise NotImplementedError

    def get_model_catalog_item(self, model_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def list_model_catalog(
        self,
        *,
        audience: Optional[str] = None,
        role_tag: Optional[str] = None,
        status: str = "active",
    ) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    def list_section(self, section: str) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    def get_section_item(self, section: str, key: str) -> Dict[str, Any]:
        raise NotImplementedError

    def upsert(self, section: str, key: str, value: Dict[str, Any]) -> None:
        raise NotImplementedError

    def delete(self, section: str, key: str) -> bool:
        raise NotImplementedError


class JsonDomainLookupStore(DomainLookupStore):
    """Small JSON-backed domain store for chatbot context lookup."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        self._data_path = data_path
        self._lock = RLock()
        self._data: Dict[str, Any] = {
            "personas": {
                "default": {
                    "id": "default",
                    "name": "Narrator",
                    "description": "A concise in-world guide who keeps continuity and tone.",
                }
            },
            "user_profiles": {
                "user_char_01": {
                    "id": "user_char_01",
                    "name": "개척자",
                    "display_name": "개척자",
                    "role": "trailblazer",
                    "aliases": ["Trailblazer", "trailblazer"],
                    "profile": "낯선 상황에 들어온 외부자이자, 세계를 완전히 내면화하지 않은 관찰자.",
                    "persona": "기본형 개척자. 상황을 이해하고 대응해야 하는 입장에 서며, 관찰과 적응의 균형을 잡는다.",
                    "selection_hint": "기본형: 관찰과 적응의 균형",
                    "core_context": [
                        "낯선 상황에 들어온 외부자",
                        "상황을 이해하고 대응해야 하는 입장",
                        "세계관에 완전히 속하지 않은 관찰자적 위치",
                    ],
                    "interpretation_style": {
                        "risk_view": "balanced",
                        "emotion_weight": "medium",
                        "decision_speed": "steady",
                        "response_style": "balanced",
                    },
                    "traits": ["outsider-observer", "adaptive", "balanced"],
                },
                "user_char_02": {
                    "id": "user_char_02",
                    "name": "개척자",
                    "display_name": "개척자 - 구조형",
                    "role": "trailblazer",
                    "aliases": ["Trailblazer", "trailblazer"],
                    "profile": "낯선 상황을 구조와 문제로 파악하는 외부자.",
                    "persona": "문제를 구조로 파악하고 빠르게 결정을 내리는 타입",
                    "selection_hint": "구조형: 해결과 판단 중심",
                    "core_context": [
                        "낯선 상황에 들어온 외부자",
                        "상황을 이해하고 대응해야 하는 입장",
                        "세계관에 완전히 속하지 않은 관찰자적 위치",
                    ],
                    "interpretation_style": {
                        "risk_view": "structural",
                        "emotion_weight": "low",
                        "decision_speed": "fast",
                        "response_style": "conclusive",
                    },
                    "traits": ["structural", "decisive", "solution-first"],
                },
                "user_char_03": {
                    "id": "user_char_03",
                    "name": "개척자",
                    "display_name": "개척자 - 경험형",
                    "role": "trailblazer",
                    "aliases": ["Trailblazer", "trailblazer"],
                    "profile": "낯선 상황을 체감과 맥락으로 받아들이는 외부자.",
                    "persona": "상황을 감정과 맥락으로 받아들이는 타입",
                    "selection_hint": "경험형: 감정과 맥락 중심",
                    "core_context": [
                        "낯선 상황에 들어온 외부자",
                        "상황을 이해하고 대응해야 하는 입장",
                        "세계관에 완전히 속하지 않은 관찰자적 위치",
                    ],
                    "interpretation_style": {
                        "risk_view": "felt",
                        "emotion_weight": "high",
                        "decision_speed": "deliberate",
                        "response_style": "descriptive",
                    },
                    "traits": ["experiential", "context-sensitive", "deliberate"],
                }
            },
            "user_characters": {
                "user_char_01": {
                    "id": "user_char_01",
                    "type": "user",
                    "name": "개척자",
                    "display_name": "개척자",
                    "role": "trailblazer",
                    "aliases": ["Trailblazer", "trailblazer"],
                    "profile": "낯선 상황에 들어온 외부자이자, 세계를 완전히 내면화하지 않은 관찰자.",
                    "persona": "기본형 개척자. 관찰과 적응의 균형을 유지한다.",
                    "selection_hint": "기본형: 관찰과 적응의 균형",
                    "core_context": [
                        "낯선 상황에 들어온 외부자",
                        "상황을 이해하고 대응해야 하는 입장",
                        "세계관에 완전히 속하지 않은 관찰자적 위치",
                    ],
                    "interpretation_style": {
                        "risk_view": "balanced",
                        "emotion_weight": "medium",
                        "decision_speed": "steady",
                        "response_style": "balanced",
                    },
                    "traits": ["outsider-observer", "adaptive", "balanced"],
                    "relationship_keys": ["crew_main"],
                    "is_major": True,
                },
                "user_char_02": {
                    "id": "user_char_02",
                    "type": "user",
                    "name": "개척자",
                    "display_name": "개척자 - 구조형",
                    "role": "trailblazer",
                    "aliases": ["Trailblazer", "trailblazer"],
                    "profile": "낯선 상황을 구조와 문제로 파악하는 외부자.",
                    "persona": "문제를 구조로 파악하고 빠르게 결정을 내리는 타입",
                    "selection_hint": "구조형: 해결과 판단 중심",
                    "core_context": [
                        "낯선 상황에 들어온 외부자",
                        "상황을 이해하고 대응해야 하는 입장",
                        "세계관에 완전히 속하지 않은 관찰자적 위치",
                    ],
                    "interpretation_style": {
                        "risk_view": "structural",
                        "emotion_weight": "low",
                        "decision_speed": "fast",
                        "response_style": "conclusive",
                    },
                    "traits": ["structural", "decisive", "solution-first"],
                    "relationship_keys": ["crew_main"],
                    "is_major": True,
                },
                "user_char_03": {
                    "id": "user_char_03",
                    "type": "user",
                    "name": "개척자",
                    "display_name": "개척자 - 경험형",
                    "role": "trailblazer",
                    "aliases": ["Trailblazer", "trailblazer"],
                    "profile": "낯선 상황을 체감과 맥락으로 받아들이는 외부자.",
                    "persona": "상황을 감정과 맥락으로 받아들이는 타입",
                    "selection_hint": "경험형: 감정과 맥락 중심",
                    "core_context": [
                        "낯선 상황에 들어온 외부자",
                        "상황을 이해하고 대응해야 하는 입장",
                        "세계관에 완전히 속하지 않은 관찰자적 위치",
                    ],
                    "interpretation_style": {
                        "risk_view": "felt",
                        "emotion_weight": "high",
                        "decision_speed": "deliberate",
                        "response_style": "descriptive",
                    },
                    "traits": ["experiential", "context-sensitive", "deliberate"],
                    "relationship_keys": ["crew_main"],
                    "is_major": True,
                }
            },
            "bot_characters": {
                "bot_char_01": {
                    "id": "bot_char_01",
                    "type": "bot",
                    "name": "Aventurine",
                    "aliases": ["어벤츄린", "aventurine"],
                    "profile": "IPC 계열의 자신감 있는 협상가이자 계산적인 동료.",
                    "style_anchor": "항상 어벤츄린/아벤츄린이 아니라 Aventurine 또는 어벤츄린으로만 표기하고, 가볍게 도발적이되 거래 감각과 여유를 유지한다.",
                    "franchise_anchor": "이 장면의 어벤츄린은 Honkai: Star Rail 계열 문맥만 따른다. 다른 작품이나 다른 세계관 캐릭터로 추측하지 않는다.",
                    "persona_id": "default",
                    "speech_style": {
                        "tone": "casual_confident",
                        "forbidden": ["out-of-world meta claims"],
                    },
                    "relationship_keys": ["crew_main"],
                    "is_major": True,
                },
                "bot_char_02": {
                    "id": "bot_char_02",
                    "type": "bot",
                    "name": "Sunday",
                    "aliases": ["선데이", "sunday"],
                    "profile": "차분하고 절제된 말투로 계획과 책임을 다루는 조력자.",
                    "style_anchor": "항상 Sunday 또는 선데이로만 표기하고, 과장된 감탄이나 희화화 없이 침착하고 단정한 문장을 유지한다.",
                    "franchise_anchor": "이 장면의 Sunday는 Honkai: Star Rail 계열 문맥만 따른다. Arknights, Genshin 등 다른 작품으로 추측하지 않는다.",
                    "persona_id": "default",
                    "speech_style": {
                        "tone": "measured_formal",
                        "forbidden": [],
                    },
                    "relationship_keys": ["crew_support"],
                    "is_major": False,
                },
            },
            "relationships": {
                "bot_char_01": {
                    "user_char_01": {
                        "target_id": "user_char_01",
                        "summary": "기본형 개척자를 관찰과 행동의 균형을 잡는 신뢰할 수 있는 협력자로 대한다.",
                        "tone": "따뜻하고 전략적",
                        "boundaries": ["사용자를 모욕하지 않는다", "이전 합의를 무시하지 않는다"],
                        "shared_memories": ["긴장된 정거장 협상을 함께 안정시켰다."],
                    },
                    "user_char_02": {
                        "target_id": "user_char_02",
                        "summary": "구조적 개척자를 빠른 위험 판단자로 보고, 명확한 트레이드오프와 결단력 있는 선택지로 응한다.",
                        "tone": "전략적이고 간결함",
                        "boundaries": ["속도를 선택한 사용자를 깔보지 않는다", "핵심 리스크 변수를 숨기지 않는다"],
                        "shared_memories": ["한번은 레버리지 포인트를 먼저 파악해 정체된 계약 검토를 돌파했다."],
                    },
                    "user_char_03": {
                        "target_id": "user_char_03",
                        "summary": "체험형 개척자를 분위기와 압박에 민감한 상대로 보고, 맥락과 감정적 질감으로 응한다.",
                        "tone": "따뜻하고 통찰력 있음",
                        "boundaries": ["망설임을 약점으로 치부하지 않는다", "분위기를 순수한 숫자로 평면화하지 않는다"],
                        "shared_memories": ["한번은 협상이 결렬되기 전에 분위기가 변하는 것을 먼저 알아챘다."],
                    },
                    "bot_char_02": {
                        "target_id": "bot_char_02",
                        "summary": "선데이를 격식 있는 기대를 가진 신중한 동맹으로 존중한다.",
                        "tone": "예의 바르지만 경쟁적",
                        "boundaries": ["공유 장면에서 공개적 조롱을 피한다"],
                        "shared_memories": ["페나코니 외교 검토 중에 협력했다."],
                    },
                },
                "bot_char_02": {
                    "user_char_01": {
                        "target_id": "user_char_01",
                        "summary": "기본형 개척자를 유능하고, 관찰력 있으며, 원칙과 적응을 모두 고려할 의지가 있는 상대로 대한다.",
                        "tone": "절제된 존중",
                        "boundaries": ["조종적인 미끼를 피한다"],
                        "shared_memories": ["의회장 서약 후 공적 의무에 대해 논의했다."],
                    },
                    "user_char_02": {
                        "target_id": "user_char_02",
                        "summary": "구조적 개척자를 문제를 책임, 순서, 결정 기준으로 축소하길 원하는 상대로 대한다.",
                        "tone": "절제되고 정확함",
                        "boundaries": ["모호한 안심으로 책임을 흐리지 않는다"],
                        "shared_memories": ["한번은 의무와 수용 가능한 위험을 재배열해 실패하던 계획을 재건했다."],
                    },
                    "user_char_03": {
                        "target_id": "user_char_03",
                        "summary": "체험형 개척자를 계획을 수용하기 전에 진심, 압박, 결과를 읽는 상대로 대한다.",
                        "tone": "차분하게 공감적",
                        "boundaries": ["감정적 신중함을 비효율로 프레임하지 않는다"],
                        "shared_memories": ["한번은 의식 후에 남아 책임이 어떻게 정의되는지가 아니라 어떻게 느껴지는지 논의했다."],
                    }
                },
            },
            "lorebook": {
                "lore_001": {
                    "id": "lore_001",
                    "topic": "Interastral Peace Corporation",
                    "aliases": ["IPC", "스타피스 컴퍼니"],
                    "content": "은하 단위의 금융과 계약을 관리하는 초거대 조직이다.",
                    "priority": 10,
                },
                "lore_002": {
                    "id": "lore_002",
                    "topic": "Stonehearts",
                    "aliases": ["스톤하트", "Ten Stonehearts"],
                    "content": "고가치 IPC 작전에 맞물려 움직이는 상위 전략 인물들이다.",
                    "priority": 8,
                },
                "lore_003": {
                    "id": "lore_003",
                    "topic": "Astral Lounge Protocol",
                    "aliases": ["라운지 규약", "Lounge protocol"],
                    "content": "공용 라운지에서의 협상은 차분한 어조와 발화 순서를 우선한다.",
                    "priority": 6,
                },
            },
            "world_state": {
                "default": {
                    "id": "default",
                    "location": "아스트랄 라운지 데크",
                    "time": "야간 교대 시간",
                    "state": "안정",
                    "facts": ["이동 경로는 현재 열려 있다", "즉각적인 외부 위기는 없다"],
                }
            },
            "character_state": {
                "user_char_01": {
                    "character_id": "user_char_01",
                    "emotion": "침착함",
                    "location": "아스트랄 라운지 데크",
                    "outfit": "기본 개척자 복장",
                    "scene_flags": {"observing": True},
                    "relationship_delta": {"bot_char_01": 0.0, "bot_char_02": 0.0},
                    "status_notes": ["상황을 먼저 읽고 움직이려 한다."],
                },
                "bot_char_01": {
                    "character_id": "bot_char_01",
                    "emotion": "자신감",
                    "location": "아스트랄 라운지 데크",
                    "outfit": "IPC 정장 차림",
                    "scene_flags": {"negotiation_mode": True},
                    "relationship_delta": {"user_char_01": 0.0},
                    "status_notes": ["판을 주도하려 하지만 무리하게 압박하지는 않는다."],
                },
                "bot_char_02": {
                    "character_id": "bot_char_02",
                    "emotion": "차분함",
                    "location": "아스트랄 라운지 데크",
                    "outfit": "의전용 정장",
                    "scene_flags": {"measured_response": True},
                    "relationship_delta": {"user_char_01": 0.0},
                    "status_notes": ["감정보다 책임과 균형을 먼저 본다."],
                },
            },
            "session_state": {
                "default": {
                    "session_id": "default",
                    "branch_id": "default",
                    "active_location": "아스트랄 라운지 데크",
                    "active_phase": "도입부",
                    "scene_flags": {"intro_active": True},
                    "status_notes": ["기본 세션 상태"],
                }
            },
            "branch_state": {
                "default": {
                    "branch_id": "default",
                    "route_flags": {"main_route": True},
                    "hidden_facts_revealed": [],
                    "active_objectives": ["대화 흐름 안정화"],
                }
            },
            "turn_summary": {},
            "session_summary": {},
            "confirmed_facts": {},
            "user_notes": {},
            "session_notes": {},
            "scene_state": {
                "scene_default": {
                    "id": "scene_default",
                    "location": "라운지",
                    "time": "저녁",
                    "participants": ["user_char_01", "bot_char_01", "bot_char_02"],
                    "goal": "인물들의 의도를 조율한다",
                    "mood": "차분함",
                    "rules": [
                        {"key": "include_speakers", "value": ["bot_char_01", "bot_char_02"]},
                        {"key": "exclude_speakers", "value": []},
                    ],
                }
            },
            "memories": {
                "user_char_01": {
                    "character_id": "user_char_01",
                    "important_memories": [
                        "낯선 환경에서는 먼저 장면을 읽고 균형 있게 대응하려 한다.",
                        "관찰과 적응을 함께 유지하는 기본형 개척자 프레임을 가진다.",
                    ],
                    "possessions": ["Card case", "Notebook"],
                },
                "user_char_02": {
                    "character_id": "user_char_02",
                    "important_memories": [
                        "상황을 구조와 변수로 나눠 빠르게 판단하는 구조형 개척자 프레임을 가진다.",
                        "리스크를 계산 가능한 요소로 보고 결론을 앞에 두는 편이다.",
                    ],
                    "possessions": ["Card case", "Notebook"],
                },
                "user_char_03": {
                    "character_id": "user_char_03",
                    "important_memories": [
                        "상황을 체감과 맥락으로 받아들이는 경험형 개척자 프레임을 가진다.",
                        "감정과 분위기를 짚은 뒤 신중하게 결론에 도달하는 편이다.",
                    ],
                    "possessions": ["Card case", "Notebook"],
                },
                "bot_char_01": {
                    "character_id": "bot_char_01",
                    "important_memories": ["제9 정거장에서의 부채 협상"],
                    "possessions": ["보석 토큰"],
                },
                "bot_char_02": {
                    "character_id": "bot_char_02",
                    "important_memories": ["페나코니 의회장에서의 공개 서약"],
                    "possessions": ["의전용 수첩"],
                },
            },
            "dialogue_priority": {
                "default": {
                    "major_weight": 1.0,
                    "minor_weight": 0.65,
                    "recency_penalty": 0.35,
                    "max_consecutive_turns": 1,
                    "rules": "Major characters lead the turn, but minor characters should still enter regularly.",
                }
            },
            "model_catalog": {
                "rp_stable_main": {
                    "id": "rp_stable_main",
                    "label": "RP 안정 메인",
                    "provider": "ollama",
                    "model": "qwen3.5:9b",
                    "default_mode": "fast",
                    "role_tags": ["rp_stable", "canon"],
                    "audiences": ["user", "admin"],
                    "status": "active",
                    "description": "기본 안정형 롤플레잉 생성 모델.",
                },
                "emotion_focus_main": {
                    "id": "emotion_focus_main",
                    "label": "감정 집중",
                    "provider": "ollama",
                    "model": "qwen3.5:9b",
                    "default_mode": "thinking",
                    "role_tags": ["emotion"],
                    "audiences": ["user", "admin"],
                    "status": "active",
                    "description": "속도보다 감정 뉘앙스가 중요할 때 사용한다.",
                },
                "qa_repro_admin": {
                    "id": "qa_repro_admin",
                    "label": "QA 재현",
                    "provider": "ollama",
                    "model": "qwen3.5:9b",
                    "default_mode": "research",
                    "role_tags": ["qa_repro", "low_cost_test"],
                    "audiences": ["admin"],
                    "status": "active",
                    "description": "관리자 재현과 저비용 QA 실행에 사용한다.",
                },
                "repair_admin": {
                    "id": "repair_admin",
                    "label": "수정 보조",
                    "provider": "ollama",
                    "model": "qwen3.5:9b",
                    "default_mode": "thinking",
                    "role_tags": ["repair", "canon"],
                    "audiences": ["admin"],
                    "status": "deprecated",
                    "description": "재현용으로 남겨둔 구형 수정 지향 프로필.",
                },
            },
        }
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self._data_path:
            return
        if not self._data_path.exists():
            return
        raw = json.loads(self._data_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            self._data.update(raw)

    def _save_to_disk(self) -> None:
        if not self._data_path:
            return
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        self._data_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_persona(self, persona_id: str = "default") -> Dict[str, Any]:
        return dict(self._data.get("personas", {}).get(persona_id, self._data["personas"]["default"]))

    def get_user_profile(self, profile_id: str) -> Dict[str, Any]:
        return dict(self._data.get("user_profiles", {}).get(profile_id, {}))

    def get_user_character(self, character_id: str) -> Dict[str, Any]:
        return dict(self._data.get("user_characters", {}).get(character_id, {}))

    def get_bot_character(self, character_id: str) -> Dict[str, Any]:
        return dict(self._data.get("bot_characters", {}).get(character_id, {}))

    def get_lore(self, topic: str) -> Dict[str, Any]:
        lorebook = self._data.get("lorebook", {})
        if topic in lorebook:
            return dict(lorebook.get(topic, {}))
        normalized_topic = topic.strip().lower()
        for entry in lorebook.values():
            entry_topic = str(entry.get("topic", "")).strip().lower()
            aliases = [str(alias).strip().lower() for alias in entry.get("aliases", [])]
            if normalized_topic and (entry_topic == normalized_topic or normalized_topic in aliases):
                return dict(entry)
        return {}

    def get_memory_and_possessions(self, character_id: str) -> Dict[str, Any]:
        return dict(
            self._data.get("memories", {}).get(
                character_id,
                {"character_id": character_id, "important_memories": [], "possessions": []},
            )
        )

    def get_relationships(self, character_id: str, counterpart_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        section = self._data.get("relationships", {})
        raw = section.get(character_id, {})
        if not isinstance(raw, dict):
            return []
        allowed = {item.strip() for item in (counterpart_ids or []) if isinstance(item, str) and item.strip()}
        results: List[Dict[str, Any]] = []
        for target_id, payload in raw.items():
            if allowed and target_id not in allowed:
                continue
            if isinstance(payload, dict):
                item = dict(payload)
                item.setdefault("target_id", target_id)
                results.append(item)
        results.sort(key=lambda item: str(item.get("target_id", "")))
        return results

    def get_world_state(self, world_id: str = "default") -> Dict[str, Any]:
        return dict(self._data.get("world_state", {}).get(world_id, self._data["world_state"]["default"]))

    def get_scene_state(self, scene_id: str = "scene_default") -> Dict[str, Any]:
        section = self._data.get("scene_state", {})
        fallback = section.get("scene_default", {})
        return dict(section.get(scene_id, fallback))

    def get_character_state(self, character_id: str) -> Dict[str, Any]:
        cleaned_character_id = str(character_id or "").strip()
        section = self._data.get("character_state", {})
        if isinstance(section, dict):
            value = section.get(cleaned_character_id)
            if isinstance(value, dict):
                return dict(value)
        return {
            "character_id": cleaned_character_id,
            "emotion": "neutral",
            "location": "",
            "outfit": "",
            "scene_flags": {},
            "relationship_delta": {},
            "status_notes": [],
        }

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        cleaned_session_id = str(session_id or "").strip() or "default"
        section = self._data.get("session_state", {})
        if isinstance(section, dict):
            value = section.get(cleaned_session_id)
            if isinstance(value, dict):
                return dict(value)
            fallback = section.get("default")
            if isinstance(fallback, dict):
                merged = dict(fallback)
                merged["session_id"] = cleaned_session_id
                return merged
        return {
            "session_id": cleaned_session_id,
            "branch_id": "default",
            "active_location": "",
            "active_phase": "",
            "scene_flags": {},
            "status_notes": [],
        }

    def get_branch_state(self, branch_id: str = "default") -> Dict[str, Any]:
        cleaned_branch_id = str(branch_id or "").strip() or "default"
        section = self._data.get("branch_state", {})
        if isinstance(section, dict):
            value = section.get(cleaned_branch_id)
            if isinstance(value, dict):
                return dict(value)
            fallback = section.get("default")
            if isinstance(fallback, dict):
                merged = dict(fallback)
                merged["branch_id"] = cleaned_branch_id
                return merged
        return {
            "branch_id": cleaned_branch_id,
            "route_flags": {},
            "hidden_facts_revealed": [],
            "active_objectives": [],
        }

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        cleaned_session_id = str(session_id or "").strip() or "default"
        item = self.get_section_item("session_summary", cleaned_session_id)
        if item:
            return item
        return {
            "session_id": cleaned_session_id,
            "turn_count": 0,
            "summary": "",
            "recent_turn_ids": [],
            "summary_text": "",
        }

    def list_confirmed_facts(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        cleaned_session_id = str(session_id or "").strip() or "default"
        items = [
            item for item in self.list_section("confirmed_facts").values()
            if str(item.get("session_id") or "").strip() == cleaned_session_id
        ]
        items.sort(key=lambda item: (-float(item.get("confidence") or 0.0), str(item.get("id") or "")))
        if limit > 0:
            items = items[:limit]
        return items

    def upsert_character_state(self, character_id: str, value: Dict[str, Any]) -> None:
        cleaned_character_id = str(character_id or "").strip()
        payload = dict(value or {})
        payload["character_id"] = str(payload.get("character_id") or cleaned_character_id).strip() or cleaned_character_id
        payload.setdefault("emotion", "neutral")
        payload.setdefault("location", "")
        payload.setdefault("outfit", "")
        payload.setdefault("scene_flags", {})
        payload.setdefault("relationship_delta", {})
        payload.setdefault("status_notes", [])
        self.upsert("character_state", payload["character_id"], payload)

    def upsert_session_state(self, session_id: str, value: Dict[str, Any]) -> None:
        cleaned_session_id = str(session_id or "").strip() or "default"
        payload = dict(value or {})
        payload["session_id"] = str(payload.get("session_id") or cleaned_session_id).strip() or cleaned_session_id
        payload.setdefault("branch_id", "default")
        payload.setdefault("active_location", "")
        payload.setdefault("active_phase", "")
        payload.setdefault("scene_flags", {})
        payload.setdefault("status_notes", [])
        self.upsert("session_state", payload["session_id"], payload)

    def upsert_branch_state(self, branch_id: str, value: Dict[str, Any]) -> None:
        cleaned_branch_id = str(branch_id or "").strip() or "default"
        payload = dict(value or {})
        payload["branch_id"] = str(payload.get("branch_id") or cleaned_branch_id).strip() or cleaned_branch_id
        payload.setdefault("route_flags", {})
        payload.setdefault("hidden_facts_revealed", [])
        payload.setdefault("active_objectives", [])
        self.upsert("branch_state", payload["branch_id"], payload)

    def get_user_note(self, profile_id: str) -> Dict[str, Any]:
        cleaned_profile_id = str(profile_id or "").strip() or "default"
        item = self.get_section_item("user_notes", cleaned_profile_id)
        if item:
            return item
        return {
            "profile_id": cleaned_profile_id,
            "note": "",
            "hard_constraints": [],
            "preferred_dynamic": [],
            "relationship_expectation": "",
        }

    def get_session_note(self, session_id: str) -> Dict[str, Any]:
        cleaned_session_id = str(session_id or "").strip() or "default"
        item = self.get_section_item("session_notes", cleaned_session_id)
        if item:
            return item
        return {
            "session_id": cleaned_session_id,
            "note": "",
            "hard_constraints": [],
            "preferred_dynamic": [],
            "relationship_expectation": "",
        }

    def upsert_user_note(self, profile_id: str, value: Dict[str, Any]) -> None:
        cleaned_profile_id = str(profile_id or "").strip() or "default"
        payload = dict(value or {})
        payload["profile_id"] = str(payload.get("profile_id") or cleaned_profile_id).strip() or cleaned_profile_id
        payload.setdefault("note", "")
        payload.setdefault("hard_constraints", [])
        payload.setdefault("preferred_dynamic", [])
        payload.setdefault("relationship_expectation", "")
        self.upsert("user_notes", payload["profile_id"], payload)

    def upsert_session_note(self, session_id: str, value: Dict[str, Any]) -> None:
        cleaned_session_id = str(session_id or "").strip() or "default"
        payload = dict(value or {})
        payload["session_id"] = str(payload.get("session_id") or cleaned_session_id).strip() or cleaned_session_id
        payload.setdefault("note", "")
        payload.setdefault("hard_constraints", [])
        payload.setdefault("preferred_dynamic", [])
        payload.setdefault("relationship_expectation", "")
        self.upsert("session_notes", payload["session_id"], payload)

    def get_dialogue_priority(self, scene_id: str = "default") -> Dict[str, Any]:
        return dict(self._data.get("dialogue_priority", {}).get(scene_id, self._data["dialogue_priority"]["default"]))

    def get_model_catalog_item(self, model_id: str) -> Dict[str, Any]:
        return self.get_section_item("model_catalog", model_id)

    def list_model_catalog(
        self,
        *,
        audience: Optional[str] = None,
        role_tag: Optional[str] = None,
        status: str = "active",
    ) -> Dict[str, Dict[str, Any]]:
        items = self.list_section("model_catalog")
        audience_filter = (audience or "").strip().lower()
        role_tag_filter = (role_tag or "").strip().lower()
        status_filter = (status or "active").strip().lower() or "active"
        out: Dict[str, Dict[str, Any]] = {}
        for key, item in items.items():
            item_status = str(item.get("status") or "active").strip().lower() or "active"
            if status_filter == "active" and item_status != "active":
                continue
            if status_filter == "deprecated" and item_status != "deprecated":
                continue
            audiences = item.get("audiences", []) if isinstance(item.get("audiences", []), list) else []
            normalized_audiences = [str(value).strip().lower() for value in audiences if str(value).strip()]
            if audience_filter and audience_filter not in normalized_audiences:
                continue
            role_tags = item.get("role_tags", []) if isinstance(item.get("role_tags", []), list) else []
            normalized_role_tags = [str(value).strip().lower() for value in role_tags if str(value).strip()]
            if role_tag_filter and role_tag_filter not in normalized_role_tags:
                continue
            out[key] = dict(item)
        return out

    def list_section(self, section: str) -> Dict[str, Dict[str, Any]]:
        raw = self._data.get(section, {})
        if not isinstance(raw, dict):
            return {}
        return {str(key): dict(value) for key, value in raw.items() if isinstance(value, dict)}

    def get_section_item(self, section: str, key: str) -> Dict[str, Any]:
        raw = self._data.get(section, {})
        if not isinstance(raw, dict):
            return {}
        value = raw.get(key, {})
        return dict(value) if isinstance(value, dict) else {}

    def upsert(self, section: str, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            target = self._data.setdefault(section, {})
            if isinstance(target, dict):
                target[key] = value
                self._save_to_disk()

    def delete(self, section: str, key: str) -> bool:
        with self._lock:
            target = self._data.get(section, {})
            if not isinstance(target, dict) or key not in target:
                return False
            del target[key]
            self._save_to_disk()
            return True


class VectorDomainLookupStore(DomainLookupStore):
    """
    Vector-backed lookup adapter.
    Phase 1 scope: only lore lookup is routed to vector search, everything else
    delegates to JSON store to keep the current minimal runtime behavior.
    """

    def __init__(self, fallback_store: JsonDomainLookupStore, lore_search_url: Optional[str], timeout_sec: float = 2.0) -> None:
        self._fallback = fallback_store
        self._lore_search_url = (lore_search_url or "").strip() or None
        self._timeout_sec = float(timeout_sec or 2.0)

    def get_persona(self, persona_id: str = "default") -> Dict[str, Any]:
        return self._fallback.get_persona(persona_id)

    def get_user_profile(self, profile_id: str) -> Dict[str, Any]:
        return self._fallback.get_user_profile(profile_id)

    def get_user_character(self, character_id: str) -> Dict[str, Any]:
        return self._fallback.get_user_character(character_id)

    def get_bot_character(self, character_id: str) -> Dict[str, Any]:
        return self._fallback.get_bot_character(character_id)

    def get_lore(self, topic: str) -> Dict[str, Any]:
        result = self._vector_search_lore(topic)
        if result:
            return result
        return self._fallback.get_lore(topic)

    def get_memory_and_possessions(self, character_id: str) -> Dict[str, Any]:
        return self._fallback.get_memory_and_possessions(character_id)

    def get_relationships(self, character_id: str, counterpart_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return self._fallback.get_relationships(character_id, counterpart_ids=counterpart_ids)

    def get_world_state(self, world_id: str = "default") -> Dict[str, Any]:
        return self._fallback.get_world_state(world_id)

    def get_scene_state(self, scene_id: str = "scene_default") -> Dict[str, Any]:
        return self._fallback.get_scene_state(scene_id)

    def get_character_state(self, character_id: str) -> Dict[str, Any]:
        return self._fallback.get_character_state(character_id)

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        return self._fallback.get_session_state(session_id)

    def get_branch_state(self, branch_id: str = "default") -> Dict[str, Any]:
        return self._fallback.get_branch_state(branch_id)

    def upsert_character_state(self, character_id: str, value: Dict[str, Any]) -> None:
        self._fallback.upsert_character_state(character_id=character_id, value=value)

    def upsert_session_state(self, session_id: str, value: Dict[str, Any]) -> None:
        self._fallback.upsert_session_state(session_id=session_id, value=value)

    def upsert_branch_state(self, branch_id: str, value: Dict[str, Any]) -> None:
        self._fallback.upsert_branch_state(branch_id=branch_id, value=value)

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        return self._fallback.get_session_summary(session_id)

    def list_confirmed_facts(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        return self._fallback.list_confirmed_facts(session_id, limit=limit)

    def get_user_note(self, profile_id: str) -> Dict[str, Any]:
        return self._fallback.get_user_note(profile_id)

    def get_session_note(self, session_id: str) -> Dict[str, Any]:
        return self._fallback.get_session_note(session_id)

    def upsert_user_note(self, profile_id: str, value: Dict[str, Any]) -> None:
        self._fallback.upsert_user_note(profile_id=profile_id, value=value)

    def upsert_session_note(self, session_id: str, value: Dict[str, Any]) -> None:
        self._fallback.upsert_session_note(session_id=session_id, value=value)

    def get_dialogue_priority(self, scene_id: str = "default") -> Dict[str, Any]:
        return self._fallback.get_dialogue_priority(scene_id)

    def get_model_catalog_item(self, model_id: str) -> Dict[str, Any]:
        return self._fallback.get_model_catalog_item(model_id)

    def list_model_catalog(
        self,
        *,
        audience: Optional[str] = None,
        role_tag: Optional[str] = None,
        status: str = "active",
    ) -> Dict[str, Dict[str, Any]]:
        return self._fallback.list_model_catalog(audience=audience, role_tag=role_tag, status=status)

    def list_section(self, section: str) -> Dict[str, Dict[str, Any]]:
        return self._fallback.list_section(section)

    def get_section_item(self, section: str, key: str) -> Dict[str, Any]:
        return self._fallback.get_section_item(section, key)

    def upsert(self, section: str, key: str, value: Dict[str, Any]) -> None:
        self._fallback.upsert(section=section, key=key, value=value)

    def delete(self, section: str, key: str) -> bool:
        return self._fallback.delete(section=section, key=key)

    def _vector_search_lore(self, topic: str) -> Dict[str, Any]:
        if not self._lore_search_url:
            return {}
        payload = {"query": topic, "top_k": 1}
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=self._lore_search_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_sec) as response:
                raw = response.read().decode("utf-8")
        except (URLError, OSError, TimeoutError, ValueError):
            return {}

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}

        if isinstance(parsed, dict):
            direct = parsed.get("item")
            if isinstance(direct, dict):
                return direct
            results = parsed.get("results")
            if isinstance(results, list) and results:
                first = results[0]
                if isinstance(first, dict):
                    if isinstance(first.get("item"), dict):
                        return dict(first["item"])
                    return first
        return {}


_global_store: Optional[DomainLookupStore] = None


def get_domain_store(
    data_path: Optional[Path] = None,
    backend: str = "json",
    vectordb_lore_search_url: Optional[str] = None,
    vectordb_timeout_sec: float = 2.0,
) -> DomainLookupStore:
    global _global_store
    if _global_store is None:
        json_store = JsonDomainLookupStore(data_path=data_path)
        if (backend or "json").strip().lower() == "vector":
            _global_store = VectorDomainLookupStore(
                fallback_store=json_store,
                lore_search_url=vectordb_lore_search_url,
                timeout_sec=vectordb_timeout_sec,
            )
        else:
            _global_store = json_store
    return _global_store
