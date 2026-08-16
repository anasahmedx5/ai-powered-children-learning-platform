import logging
from typing import List, Dict, Optional

logger = logging.getLogger("MindBuzzLogger")


class WordNotFoundError(Exception):
    def __init__(self, word: str):
        self.word = word
        super().__init__(f"Word '{word}' not found in pronunciation dictionary")


CMU_DICTIONARY: Dict[str, List[str]] = {
    "APPLE": ["AE", "P", "AH", "L"],
    "ANCHOR": ["AE", "NG", "K", "ER"],
    "ANIMAL": ["AE", "N", "AH", "M", "AH", "L"],
    "BANANA": ["B", "AH", "N", "AE", "N", "AH"],
    "BASKET": ["B", "AE", "S", "K", "AH", "T"],
    "BUTTON": ["B", "AH", "T", "AH", "N"],
    "CASTLE": ["K", "AE", "S", "AH", "L"],
    "CANDLE": ["K", "AE", "N", "D", "AH", "L"],
    "COOKIE": ["K", "UH", "K", "IY"],
    "DOLPHIN": ["D", "AA", "L", "F", "AH", "N"],
    "DRAGON": ["D", "R", "AE", "G", "AH", "N"],
    "DONUT": ["D", "OW", "N", "AH", "T"],
    "ELEPHANT": ["EH", "L", "AH", "F", "AH", "N", "T"],
    "ENGINE": ["EH", "N", "JH", "AH", "N"],
    "ELBOW": ["EH", "L", "B", "OW"],
    "FLOWER": ["F", "L", "AW", "ER"],
    "FEATHER": ["F", "EH", "DH", "ER"],
    "FOREST": ["F", "AO", "R", "AH", "S", "T"],
    "GARDEN": ["G", "AA", "R", "D", "AH", "N"],
    "GIRAFFE": ["JH", "ER", "AE", "F"],
    "GUITAR": ["G", "IH", "T", "AA", "R"],
    "HAMMER": ["HH", "AE", "M", "ER"],
    "HELMET": ["HH", "EH", "L", "M", "AH", "T"],
    "HONEY": ["HH", "AH", "N", "IY"],
    "IGLOO": ["IH", "G", "L", "UW"],
    "INSECT": ["IH", "N", "S", "EH", "K", "T"],
    "ISLAND": ["AY", "L", "AH", "N", "D"],
    "JACKET": ["JH", "AE", "K", "AH", "T"],
    "JUNGLE": ["JH", "AH", "NG", "G", "AH", "L"],
    "JELLY": ["JH", "EH", "L", "IY"],
    "KITTEN": ["K", "IH", "T", "AH", "N"],
    "KETTLE": ["K", "EH", "T", "AH", "L"],
    "KANGAROO": ["K", "AE", "NG", "G", "ER", "UW"],
    "LEMON": ["L", "EH", "M", "AH", "N"],
    "LIZARD": ["L", "IH", "Z", "ER", "D"],
    "LANTERN": ["L", "AE", "N", "T", "ER", "N"],
    "MONKEY": ["M", "AH", "NG", "K", "IY"],
    "MAGNET": ["M", "AE", "G", "N", "AH", "T"],
    "MUFFIN": ["M", "AH", "F", "AH", "N"],
    "NUMBER": ["N", "AH", "M", "B", "ER"],
    "NOODLE": ["N", "UW", "D", "AH", "L"],
    "NAPKIN": ["N", "AE", "P", "K", "AH", "N"],
    "ORANGE": ["AO", "R", "AH", "N", "JH"],
    "OCTOPUS": ["AA", "K", "T", "AH", "P", "UH", "S"],
    "OSTRICH": ["AA", "S", "T", "R", "IH", "CH"],
    "PANDA": ["P", "AE", "N", "D", "AH"],
    "PENCIL": ["P", "EH", "N", "S", "AH", "L"],
    "PUPPET": ["P", "AH", "P", "AH", "T"],
    "QUEEN": ["K", "W", "IY", "N"],
    "QUILT": ["K", "W", "IH", "L", "T"],
    "QUACK": ["K", "W", "AE", "K"],
    "RABBIT": ["R", "AE", "B", "IH", "T"],
    "ROCKET": ["R", "AA", "K", "AH", "T"],
    "RAINBOW": ["R", "EY", "N", "B", "OW"],
    "SPIDER": ["S", "P", "AY", "D", "ER"],
    "SQUIRREL": ["S", "K", "W", "ER", "AH", "L"],
    "SUNFLOWER": ["S", "AH", "N", "F", "L", "AW", "ER"],
    "TURTLE": ["T", "ER", "T", "AH", "L"],
    "TIGER": ["T", "AY", "G", "ER"],
    "TOMATO": ["T", "AH", "M", "EY", "T", "OW"],
    "UMBRELLA": ["AH", "M", "B", "R", "EH", "L", "AH"],
    "UNICORN": ["Y", "UW", "N", "AH", "K", "AO", "R", "N"],
    "UNIFORM": ["Y", "UW", "N", "AH", "F", "AO", "R", "M"],
    "VOLCANO": ["V", "AA", "L", "K", "EY", "N", "OW"],
    "VIOLET": ["V", "AY", "AH", "L", "AH", "T"],
    "VIOLIN": ["V", "AY", "AH", "L", "IH", "N"],
    "WINDOW": ["W", "IH", "N", "D", "OW"],
    "WATERMELON": ["W", "AO", "T", "ER", "M", "EH", "L", "AH", "N"],
    "WHISPER": ["W", "IH", "S", "P", "ER"],
    "XYLOPHONE": ["Z", "AY", "L", "AH", "F", "OW", "N"],
    "XRAY": ["EKS", "R", "EY"],
    "XEROX": ["Z", "IH", "R", "AA", "K", "S"],
    "YELLOW": ["Y", "EH", "L", "OW"],
    "YOGURT": ["Y", "OW", "G", "ER", "T"],
    "YACHT": ["Y", "AA", "T"],
    "ZEBRA": ["Z", "IY", "B", "R", "AH"],
    "ZIPPER": ["Z", "IH", "P", "ER"],
    "ZUCCHINI": ["Z", "UW", "K", "IY", "N", "IY"],
    "ZERO": ["Z", "IH", "R", "OW"],
    "ONE": ["W", "AH", "N"],
    "TWO": ["T", "UW"],
    "THREE": ["TH", "R", "IY"],
    "FOUR": ["F", "AO", "R"],
    "FIVE": ["F", "AY", "V"],
    "SIX": ["S", "IH", "K", "S"],
    "SEVEN": ["S", "EH", "V", "AH", "N"],
    "EIGHT": ["EY", "T"],
    "NINE": ["N", "AY", "N"],
    "TEN": ["T", "EH", "N"]
}

