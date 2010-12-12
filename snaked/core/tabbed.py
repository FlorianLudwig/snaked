import time
import weakref

import gtk

from snaked.core.shortcuts import ContextShortcutActivator, register_shortcut
import snaked.core.manager
import snaked.core.editor

class TabbedEditorManager(snaked.core.manager.EditorManager):
    def __init__(self, session):
        super(TabbedEditorManager, self).__init__(session)

        self.last_switch_time = None
        self.panels = weakref.WeakKeyDictionary()

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect('delete-event', self.on_delete_event)

        self.window.set_property('default-width', 800)
        self.window.set_property('default-height', 500)

        self.activator = ContextShortcutActivator(self.window, self.get_context)

        self.box = gtk.VBox()
        self.window.add(self.box)

        self.note = gtk.Notebook()
        self.note.set_show_tabs(self.snaked_conf['SHOW_TABS'])
        self.note.set_scrollable(True)
        self.note.set_property('tab-hborder', 10)
        self.note.set_property('homogeneous', False)
        self.note.connect_after('switch-page', self.on_switch_page)
        self.note.connect('page_removed', self.on_page_removed)
        self.note.connect('page_reordered', self.on_page_reordered)
        self.box.pack_start(self.note)

        register_shortcut('toggle-tabs-visibility', '<alt>F11', 'Window', 'Toggles tabs visibility')
        register_shortcut('next-editor', '<alt>Right', 'Window', 'Switches to next editor')
        register_shortcut('prev-editor', '<alt>Left', 'Window', 'Switches to previous editor')
        register_shortcut('next-editor-alt', '<ctrl>Page_Down', 'Window', 'Switches to next editor')
        register_shortcut('prev-editor-alt', '<ctrl>Page_Up', 'Window', 'Switches to previous editor')
        register_shortcut('fullscreen', 'F11', 'Window', 'Toggles fullscreen mode')

        register_shortcut('toggle-console', '<alt>grave', 'Window', 'Toggles console')


        if self.snaked_conf['RESTORE_POSITION'] and 'LAST_POSITION' in self.snaked_conf:
            pos, size = self.snaked_conf['LAST_POSITION']
            self.window.move(*pos)
            self.window.resize(*size)

        self.window.show_all()

        if self.snaked_conf['FULLSCREEN']:
            self.window.fullscreen()

    def get_context(self):
        widget = self.note.get_nth_page(self.note.get_current_page())
        for e in self.editors:
            if e.widget is widget:
                return (e,)

        return (None,)

    def manage_editor(self, editor):
        label = gtk.Label('Unknown')
        self.note.insert_page(editor.widget, label, -1)
        self.note.set_tab_reorderable(editor.widget, True)
        self.focus_editor(editor)
        editor.view.grab_focus()

    def focus_editor(self, editor):
        idx = self.note.page_num(editor.widget)
        self.note.set_current_page(idx)

    def update_top_level_title(self):
        idx = self.note.get_current_page()
        if idx < 0:
            return

        editor = self.get_context()[0]
        if editor:
            title = editor.get_window_title.emit()

        if not title:
            title = self.note.get_tab_label_text(self.note.get_nth_page(idx))

        if title is not None:
            self.window.set_title(title)

    def set_editor_title(self, editor, title):
        self.note.set_tab_label_text(editor.widget, title)
        if self.note.get_current_page() == self.note.page_num(editor.widget):
            self.update_top_level_title()

    def on_delete_event(self, *args):
        self.quit(self.get_context()[0])

    def close_editor(self, editor):
        idx = self.note.page_num(editor.widget)
        self.note.remove_page(idx)
        editor.editor_closed.emit()

    def set_editor_shortcuts(self, editor):
        self.plugin_manager.bind_shortcuts(self.activator, editor)

        if hasattr(self, 'editor_shortcuts_binded'):
            return

        self.editor_shortcuts_binded = True

        self.activator.bind_to_name('quit', self.quit)
        self.activator.bind_to_name('close-window', self.close_editor)
        self.activator.bind_to_name('save', self.save)
        self.activator.bind_to_name('next-editor', self.switch_to, 1)
        self.activator.bind_to_name('prev-editor', self.switch_to, -1)
        self.activator.bind_to_name('next-editor-alt', self.switch_to, 1)
        self.activator.bind_to_name('prev-editor-alt', self.switch_to, -1)
        self.activator.bind_to_name('new-file', self.new_file_action)
        self.activator.bind_to_name('show-preferences', self.show_preferences)
        self.activator.bind_to_name('fullscreen', self.fullscreen)
        self.activator.bind_to_name('toggle-tabs-visibility', self.toggle_tabs)

        self.activator.bind_to_name('place-spot', self.add_spot_with_feedback)
        self.activator.bind_to_name('goto-last-spot', self.goto_last_spot)
        self.activator.bind_to_name('goto-next-spot', self.goto_next_prev_spot, True)
        self.activator.bind_to_name('goto-prev-spot', self.goto_next_prev_spot, False)

        self.activator.bind_to_name('toggle-console', self.toggle_console)

        self.activator.bind('Escape', self.process_escape)

    def quit(self, editor):
        self.snaked_conf['LAST_POSITION'] = self.window.get_position(), self.window.get_size()

        self.window.hide()
        super(TabbedEditorManager, self).quit(editor)

    def save(self, editor):
        editor.save()

    def set_transient_for(self, editor, window):
        window.set_transient_for(self.window)

    def on_switch_page(self, *args):
        self.update_top_level_title()

    def on_page_removed(self, note, child, idx):
        for e in self.editors:
            if e.widget is child:
                spot = self.get_last_spot(None, e)
                if spot:
                    note.set_current_page(note.page_num(spot.editor().widget))
                    return

        if idx > 0:
            note.set_current_page(idx - 1)

    def switch_to(self, editor, dir):
        if self.last_switch_time is None or time.time() - self.last_switch_time > 5:
            self.add_spot(editor)

        self.last_switch_time = time.time()

        idx = ( self.note.get_current_page() + dir ) % self.note.get_n_pages()
        self.note.set_current_page(idx)

    def fullscreen(self, editor):
        self.snaked_conf['FULLSCREEN'] = not self.snaked_conf['FULLSCREEN']
        if self.snaked_conf['FULLSCREEN']:
            self.window.fullscreen()
        else:
            self.window.unfullscreen()

    def toggle_tabs(self, editor):
        self.note.set_show_tabs(not self.note.get_show_tabs())
        self.snaked_conf['SHOW_TABS'] = self.note.get_show_tabs()

    @snaked.core.editor.Editor.stack_add_request
    def on_stack_add_request(self, editor, widget, on_popup):
        self.panels[widget] = on_popup
        self.box.pack_end(widget, False, False)

    @snaked.core.editor.Editor.stack_popup_request
    def on_stack_popup_request(self, editor, widget):
        if widget in self.panels:
            for w in self.panels:
                if w is not widget:
                    w.hide()

            widget.show()

            _, _, _, wh, _ = self.window.window.get_geometry()
            w, _ = widget.get_size_request()
            h = max(200, wh/3)
            widget.set_size_request(w, h)

            if self.panels[widget]:
                self.panels[widget](widget, editor)

    def toggle_console(self, editor):
        from snaked.core.console import toggle_console
        toggle_console(editor)

    def on_page_reordered(self, note, child, num):
        for i, e in enumerate(self.editors):
            if e.widget is child:
                self.editors[i], self.editors[num] = self.editors[num], self.editors[i]
                break