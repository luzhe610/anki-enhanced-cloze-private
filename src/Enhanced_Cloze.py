# -*- coding: utf-8 -*-

import re

import aqt
from aqt import mw
from aqt.utils import showInfo
from aqt.addcards import AddCards
from aqt.browser import Browser
from aqt.editcurrent import EditCurrent
from aqt.utils import tooltip
from aqt.editor import Editor
from aqt.qt import *
from anki.hooks import addHook, wrap

from bs4 import BeautifulSoup

import sys
reload(sys)
sys.setdefaultencoding('utf8')

# global variables
genuine_cloze_answer_array = []
genuine_cloze_hint_array = []
pseudo_cloze_answer_array = []
pseudo_cloze_hint_array = []
current_cloze_field_number = 0

# constants
MODEL_NAME_CORE_PART = "Enhanced Cloze"
CONTENT_FIELD_NAME_1 = "# Content 1"
CONTENT_FIELD_NAME_2 = "# Content 2"
CONTENT_FIELD_NAME_3 = "# Content 3"
CONTENT_FIELD_NAME_4 = "# Content 4"
CONTENT_FIELD_NAME_5 = "# Content 5"
CONTENT_FIELD_NAME_LIST = [CONTENT_FIELD_NAME_1, CONTENT_FIELD_NAME_2,
                           CONTENT_FIELD_NAME_3, CONTENT_FIELD_NAME_4, CONTENT_FIELD_NAME_5]
IN_USE_CLOZES_FIELD_NAME = "In-use Clozes"
UPDATE_ENHANCED_CLOZE_SHORTCUT = "Ctrl+Alt+Shift+U"
MAX_CLOZE_FIELD_NUMBER = 100


def generate_enhanced_cloze(note):
    # cloze_id means, eg. c1, cloze_number means, eg. 1

    src_content = ""
    for content_field_name in CONTENT_FIELD_NAME_LIST:
        soup = BeautifulSoup(note[content_field_name])
        if soup.get_text():
            src_content += '<div id={} class="content-block">{}</div>'.format(
                "content-" + re.search(r'\d+', content_field_name).group(), note[content_field_name])
    src_content = remove_cloze_style_tag(src_content)

    # Get ids of in-use clozes
    cloze_start_regex = r"\{\{c\d+::"
    cloze_start_matches = re.findall(cloze_start_regex, src_content)

    if not cloze_start_matches:
        for i_cloze_field_number in range(1, MAX_CLOZE_FIELD_NUMBER + 1):
            dest_field_name = "Cloze{}".format(i_cloze_field_number)
            note[dest_field_name] = ""

        note[IN_USE_CLOZES_FIELD_NAME] = "[0]"

        # Anki will warn if cloze notes include no cloze or more strictly, no single-line cloze
        # so I use a invisible single-line cloze {{cX::@@@@}} to cheat Anki :)
        note["Cloze1"] = src_content + \
            '<div style="display:none">{{c1::@@@@}}</div>' + \
            '<div id="card-cloze-id" style="display:none">c0</div>'
        return
    else:
        in_use_clozes_numbers = sorted(
            [int(re.search(r"\d+", x).group()) for x in set(cloze_start_matches)])
        note[IN_USE_CLOZES_FIELD_NAME] = str(in_use_clozes_numbers)

        # Fill in content in in-use cloze fields and empty content in not-in-use fields
        global current_cloze_field_number
        for current_cloze_field_number in range(1, MAX_CLOZE_FIELD_NUMBER + 1):

            dest_field_name = "Cloze{}".format(current_cloze_field_number)

            if not current_cloze_field_number in in_use_clozes_numbers:
                dest_field_content = ""
            else:
                # Initialize the lists to store different content on each card later
                global genuine_cloze_answer_array
                global genuine_cloze_hint_array
                global pseudo_cloze_answer_array
                global pseudo_cloze_hint_array

                del genuine_cloze_answer_array[:]
                del genuine_cloze_hint_array[:]
                del pseudo_cloze_answer_array[:]
                del pseudo_cloze_hint_array[:]

                dest_field_content = src_content

                cloze_regex = r"\{\{c\d+::[\s\S]*?\}\}"
                dest_field_content = re.sub(
                    cloze_regex, process_cloze, dest_field_content)

                # Store corresponding answers and hints (gunuine or pseudo)
                # in html of every in-use cloze fields for javascript to fetch later
                for index, item in enumerate(genuine_cloze_answer_array):
                    dest_field_content += '<pre style="display:none"><div id="genuine-cloze-answer-{}">{}</div></pre>'.format(
                        index, item)
                for index, item in enumerate(genuine_cloze_hint_array):
                    dest_field_content += '<pre style="display:none"><div id="genuine-cloze-hint-{}">{}</div></pre>'.format(
                        index, item)
                for index, item in enumerate(pseudo_cloze_answer_array):
                    dest_field_content += '<pre style="display:none"><div id="pseudo-cloze-answer-{}">{}</div></pre>'.format(
                        index, item)
                for index, item in enumerate(pseudo_cloze_hint_array):
                    dest_field_content += '<pre style="display:none"><div id="pseudo-cloze-hint-{}">{}</div></pre>'.format(
                        index, item)

                dest_field_content += '<div style="display:none">{{c{}::@@@@}}</div>'.format(
                    current_cloze_field_number)
                dest_field_content += '<div id="card-cloze-id" style="display:none">c{}</div>'.format(
                    str(current_cloze_field_number))

            note[dest_field_name] = dest_field_content