G2P_LETTER_MAP: Dict[str, str] = {
    'A': 'AE', 'B': 'B', 'C': 'K', 'D': 'D', 'E': 'EH',
    'F': 'F', 'G': 'G', 'H': 'HH', 'I': 'IH', 'J': 'JH',
    'K': 'K', 'L': 'L', 'M': 'M', 'N': 'N', 'O': 'AA',
    'P': 'P', 'Q': 'K', 'R': 'R', 'S': 'S', 'T': 'T',
    'U': 'AH', 'V': 'V', 'W': 'W', 'X': 'K', 'Y': 'Y', 'Z': 'Z'
}


class PronunciationDictionary:

    def __init__(self, custom_dict: Optional[Dict[str, List[str]]] = None):
        self._dict = dict(CMU_DICTIONARY)
        if custom_dict:
            for k, v in custom_dict.items():
                self._dict[k.strip().upper()] = v

    def get_phonemes(self, word: str) -> List[str]:
        if not word or not word.strip():
            raise WordNotFoundError(word)

        clean_word = "".join(c.upper() for c in word.strip() if c.isalpha())
        if not clean_word:
            raise WordNotFoundError(word)

        if clean_word in self._dict:
            return list(self._dict[clean_word])

        phonemes = [G2P_LETTER_MAP[ch] for ch in clean_word if ch in G2P_LETTER_MAP]
        if phonemes:
            return phonemes

        raise WordNotFoundError(word)
