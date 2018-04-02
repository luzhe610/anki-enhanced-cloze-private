# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from aqt.qt import *

from aqt import mw
from aqt.addcards import AddCards
from aqt.browser import Browser
from aqt.editcurrent import EditCurrent
from aqt.editor import Editor
from aqt.utils import tooltip
from anki.hooks import addHook, wrap

from Add_note_id import id_fields

import bs4


# global variables
genuine_cloze_answer_array = []
genuine_cloze_hint_array = []
pseudo_cloze_answer_array = []
pseudo_cloze_hint_array = []
filling_cloze_field_number = 0

# constants
CONTENT_FIELD_NAME_1 = "# Content 1"
CONTENT_FIELD_NAME_2 = "# Content 2"
CONTENT_FIELD_NAME_3 = "# Content 3"
CONTENT_FIELD_NAME_4 = "# Content 4"
CONTENT_FIELD_NAME_5 = "# Content 5"
CONTENT_FIELD_NAME_LIST = [CONTENT_FIELD_NAME_1, CONTENT_FIELD_NAME_2,
                           CONTENT_FIELD_NAME_3, CONTENT_FIELD_NAME_4, CONTENT_FIELD_NAME_5]

IN_USE_CLOZES_FIELD_NAME = "In-use Clozes"
MAX_CLOZE_FIELD_NUMBER = 100


def update_cloze_fields(note):
    # cloze_id like c1, cloze_number like 1
    src_content = ""
    for content_field_name in CONTENT_FIELD_NAME_LIST:
        content_field_content = note[content_field_name]
        src_content += '<div id="content-{}" class="content-block">{}</div>'.format(
            re.search(r'\d+', content_field_name).group(), content_field_content)

    src_content = remove_cloze_wrapper_of_string(src_content)

    cloze_start_regex = r"\{\{c\d+::"
    cloze_start_matches = re.findall(cloze_start_regex, src_content)

    if not cloze_start_matches:
        for cloze_field_number in range(1, MAX_CLOZE_FIELD_NUMBER + 1):
            dest_field_name = "Cloze{}".format(cloze_field_number)
            note[dest_field_name] = ""

        note[IN_USE_CLOZES_FIELD_NAME] = "[0]"

        # Anki will warn if cloze notes include no cloze or more strictly, no single-line cloze
        # so I use a invisible single-line cloze {{cX::@@@@}} to cheat Anki :)
        note["Cloze1"] = src_content + \
            '<div style="display:none">{{c1::@@@@}}</div>' + \
            '<div id="card-cloze-id" style="display:none">c0</div>'
    else:
        in_use_clozes_numbers = sorted(
            [int(re.search(r"\d+", x).group()) for x in set(cloze_start_matches)])
        note[IN_USE_CLOZES_FIELD_NAME] = unicode(str(in_use_clozes_numbers))

        # Fill in content in in-use cloze fields and empty content in not-in-use fields
        global filling_cloze_field_number
        for filling_cloze_field_number in range(1, MAX_CLOZE_FIELD_NUMBER + 1):

            dest_field_name = "Cloze{}".format(filling_cloze_field_number)

            if not filling_cloze_field_number in in_use_clozes_numbers:
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

                cloze_regex = r"\{\{c\d+::[\s\S]*?\}\}"
                dest_field_content = re.sub(
                    cloze_regex, process_cloze, src_content)

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

                dest_field_content += '<div style="display:none">{{c%s::@@@@}}</div>' % (
                    filling_cloze_field_number)
                dest_field_content += '<div id="card-cloze-id" style="display:none">c{}</div>'.format(
                    filling_cloze_field_number)
            note[dest_field_name] = dest_field_content


def check_model(model):
    return re.search("Enhanced Cloze", model["name"])


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

    global filling_cloze_field_number
    if cloze_id != 'c' + str(filling_cloze_field_number):
        # Process pseudo-cloze
        global pseudo_cloze_answer_array
        global pseudo_cloze_hint_array
        pseudo_cloze_answer_array.append(answer)
        pseudo_cloze_hint_array.append(hint)
        index_in_array = len(pseudo_cloze_answer_array) - 1
        new_html = '<lz-cloze class="pseudo-cloze" index="{}" show-state="hint" cloze-id="{}">{}</lz-cloze>'.format(
            index_in_array, cloze_id, cloze_string.replace("{{", '[[').replace("}}", "]]"))
    else:
        # Process genuine-cloze
        global genuine_cloze_answer_array
        global genuine_cloze_hint_array
        genuine_cloze_answer_array.append(answer)
        genuine_cloze_hint_array.append(hint)
        index_in_array = len(genuine_cloze_answer_array) - 1
        new_html = '<lz-cloze class="genuine-cloze" index="{}" show-state="hint" cloze-id="{}">{}</lz-cloze>'.format(
            index_in_array,  cloze_id, cloze_string)
    return new_html


def on_save_now(self, _old):
    self.web.eval('saveFields("key")')
    note = self.note
    if not note or not check_model(note.model()):
        return _old(self)
    remove_style_attr_of_note(note)
    add_cloze_wrapper_of_note(note)
    update_cloze_fields(note)
    ret = _old(self)
    return ret


def update_all_enhanced_clozes_in_browser(browser):
    mw.checkpoint("Update Enhanced Clozes")
    mw.progress.start()
    browser.model.beginReset()

    update_all_enhanced_clozes()

    browser.model.endReset()
    mw.requireReset()
    mw.progress.finish()
    mw.reset()
    tooltip('Enhanced Clozed Updated!')


def update_all_enhanced_clozes_in_main_window():
    mw.checkpoint("Update Enhanced Clozes")
    mw.progress.start()

    update_all_enhanced_clozes()

    mw.requireReset()
    mw.progress.finish()
    mw.reset()
    tooltip('Enhanced Clozed Updated!')


