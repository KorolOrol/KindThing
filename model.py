from __future__ import annotations
from typing import List, Union, Set, Dict, Optional, Tuple
from enum import Enum
import math
import json

class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    UNISEX = "unisex"


class Purpose(Enum):
    APPEARANCE = "appearance"
    POSE = "pose"
    ACTION = "action"
    STYLE = "style"
    LIGHTING = "lighting"
    CLOTHING = "clothing"
    EXPRESSION = "expression"
    COMPOSITION = "composition"
    BACKGROUND = "background"
    OTHER = "other"


class CombinePolicy(Enum):
    GEOMETRIC = "geometric"
    MULTIPLICATIVE = "multiplicative" # not realized yet
    WRAP = "wrap" # not realized yet


class PromptPart:
    """
    Атомарный элемент промпта: строка или вложенный PromptElement с весом.
    """
    def __init__(self, value: Union[str, PromptElement], weight: float = 1.0):
        self.value = value
        self.weight = weight

    def render(self) -> Dict[str, List[float]]:
        """
        Преобразовать часть в строку для промпта с учетом веса.
        """
        if isinstance(self.value, str):
            return {self.value:[self.weight]}
        else:
            return self.value.render(weight_override=self.weight)

    def collect_tags(self) -> Set[str]:
        """
        Собрать имена всех вложенных тегов из этой части.
        """
        if isinstance(self.value, PromptElement):
            return self.value.collect_all_tags()
        return set()


class PromptElement:
    """
    Базовый класс для тегов, персонажей и Lora: содержит имя, пол
    и упорядоченный список PromptPart.
    """
    def __init__(
        self,
        name: str,
        gender: Gender,
        parts: List[PromptPart],
        combine_policy: CombinePolicy = CombinePolicy.GEOMETRIC,
    ):
        self.name = name
        self.gender = gender
        self.parts = parts
        self.combine_policy = combine_policy

    def render(self, weight_override: float = 1.0) -> Dict[str, List[float]]:
        """
        Сформировать словарь промптов с весами
        Если weight_override != 1.0, применить политику объединения.
        """
        rendered_parts: Dict[str, List[float]] = {}
        for part in self.parts:
            for key, value in part.render().items():
                if key not in rendered_parts:
                    rendered_parts[key] = []
                rendered_parts[key].extend(value)
        
        for key in rendered_parts:
            rendered_parts[key].append(weight_override)
        
        return rendered_parts

    def collect_all_tags(self) -> Set[str]:
        """
        Собрать имя элемента и все вложенные имена тегов.
        """
        tags = {self.name}
        for part in self.parts:
            tags |= part.collect_tags()
        return tags


class Tag(PromptElement):
    """
    Тег промпта: цель, несовместимости
    и вложенные через PromptPart.
    """
    def __init__(
        self,
        name: str,
        gender: Gender,
        purpose: Purpose,
        parts: List[PromptPart],
        incompatible_names: Optional[Set[str]] = None,
        combine_policy: CombinePolicy = CombinePolicy.GEOMETRIC,
    ):
        super().__init__(name, gender, parts, combine_policy)
        self.purpose = purpose
        self.incompatible_names: Set[str] = incompatible_names or set()
        self.incompatible_tags: Set[Tag] = set()

    def add_incompatibility(self, other: Tag):
        """
        Установить взаимную несовместимость с другим тегом.
        """
        self.incompatible_tags.add(other)
        other.incompatible_tags.add(self)
        self.incompatible_names.add(other.name)
        other.incompatible_names.add(self.name)

    def is_compatible_with(self, other: Tag) -> bool:
        """
        Проверить, совместим ли текущий тег с другим.
        """
        return other.name not in self.incompatible_names


class Character(PromptElement):
    """
    Персонаж: хранит имя, пол, части промпта и счетчик использования.
    """
    def __init__(
        self,
        name: str,
        gender: Gender,
        parts: List[PromptPart],
    ):
        super().__init__(name, gender, parts)
        self.images_generated = 0  # счетчик созданных изображений

    def increment_usage(self):
        """
        Увеличить счетчик использования персонажа.
        """
        self.images_generated += 1


