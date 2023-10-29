"""
- With min changes to main code base, implementing mouse free select handling using clipboard window.

- Vishweshwar Saran Singh Deo vssdeo@gmail.com
"""

import gi
gi.require_version('Vte', '2.91')  # vte-0.38 (gnome-3.14)
from gi.repository import Gtk, Gdk, Vte

from terminatorlib.terminator import Terminator

from terminatorlib.config import Config
import terminatorlib.plugin as plugin
from terminatorlib.plugin import KeyBindUtil

from terminatorlib.util import err, dbg, gerr
from terminatorlib import regex

import re


AVAILABLE = ['MouseFreeKeyTextSelect']

PluginKbSelActKeyUp = "plugin_kbsel_key_up"
PluginKbSelActKeyDn = "plugin_kbsel_key_dn"
PluginKbSelActEsc   = "plugin_kbsel_esc"
# we use the same as in terminal for consistency
PluginKbSelActCp    = "copy"


PluginKbSelKeyUp = "Plugin Select Text Up"
PluginKbSelKeyDn = "Plugin Select Text Dn"
PluginKbSelEsc   = "Plugin Clear/Esc Selected Text"
PluginKbSelCp    = "Plugin Copy Selected Text"

PluginKbSelLabelDesc =  "(Read-Only) Copy Paste Clipboard Buffer\
   Select: %s   Copy: %s   Cancel: %s"


class MouseFreeKeyTextSelect(plugin.Plugin):
    from_column = 0
    from_row    = 0
    to_column   = 0
    to_row      = 0
    vte         = None
    select_on   = False
    terminal    = None

    config      = Config()
    keyb        = KeyBindUtil(config)

    def __init__(self):

        self.connect_signals()

        self.keyb.bindkey_check_config(
                [PluginKbSelKeyUp , PluginKbSelActKeyUp, "<Shift>Up"])
        self.keyb.bindkey_check_config(
                [PluginKbSelKeyDn , PluginKbSelActKeyDn, "<Shift>Down"])

    def connect_signals(self):
        self.windows = Terminator().get_windows()
        for window in self.windows:
            window.connect('key-press-event', self.on_keypress)

    def unload(self):
        for window in self.windows:
            window.disconnect_by_func(self.on_keypress)

    def get_term(self):
        return  Terminator().last_focused_term

    def close_select_text(self):
        self.select_on = False
        dbg("select_start: %s" % self.select_on)
        self.window.close()

    def start_select_text(self):
        dbg("start select text")
        self.select_on = True

        self.terminal = self.get_term()
        self.vte = self.get_term().get_vte()

        window = Gtk.Window()

        # these won't be shown in keybindings as these are enabled
        # when clipboard buffer window is show, we could create a
        # local copy of keybind

        self.keyb.bindkey_check_config(
                [PluginKbSelEsc , PluginKbSelActEsc,"Escape"])
        self.keyb.bindkey_check_config(
                [PluginKbSelCp, PluginKbSelActCp, "<Control><Shift>c"])

        # get key-combo for copy action
        cp_key_str =  self.keyb.get_act_to_keys_config(PluginKbSelActCp)
        sel_up_str =  self.keyb.get_act_to_keys(PluginKbSelActKeyUp)
        sel_dn_str =  self.keyb.get_act_to_keys(PluginKbSelActKeyDn)
        sel_esc_str = self.keyb.get_act_to_keys(PluginKbSelActEsc)

        title = PluginKbSelLabelDesc % ( sel_up_str +
                            "/" + sel_dn_str, cp_key_str, sel_esc_str)
        window_frame = Gtk.Frame(label=title)
        window_frame.modify_bg(Gtk.StateType.NORMAL, Gdk.color_parse("red"))

        window.add(window_frame)

        window.set_title("Clipboard ~ Copy Paste")
        (width, height) = self.terminal.get_toplevel().get_size()
        window.set_default_size(width, height)

        parent_x, parent_y = self.terminal.get_toplevel().get_position()
        window.move(parent_x + 50, parent_y)

        scrolled_win = Gtk.ScrolledWindow()
        window_frame.add(scrolled_win)


        self.from_column, self.from_row = (0,0)
        self.to_column, self.to_row     = self.vte.get_cursor_position()

        #dbg("text to %s %s" % (self.to_column, self.to_row))
        txtbuf = Gtk.TextBuffer()
        txt = self.vte.get_text_range_format(Vte.Format.TEXT,
                                             self.from_row, self.from_column,
                                             self.to_row,   self.to_column)[0]
        txtbuf.set_text(txt)

        textview = Gtk.TextView.new_with_buffer(txtbuf)
        textview.connect('copy-clipboard',  self.on_copy_clipboard)
        textview.connect('key-press-event', self.on_clipboard_keypress)
        textview.set_editable(False)
        textview.set_monospace(True)

        it_end = txtbuf.get_end_iter()
        mark_end = txtbuf.create_mark("", it_end, False)
        textview.scroll_to_mark(mark_end, 0, False, 0, 0)

        textview.grab_focus()

        agr = Gtk.AccelGroup()
        window.add_accel_group(agr)
        act_str = self.keyb.get_all_act_to_keys()[PluginKbSelActCp]
        dbg("action string: %s" % act_str)
        key, mod = Gtk.accelerator_parse("<Shift><Control>c")
        textview.add_accelerator("copy-clipboard",
                    agr, key, mod, Gtk.AccelFlags.VISIBLE)

        scrolled_win.add(textview)

        window.show_all()
        self.textview = textview
        self.window   = window

    def on_copy_clipboard(self, widget):
        self.window.close()
        self.textview = None
        self.window   = None

    #buffer window event handler
    def on_clipboard_keypress(self, widget, event):
        act = self.keyb.keyaction(event)
        dbg("clipboard keyaction: (%s) (%s)" % (str(act), event.keyval))
        if act == PluginKbSelActEsc:
            self.close_select_text()

        if act == PluginKbSelActCp:
            pass

    #plugin keypress handler
    def on_keypress(self, widget, event):
        act = self.keyb.keyaction(event)
        dbg("keyaction: (%s) (%s)" % (str(act), event.keyval))

        if act == PluginKbSelActKeyUp:
            self.start_select_text()
            return True

        if act == PluginKbSelActKeyDn:
            self.start_select_text()
            return True

        if act == PluginKbSelActEsc:
            self.close_select_text()
