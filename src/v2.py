# -*- coding: utf-8 -*-

import re

from aqt import mw
from aqt.utils import showInfo
from aqt.addcards import AddCards
from aqt.browser import Browser
from aqt.editcurrent import EditCurrent
from aqt.utils import tooltip
from anki.hooks import addHook, wrap
from aqt.editor import Editor
from aqt.qt import *


from aqt.browser import DataModel

# constants
MODEL_NAME = "Test"  # TODO: change
CONTENT_FIELD_NAME = "# CONTENT"
NOTE_FIELD_NAME = "Note"
IN_USE_CLOZES_FIELD_NAME = "In-use Clozes"
UPDATE_ENHANCED_CLOZE_SHORTCUT = "Ctrl+Alt+C"
CLOZE_FIELD_NAME = "Cloze"
MAX_CLOZE_COUNT = 100


# global variables
hint_and_answer_array = [[] for i in range(MAX_CLOZE_COUNT + 1)]


def check_model(model):
    return re.search(MODEL_NAME, model["name"])


def generate_enhanced_cloze(note):
    src_content = note[CONTENT_FIELD_NAME]
    if re.search(r"\S", note[NOTE_FIELD_NAME]):
        src_content += '<br><div id="note" class="content">' + \
            note[NOTE_FIELD_NAME] + '</div>'

    cloze_start_regex = r"\{\{c\d+::"
    cloze_start_matches = re.findall(cloze_start_regex, src_content)

    if not cloze_start_matches:
        note[IN_USE_CLOZES_FIELD_NAME] = "[0]"
        note["Cloze1"] = src_content + \
            '<div style="display:none">{{c1::@@@@}}</div>' + \
            '<div id="card-cloze-id" style="display:none">c0</div>'
        return
    else:
        in_use_cloze_groups = sorted(
            [int(re.sub(r"\D", "", x)) for x in set(cloze_start_matches)])
        note[IN_USE_CLOZES_FIELD_NAME] = str(in_use_cloze_groups)

        cloze_field_content = src_content
        cloze_regex = r"\{\{c\d+::[\s\S]*?\}\}"
        cloze_field_content = re.sub(
            cloze_regex, process_cloze, cloze_field_content)
        # TODO:
        global hint_and_answer_array
        for cloze_group in in_use_cloze_groups:
            cloze_field_content += '<div style="display:none">{{c%s::@@@@}}</div>' % cloze_group
            for index, item in enumerate(hint_and_answer_array[cloze_group]):
                cloze_field_content += '<pre style="display:none"><div id="cloze-%s-%s-answer">%s</div></pre>' % (
                    cloze_group, index, item['answer'])
                cloze_field_content += '<pre style="display:none"><div id="cloze-%s-%s-hint">%s</div></pre>' % (
                    cloze_group, index, item['hint'])
        note[CLOZE_FIELD_NAME] = cloze_field_content
        return


def process_cloze(matchObj):
    cloze_string = matchObj.group()  # eg. {{c1::aa[::bbb]}}
    index_of_answer = cloze_string.find("::") + 2
    index_of_hint = cloze_string.rfind("::") + 2
    cloze_group = cloze_string[2: index_of_answer - 2]  # like: c1 or c11
    cloze_length = len(cloze_string)

    answer = ""
    hint = ""
    if index_of_answer == index_of_hint:  # actually no hint at all
        answer = cloze_string[index_of_answer: cloze_length - 2]
        hint = ""
    else:
        answer = cloze_string[index_of_answer: index_of_hint - 2]
        hint = cloze_string[index_of_hint: cloze_length - 2]

    global hint_and_answer_array

    hint_and_answer_array[cloze_group].append({'hint': hint, 'answer': answer})

    cloze_index_in_group = len(hint_and_answer_array[cloze_group]) - 1

    new_html = '<span class="cloze" cloze-group="_cloze-group_" cloze-index-in-group="_cloze-index-in-group_" show-state="hint" >_content_</span>'
    new_html = new_html.replace('_cloze-group_', cloze_group).replace(
        '_cloze-index-in-group_', cloze_index_in_group)
    return new_html


def on_add_cards(self, _old):
    process_note(self, _old)


def on_edit_current_save(self, _old):
    process_note(self, _old)


def process_note(self, _old):
    # note = pass_in_self.editor.note
    # if not note or not check_model(note.model()):
    #     return pass_in_old(pass_in_self)
    # remove_style_of_note(note)
    # generate_enhanced_cloze(note)
    ret = _old(self)
    # c = DataModel.getCard('1516434017641')
    # showInfo(c.template()['name'])
    ids = mw.col.findCards(u"tag:#深入")
    for id in ids:
        card=mw.col.getCard(id)
        q=card.q()
        a=card.a()
        showInfo(str(q))
        showInfo(str(a))
    return ret


AddCards.addCards = wrap(AddCards.addCards, on_add_cards, "around")
EditCurrent.onSave = wrap(EditCurrent.onSave, on_edit_current_save, "around")