class Lora(PromptElement):
    """
    Класс для Lora-моделей: выводит в формате <lora:имя:вес>.
    """
    def __init__(
        self,
        name: str,
        weight: float = 1.0
    ):
        super().__init__(name, Gender.UNISEX, [], combine_policy=CombinePolicy.MULTIPLICATIVE)
        self.weight = weight

    def render(self, weight_override: float = 1.0) -> Dict[str, List[float]]:
        """
        Render для Lora: применяет собственный вес и внешний override.
        """
        return {f"<lora:{self.name}:{self.weight * weight_override}>": []}


class PromptFactory:
    """
    Собирает итоговую строку промпта из списка тегов, Lora и персонажей.
    Возвращает (prompt_str, filename) с кодом usage.
    Можно опционально проверять соответствие пола тегов и персонажей.
    """
    @staticmethod
    def generate(
        elements: List[PromptElement | None],
        break_token: str = "BREAK",
        enforce_gender: bool = False,
    ) -> Tuple[str, str]:
        # разделение на группы по персонажам
        groups: List[Tuple[Character, List[PromptElement]]] = []
        current_char: Optional[Character] = None
        for el in elements:
            if el is None:
                continue
            if isinstance(el, Character):
                current_char = el
                el.increment_usage()
                groups.append((el, []))
            elif isinstance(el, (Tag, Lora)):
                if current_char is None:
                    raise ValueError("Нужен хотя бы один персонаж перед тегами или Lora")
                # опциональная проверка пола
                if enforce_gender and isinstance(el, Tag):
                    if el.gender != Gender.UNISEX and el.gender != current_char.gender:
                        raise ValueError(
                            f"Тег '{el.name}' (пол {el.gender.value}) не подходит к персонажу '{current_char.name}' (пол {current_char.gender.value})"
                        )
                groups[-1][1].append(el)
            else:
                raise TypeError(f"Неподдерживаемый тип: {type(el)}")
        if not groups:
            raise ValueError("Необходимо указать хотя бы одного персонажа")
        group_strs: List[str] = []
        name_parts: List[str] = []
        for char, parts in groups:
            name_parts.append(f"{char.name}_{char.images_generated}")
            # проверка несовместимости только для Tag
            tags = [p for p in parts if isinstance(p, Tag)]
            for t1 in tags:
                for t2 in tags:
                    if t1 is not t2 and not t1.is_compatible_with(t2):
                        raise ValueError(f"Теги '{t1.name}' и '{t2.name}' несовместимы")
            rend = char.render()
            for part in parts:
                if isinstance(part, Tag):
                    for key, value in part.render().items():
                        if key not in rend:
                            rend[key] = []
                        rend[key].extend(value)
                elif isinstance(part, Lora):
                    for key, value in part.render().items():
                        if key not in rend:
                            rend[key] = []
                        rend[key].extend(value)
                else:
                    raise TypeError(f"Неподдерживаемый тип: {type(part)}")
            # применение политики объединения
            if char.combine_policy == CombinePolicy.GEOMETRIC:
                for key in rend:
                    rend[key] = [math.prod(rend[key]) ** (1 / len(rend[key]))]

            group_str = ""
            for key, value in rend.items():
                if "<lora:" in key:
                    group_str += f"{key}, "
                else:
                    if value[0] == 1:
                        group_str += f"{key}, "
                    else:
                        group_str += f"({key}:{value[0]}), "
            group_strs.append(group_str)
        prompt_str = f" {break_token}, ".join(group_strs)
        filename = "_".join(name_parts)
        return prompt_str, filename