def check_model(model):
    return re.search(MODEL_NAME_CORE_PART, model["name"])


def process_cloze(matchObj):

    cloze_string = matchObj.group()  # eg. {{c1::aa[::bbb]}}
    index_of_answer = cloze_string.find("::") + 2
    index_of_hint = cloze_string.rfind("::") + 2
    cloze_id = cloze_string[2: index_of_answer - 2]  # like: c1 or c11
    cloze_length = len(cloze_string)

    answer = ""
    hint = ""
    if index_of_answer == index_of_hint:  # actually no hint at all
        answer = cloze_string[index_of_answer: cloze_length - 2]
        hint = ""
    else:
        answer = cloze_string[index_of_answer: index_of_hint - 2]
        hint = cloze_string[index_of_hint: cloze_length - 2]

    global current_cloze_field_number
    if cloze_id != 'c' + str(current_cloze_field_number):
        # Process pseudo-cloze
        global pseudo_cloze_answer_array
        global pseudo_cloze_hint_array
        pseudo_cloze_answer_array.append(answer)
        pseudo_cloze_hint_array.append(hint)
        index_in_array = len(pseudo_cloze_answer_array) - 1
        new_html = '<span class="pseudo-cloze" index="{}" show-state="hint" cloze-id="{}">{}</span>'.format(
            str(index_in_array), cloze_id, cloze_string.replace("{", '[').replace("}", "]"))
        return new_html
    else:
        # Process genuine-cloze
        global genuine_cloze_answer_array
        global genuine_cloze_hint_array
        genuine_cloze_answer_array.append(answer)
        genuine_cloze_hint_array.append(hint)
        index_in_array = len(genuine_cloze_answer_array) - 1
        new_html = '<span class="genuine-cloze" index="{}" show-state="hint" cloze-id="{}">{}</span>'.format(
            str(index_in_array),  cloze_id, cloze_string)
        return new_html


def on_add_cards(self, _old):
    add_or_edit_current(self, _old)


def on_edit_current_save(self, _old):
    add_or_edit_current(self, _old)


def add_or_edit_current(self, _old):
    note = self.editor.note
    if not note or not check_model(note.model()):
        return _old(self)
    remove_style_of_note(note)
    add_cloze_style_tag_of_note(note)
    generate_enhanced_cloze(note)
    ret = _old(self)
    return ret


def update_all_enhanced_clozes_in_browser(self):
    browser = self
    mw = browser.mw

    mw.checkpoint("Update Enhanced Clozes")
    mw.progress.start()
    browser.model.beginReset()

    update_all_enhanced_cloze(self)

    browser.model.endReset()
    mw.requireReset()
    mw.progress.finish()
    mw.reset()


def update_all_enhanced_clozes_in_main_window():
    update_all_enhanced_cloze(aqt)
    aqt.mw.reset()


def update_all_enhanced_cloze(self):
    mw = self.mw
    nids = mw.col.findNotes("*")
    for nid in nids:
        note = mw.col.getNote(nid)
        if not check_model(note.model()):
            continue
        remove_style_of_note(note)
        add_cloze_style_tag_of_note(note)

        # # in case you have to remove
        # note[CONTENT_FIELD_NAME] = remove_cloze_style_tag(
        #     note[CONTENT_FIELD_NAME])
        # note[NOTE_FIELD_NAME] = remove_cloze_style_tag(note[NOTE_FIELD_NAME])

        generate_enhanced_cloze(note)
        # note.flush()
    tooltip('Update Enhanced Clozed Finished')