def update_all_enhanced_clozes():
    nids = mw.col.findNotes("*")
    for nid in nids:
        note = mw.col.getNote(nid)
        if not check_model(note.model()):
            continue
        remove_style_attr_of_note(note)
        add_cloze_wrapper_of_note(note)
        update_cloze_fields(note)
        note.flush()


def setup_menu_in_browser(browser):
    setup_menu(browser)


def setup_menu(window):
    try:
        menu = window.form.menuUtilities
    except:
        window.form.menuUtilities = QMenu("&Utilities", window.form.menubar)
        menu = window.form.menuUtilities
        window.form.menubar.addMenu(menu)
    a = menu.addAction('&Update Enhanced Clozes')
    # a.setShortcut(QKeySequence("Ctrl+Alt+Shift+U"))
    if window == mw:
        a.triggered.connect(update_all_enhanced_clozes_in_main_window)
    else:
        a.triggered.connect(
            lambda _, b=window: update_all_enhanced_clozes_in_browser(b))


def remove_style_attr_of_note(note):
    for content_field_name in CONTENT_FIELD_NAME_LIST:
        note[content_field_name] = remove_style_attr_of_string(
            note[content_field_name])


def remove_style_attr_of_string(string):
    soup = bs4.BeautifulSoup(string)
    for tag in soup.find_all(True):
        for attr in ['style']:
            del tag[attr]
    # string = re.sub(
    #     r"(<[^>]*?)(style\s*?=\s*?(?P<quot>[\"\'])[\s\S]*?(?P=quot))([\s\S]*?>)", "\g<1>\g<4>", string)
    return unicode(soup)


def add_cloze_wrapper_of_note(note):
    for content_field_name in CONTENT_FIELD_NAME_LIST:
        note[content_field_name] = add_cloze_wrapper_of_string(
            note[content_field_name])


def add_cloze_wrapper_of_string(string):
    string = re.sub(
        r"(?<!<lz-cloze>)(\{\{c\d+::[\s\S]*?\}\})(?!</lz-cloze>)", "<lz-cloze>\g<1></lz-cloze>", string)
    return string


def remove_cloze_wrapper_of_string(string):
    string = re.sub(r"</?lz-cloze>", "", string)
    return string


def process_content_fields(editor):
    editor.web.eval("saveField('key');")
    note = editor.note
    if not note or not check_model(note.model()):
        return
    remove_style_attr_of_note(note)
    add_cloze_wrapper_of_note(note)
    editor.loadNote()
    editor.web.eval("focusField(%d);" % editor.currentField)
    # mw.progress.timer(100, editor.loadNote, False)


def empty_cloze_fields(editor):
    editor.web.eval("saveField('key');")
    note = editor.note
    if not note or not check_model(note.model()):
        return
    for cloze_field_number in range(1, MAX_CLOZE_FIELD_NUMBER + 1):
        dest_field_name = "Cloze{}".format(cloze_field_number)
        note[dest_field_name] = ""
    editor.loadNote()
    editor.web.eval("focusField(%d);" % editor.currentField)


def remove_cloze_wrapper(editor):
    editor.web.eval("saveField('key');")
    note = editor.note
    if not note or not check_model(note.model()):
        return
    for content_field_name in CONTENT_FIELD_NAME_LIST:
        note[content_field_name] = remove_cloze_wrapper_of_string(
            note[content_field_name])
    editor.loadNote()
    editor.web.eval("focusField(%d);" % editor.currentField)


def setup_buttons(editor):
    PROCESS_CONTENT_FIELDS_KEY = "Ctrl+Shift+A"
    b = editor._addButton("Process content fields", lambda edt=editor: process_content_fields(
        edt), text="[A]", size=True, tip="Process content fields<br>({})".format(_(PROCESS_CONTENT_FIELDS_KEY)), key=(PROCESS_CONTENT_FIELDS_KEY))
    b.setFixedWidth(30)

    REMOVE_CLOZE_WRAPPER_KEY = "Ctrl+Shift+R"
    b = editor._addButton("Remove cloze wrapper", lambda edt=editor: remove_cloze_wrapper(
        edt), text="[R]", size=True, tip="Remove cloze wrapper<br>({})".format(_(REMOVE_CLOZE_WRAPPER_KEY)), key=_(REMOVE_CLOZE_WRAPPER_KEY))
    b.setFixedWidth(30)

    EMPTY_CLOZE_FIELDS_KEY = "Ctrl+Shift+E"
    b = editor._addButton("Empty cloze fields", lambda edt=editor: empty_cloze_fields(
        edt), text="[E]", size=True, tip="Empty cloze fields<br>({})".format(_(EMPTY_CLOZE_FIELDS_KEY)), key=_(EMPTY_CLOZE_FIELDS_KEY))
    b.setFixedWidth(30)


def on_browser_close(self, evt):
    update_all_enhanced_clozes_in_browser(self)


def on_edit_focus_lost(flag, note, fidx):
    field_names = mw.col.models.fieldNames(note.model())
    field_name = field_names[fidx]
    if field_name in id_fields:
        return flag
    if note[field_name] == '':
        return flag
    soup = bs4.BeautifulSoup(note[field_name])
    if soup.get_text() == '':
        note[field_name] = ''
        return True
    return flag


Editor.saveNow = wrap(Editor.saveNow, on_save_now, "around")
addHook('editFocusLost', on_edit_focus_lost)
addHook("setupEditorButtons", setup_buttons)

# Main window and browser menu
setup_menu(mw)
addHook("browser.setupMenus", setup_menu_in_browser)