class TagRegistry:
    """
    Глобальный реестр тегов, персонажей и Lora для поиска и сохранения.
    """
    _tags: Dict[str, Tag] = {}
    _chars: Dict[str, Character] = {}
    _loras: Dict[str, Lora] = {}

    @classmethod
    def register_tag(cls, tag: Tag):
        cls._tags[tag.name] = tag

    @classmethod
    def register_char(cls, char: Character):
        cls._chars[char.name] = char

    @classmethod
    def register_lora(cls, lora: Lora):
        cls._loras[lora.name] = lora

    @classmethod
    def find(cls, name: str) -> Optional[PromptElement]:
        return cls._tags.get(name) or cls._chars.get(name) or cls._loras.get(name)

    @classmethod
    def all_tags(cls) -> List[Tag]:
        return list(cls._tags.values())

    @classmethod
    def all_characters(cls) -> List[Character]:
        return list(cls._chars.values())

    @classmethod
    def all_loras(cls) -> List[Lora]:
        return list(cls._loras.values())

    @classmethod
    def save(cls, filepath: str):
        """
        Сохранить персонажей, теги и Lora в JSON-файл.
        """
        data = {
            'characters': [
                {'name': c.name, 'gender': c.gender.value,
                 'parts': [{'type': 'string' if isinstance(part.value, str) else 'element',
                            'value': part.value if isinstance(part.value, str) else part.value.name,
                            'weight': part.weight}
                           for part in c.parts],
                 'images_generated': c.images_generated
                }
                for c in cls.all_characters()
            ],
            'tags': [
                {'name': t.name, 'gender': t.gender.value, 'purpose': t.purpose.value,
                 'parts': [{'type': 'string' if isinstance(part.value, str) else 'element',
                            'value': part.value if isinstance(part.value, str) else part.value.name,
                            'weight': part.weight}
                           for part in t.parts],
                 'incompatibles': list(t.incompatible_names)
                }
                for t in cls.all_tags()
            ],
            'loras': [
                {'name': lora.name, 'weight': lora.weight}
                for lora in cls.all_loras()
            ]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str):
        """
        Загрузить персонажей, теги и Lora из JSON-файла.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            # Чтение основной информации без вложенных тегов
            # и создание объектов Tag, Character и Lora
            data = json.load(f)
            for char_data in data.get('characters', []):
                char = Character(
                    name=char_data['name'],
                    gender=Gender[char_data['gender'].upper()],
                    parts=[])
                TagRegistry.register_char(char)
            for tag_data in data.get('tags', []):
                tag = Tag(
                    name=tag_data['name'],
                    gender=Gender[tag_data['gender'].upper()],
                    purpose=Purpose[tag_data['purpose'].upper()],
                    parts=[])
                TagRegistry.register_tag(tag)
            for lora_data in data.get('loras', []):
                lora = Lora(
                    name=lora_data['name'],
                    weight=lora_data['weight'])
                TagRegistry.register_lora(lora)
            
            # Чтение вложенных тегов и частей
            # и добавление их в соответствующие объекты Tag и Character
            for char_data in data.get('characters', []):
                char = TagRegistry.find(char_data['name'])
                if char is None:
                    char = Character(
                        name=char_data['name'],
                        gender=Gender[char_data['gender'].upper()],
                        parts=[]
                    )
                    TagRegistry.register_char(char)
                for part_data in char_data['parts']:
                    if part_data['type'] == 'string':
                        char.parts.append(PromptPart(part_data['value'], part_data['weight']))
                    else:
                        insertion = TagRegistry.find(part_data['value'])
                        if insertion is None:
                            raise ValueError(f"Неизвестный элемент: {part_data['value']}")
                        part = PromptPart(insertion, part_data['weight'])
                        char.parts.append(part)
                if isinstance(char, Character):
                    char.images_generated = char_data['images_generated']
            for tag_data in data.get('tags', []):
                tag = TagRegistry.find(tag_data['name'])
                if tag is None:
                    tag = Tag(
                        name=tag_data['name'],
                        gender=Gender[tag_data['gender'].upper()],
                        purpose=Purpose[tag_data['purpose'].upper()],
                        parts=[]
                    )
                    TagRegistry.register_tag(tag)
                for part_data in tag_data['parts']:
                    if part_data['type'] == 'string':
                        tag.parts.append(PromptPart(part_data['value'], part_data['weight']))
                    else:
                        insertion = TagRegistry.find(part_data['value'])
                        if insertion is None:
                            raise ValueError(f"Неизвестный элемент: {part_data['value']}")
                        part = PromptPart(insertion, part_data['weight'])
                        tag.parts.append(part)
                for name in tag_data['incompatibles']:
                    incompatible_tag = TagRegistry.find(name)
                    if incompatible_tag is None:
                        raise ValueError(f"Неизвестный элемент: {name}")
                    if isinstance(tag, Tag) and isinstance(incompatible_tag, Tag):
                        tag.add_incompatibility(incompatible_tag)
                
            