def setup_menu_in_browser(self):
    setup_menu(self)


def setup_menu(window):
    try:
        menu = window.form.menuUtilities
    except:
        window.form.menuUtilities = QMenu("&Utilites", window.form.menubar)
        menu = window.form.menuUtilities
        window.form.menubar.addMenu(menu)
    a = menu.addAction('&Update Enhanced Clozes')
    a.setShortcut(QKeySequence(UPDATE_ENHANCED_CLOZE_SHORTCUT))
    if window == aqt.mw:
        a.triggered.connect(update_all_enhanced_clozes_in_main_window)
    else:
        a.triggered.connect(
            lambda _, b=window: update_all_enhanced_clozes_in_browser(b))


# def on_save_now(self, callback=None):
#     generate_enhanced_cloze(self.note)


def process_note_in_editor(self):
    remove_style_of_note(self.note)
    add_cloze_style_tag_of_note(self.note)
    self.mw.progress.timer(100, self.loadNote, False)


def remove_style_of_note(note):
    for content_field_name in CONTENT_FIELD_NAME_LIST:
        note[content_field_name] = remove_style_of_string(
            note[content_field_name])


def remove_style_of_string(string):
    soup = BeautifulSoup(string)
    for tag in soup.find_all(True):
        for attr in ["style", "align", "valign"]:
            del tag[attr]
    return str(soup)


def add_cloze_style_tag_of_note(note):
    for content_field_name in CONTENT_FIELD_NAME_LIST:
        note[content_field_name] = add_cloze_style_tag_of_string(
            note[content_field_name])


def add_cloze_style_tag_of_string(string):
    string = re.sub(
        r'(?<!<span class=[\"\']cloze-in-editor[\"\']>)(\{\{c\d+::[\s\S]*?\}\})', '<span class="cloze-in-editor">\g<1></span>', string)
    return string


def remove_cloze_style_tag(string):
    # string = re.sub(
    #     r'<span class="cloze-in-editor">(\{\{c\d+::)([\s\S]*?)\}\}</span>', '\g<1>\g<2>}}', string)
    soup = BeautifulSoup(string)
    for tag in soup.find_all('span', class_="cloze-in-editor"):
        tag.unwrap()
    return str(soup)


def rebuild_fields_in_editor(self):
    note = self.note
    if not note or not check_model(note.model()):
        return
    generate_enhanced_cloze(note)
    self.mw.progress.timer(100, self.loadNote, False)


def empty_generated_fields(self):
    note = self.note
    if not note or not check_model(note.model()):
        return
    for i_cloze_field_number in range(1, MAX_CLOZE_FIELD_NUMBER + 1):
        dest_field_name = "Cloze%s" % i_cloze_field_number
        note[dest_field_name] = ""
    self.mw.progress.timer(100, self.loadNote, False)


def setup_buttons(self):
    b = self._addButton(
        "Process editor", lambda: self.process_note_in_editor(),
        text="[P]", size=False, tip="Process editor", key="Ctrl+Shift+P"
    )
    b.setFixedWidth(24)
    b = self._addButton(
        "Rebuild Fields", lambda: self.rebuild_fields_in_editor(),
        text="[R]", size=False, tip="Rebuild Fields", key="Ctrl+Shift+R"
    )
    b.setFixedWidth(24)
    b = self._addButton(
        "Empty Fields", lambda: self.empty_generated_fields(),
        text="[E]", size=False, tip="Empty Fields", key="Ctrl+Shift+E"
    )
    b.setFixedWidth(24)


def on_browser_close_event(self, evt):
    update_all_enhanced_clozes_in_browser(self)


AddCards.addCards = wrap(AddCards.addCards, on_add_cards, "around")
EditCurrent.onSave = wrap(EditCurrent.onSave, on_edit_current_save, "around")
# Editor.saveNow = wrap(Editor.saveNow, on_save_now, "before")

setup_menu(aqt.mw)
addHook("browser.setupMenus", setup_menu_in_browser)

Editor.process_note_in_editor = process_note_in_editor
Editor.rebuild_fields_in_editor = rebuild_fields_in_editor
Editor.empty_generated_fields = empty_generated_fields
Editor.setupButtons = wrap(Editor.setupButtons, setup_buttons, "after")

# Browser.closeEvent = wrap(Browser.closeEvent, on_browser_close_event, "before")
