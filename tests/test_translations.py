import pytest

from bubblequest import translations
from bubblequest.translations import t


@pytest.fixture(autouse=True)
def reset_language():
    translations.load()
    yield
    translations.set_language("es")


def test_three_languages_in_menu_order():
    assert [lang.code for lang in translations.languages()] == ["es", "en", "fr"]
    assert [lang.flag for lang in translations.languages()] == ["es", "uk", "fr"]


def test_all_languages_have_same_keys():
    keys = [set(lang.texts) for lang in translations.languages()]
    assert keys[0] == keys[1] == keys[2]


def test_texts_change_with_language():
    assert t("win.title", level=2) == "Nivel 2 completado"
    translations.set_language("en")
    assert t("win.title", level=2) == "Level 2 complete"
    translations.set_language("fr")
    assert t("win.title", level=2) == "Niveau 2 terminé"


def test_next_language_cycles():
    seen = []
    for _ in range(4):
        lang = translations.next_language()
        translations.set_language(lang.code)
        seen.append(lang.code)
    assert seen == ["en", "fr", "es", "en"]


def test_unknown_key_shows_key():
    assert t("no.existe") == "no.existe"
