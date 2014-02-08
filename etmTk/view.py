#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
#import the 'tkinter' module
import os
import re
from copy import deepcopy
import subprocess
from dateutil.tz import tzlocal
import codecs

import logging
import logging.config
logger = logging.getLogger()

import platform

if platform.python_version() >= '3':
    import tkinter
    from tkinter import Tk, Entry, INSERT, END, Label, Toplevel, Button, Frame, LEFT, Text, PanedWindow, OptionMenu, StringVar, IntVar, Menu, BooleanVar, ACTIVE, Radiobutton, W
    # from tkinter import messagebox as tkMessageBox
    from tkinter import ttk
    from tkinter import font as tkFont
    from tkinter.messagebox import askokcancel
    from tkinter.filedialog import askopenfilename
    # from tkinter import simpledialog as tkSimpleDialog
    # import tkFont
else:
    import Tkinter as tkinter
    from Tkinter import Tk, Entry, INSERT, END, Label, Toplevel, Button, Frame, LEFT, Text, PanedWindow, OptionMenu, StringVar, IntVar, Menu, BooleanVar, ACTIVE, Radiobutton, W
    # import tkMessageBox
    import ttk
    import tkFont
    from tkMessageBox import askokcancel
    from tkFileDialog import askopenfilename
    # import tkSimpleDialog

tkversion = tkinter.TkVersion

import etmTk.data as data
# from data import init_localization

from dateutil.parser import parse

from etmTk.data import (
    init_localization, fmt_weekday, fmt_dt, hsh2str, leadingzero, parse_datetime, s2or3, send_mail, send_text, fmt_period, get_changes, checkForNewerVersion, datetime2minutes, calyear, expand_template, sys_platform, id2Type, get_current_time, mac, setup_logging, uniqueId, gettz, platformShortcut, bgclr, rrulefmt)

from etmTk.edit import SimpleEditor

import gettext

_ = gettext.gettext

# used in hack to prevent dialog from hanging under os x
if mac:
    AFTER = 100
else:
    AFTER = 1

from idlelib.WidgetRedirector import WidgetRedirector

from datetime import datetime, timedelta

ONEMINUTE = timedelta(minutes=1)
ONEHOUR = timedelta(hours=1)
ONEDAY = timedelta(days=1)
ONEWEEK = timedelta(weeks=1)

STOPPED = _('stopped')
PAUSED = _('paused')
RUNNING = _('running')

AGENDA = _('agenda')
SCHEDULE = _('schedule')
PATHS = _('paths')
KEYWORDS = _('keywords')
TAGS = _('tags')


class Timer():
    def __init__(self):
        """

        """
        self.timer_delta = 0 * ONEMINUTE
        self.timer_active = False
        self.timer_status = STOPPED
        self.timer_last = None
        self.timer_hsh = None
        self.timer_summary = None


    def timer_start(self, hsh=None):
        if not hsh: hsh = {}
        self.timer_hsh = hsh
        text = hsh['_summary']
        if len(text) > 10:
            self.timer_summary = "{0}~".format(text[:9])
        else:
            self.timer_summary = text
        self.timer_toggle(self.timer_hsh)

    def timer_finish(self, create=True):
        if self.timer_status == STOPPED:
            return ()
        if self.timer_status == RUNNING:
            self.timer_delta += datetime.now() - self.timer_last

        self.timer_delta = max(self.timer_delta, ONEMINUTE)
        self.timer_status = STOPPED
        self.timer_last = None

    def timer_toggle(self, hsh=None):
        if not hsh: hsh = {}
        if self.timer_status == STOPPED:
            self.timer_delta = timedelta(seconds=0)
            self.timer_last = datetime.now()
            self.timer_status = RUNNING
        elif self.timer_status == RUNNING:
            self.timer_delta += datetime.now() - self.timer_last
            self.timer_status = PAUSED
        elif self.timer_status == PAUSED:
            self.timer_status = RUNNING
            self.timer_last = datetime.now()

    def get_time(self):
        if self.timer_status == PAUSED:
            elapsed_time = self.timer_delta
        elif self.timer_status == RUNNING:
            elapsed_time = (self.timer_delta + datetime.now() -
                       self.timer_last)
        else:
            elapsed_time = 0 * ONEMINUTE
        plus = ""
        self.timer_minutes = elapsed_time.seconds//60
        if self.timer_status == RUNNING:
            plus = "+"
        # ret = "{0}  {1}{2}".format(self.timer_summary, self.timer_time, s)
        ret = "{0}  {1}{2}".format(self.timer_summary, fmt_period(elapsed_time), plus)
        logger.debug("timer: {0}; {1}; {2}".format(ret, self.timer_last, elapsed_time))
        return ret


class ReadOnlyText(Text):
    # noinspection PyShadowingNames
    def __init__(self, *args, **kwargs):
        Text.__init__(self, *args, **kwargs)
        self.redirector = WidgetRedirector(self)
        self.insert = self.redirector.register("insert", lambda *args, **kw: "break")
        self.delete = self.redirector.register("delete", lambda *args, **kw: "break")
        self.configure(highlightthickness=0)


class MessageWindow():
    # noinspection PyShadowingNames
    def __init__(self, parent, title, prompt):
        self.win = Toplevel(parent)
        self.parent = parent
        self.win.title(title)
        Label(self.win, text=prompt).pack(fill=tkinter.BOTH, expand=1, padx=10, pady=10)
        b = Button(self.win, text=_('OK'), width=10, command=self.cancel,
                   default='active')
        b.pack()
        self.win.bind('<Return>', (lambda e, b=b: b.invoke()))
        self.win.bind('<Escape>', (lambda e, b=b: b.invoke()))
        self.win.focus_set()
        self.win.grab_set()
        self.win.transient(parent)
        self.win.wait_window(self.win)
        return

    def cancel(self, event=None):
        # put focus back to the parent window
        self.parent.focus_set()
        self.win.destroy()


class Dialog(Toplevel):
    def __init__(self, parent, title=None, prompt=None, opts=None, default=None):

        Toplevel.__init__(self, parent)
        self.transient(parent)

        if title:
            self.title(title)

        self.parent = parent
        self.prompt = prompt
        self.options = opts
        self.default = default
        self.value = None

        self.error_message = None

        self.buttonbox()

        body = Frame(self)
        self.initial_focus = self.body(body)
        body.pack(side="top", padx=5, pady=5)

        # self.buttonbox()

        self.grab_set()

        if not self.initial_focus:
            self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50,
                                  parent.winfo_rooty() + 50))

        self.initial_focus.focus_set()

        self.wait_window(self)

    # construction hooks

    def body(self, master):
        # create dialog body.  return widget that should have
        # initial focus.  this method should be overridden

        pass

    def buttonbox(self):
        # add standard button box. override if you don't want the
        # standard buttons

        box = Frame(self)

        w = Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=LEFT, padx=5, pady=5)
        w = Button(box, text="OK", width=10, command=self.ok, default=ACTIVE)
        w.pack(side=LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack(side='bottom')

    # standard button semantics

    def ok(self, event=None):
        if not self.validate():
            if self.error_message:
                self.messageWindow('error', self.error_message)
            self.initial_focus.focus_set()  # put focus back
            return

        self.withdraw()
        self.update_idletasks()

        self.apply()

        self.cancel()

    def cancel(self, event=None):

        # put focus back to the parent window
        self.parent.focus_set()
        self.destroy()

    #
    # command hooks

    def validate(self):

        return 1 # override

    def apply(self):

        pass # override

    def messageWindow(self, title, prompt):
        MessageWindow(self.parent, title, prompt)


class DialogWindow(Dialog):
    # master will be a frame in Dialog
    # noinspection PyAttributeOutsideInit
    def body(self, master):
        self.entry = Entry(master)
        self.entry.pack(side="bottom", padx=5, pady=5)
        Label(master, text=self.prompt, justify='left').pack(side="top",
                                                             fill=tkinter.BOTH, expand=1,
                                                             padx=10, pady=5)
        if self.default is not None:
            self.entry.insert(0, self.default)
            self.entry.select_range(0, END)
            # self.entry.pack(padx=5, pady=5)
        return self.entry

class TextDialog(Dialog):

    def body(self, master):
        self.text = ReadOnlyText(
            master, wrap="word", padx=2, pady=2, bd=2, relief="sunken",
            font=tkFont.Font(family="Lucida Sans Typewriter"),
            height=14,
            width=52,
            takefocus=False)
        self.text.insert("1.1", self.prompt)
        self.text.pack(side='left', fill=tkinter.BOTH, expand=1, padx=0,
                       pady=0)
        ysb = ttk.Scrollbar(master, orient='vertical', command=self.text
                            .yview,
                            width=8)
        ysb.pack(side='right', fill=tkinter.Y, expand=0, padx=0, pady=0)
        # t.configure(state="disabled", yscroll=ysb.set)
        self.text.configure(yscroll=ysb.set)

    def buttonbox(self):
        # add standard button box. override if you don't want the
        # standard buttons

        box = Frame(self)

        w = Button(box, text="OK", width=10, command=self.cancel,
                   default=ACTIVE)
        w.pack(side=LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.ok)

        box.pack(side='bottom')



class OptionsDialog():
    # noinspection PyShadowingNames
    def __init__(self, parent, title="", prompt="", opts=None):
        if not opts: opts = []
        self.win = Toplevel(parent)
        self.parent = parent
        self.options = opts
        self.value = opts[0]
        self.win.title(title)
        Label(self.win, text=prompt, justify='left').pack(fill=tkinter.BOTH, expand=1, padx=10, pady=5)
        # self.sv = StringVar(parent)
        self.sv = IntVar(parent)
        # self.sv.set(opts[0])
        self.sv.set(1)
        # logger.debug('sv: {0}'.format(self.sv.get()))
        for i in range(min(9, len(self.options))):
            txt = self.options[i]
            val = i + 1
            # bind keyboard numbers 1-9 (at most) to options selection, i.e., press 1
            # to select option 1, 2 to select 2, etc.
            self.win.bind(str(val), (lambda e, x=val: self.sv.set(x)))
            Radiobutton(self.win,
                text="{0}: {1}".format(val, txt),
                padx=20,
                indicatoron=True,
                variable=self.sv,
                command=self.getValue,
                value=val).pack(padx=10, anchor=W)
        box = Frame(self.win)
        c = Button(box, text="Cancel", width=10, command=self.cancel)
        c.pack(side=LEFT, padx=5, pady=5)
        o = Button(box, text="OK", width=10, default='active', command=self.ok)
        o.pack(side=LEFT, padx=5, pady=5)
        box.pack()
        self.win.bind('<Return>', (lambda e, o=o: o.invoke()))
        self.win.bind('<Escape>', (lambda e, c=c: c.invoke()))
        # self.choice.focus_set()
        self.win.focus_set()
        self.win.grab_set()
        # self.choice.focus()
        self.win.transient(parent)
        self.win.wait_window(self.win)

    def getValue(self, e=None):
        v = self.sv.get()
        logger.debug(v)
        if v-1 in range(len(self.options)):
            o = self.options[v-1]
            logger.debug('OptionsDialog returning {0}: {1}'.format(v, o))
            return v, o
            # return o, v
        else:
            return 0, None

    def ok(self, event=None):
        self.parent.update_idletasks()
        self.quit()

    def cancel(self, event=None):
        self.sv.set(0)
        self.quit()

    def quit(self, event=None):
        # put focus back to the parent window
        self.parent.focus_set()
        self.win.destroy()


class GetInteger(DialogWindow):
    def validate(self):
        # print('integer validate', self.options)
        minvalue = maxvalue = None
        if len(self.options) > 0:
            minvalue = self.options[0]
            if len(self.options) > 1:
                maxvalue = self.options[1]
        res = self.entry.get()
        try:
            val = int(res)
            ok = (minvalue is None or val >= minvalue) and (
                maxvalue is None or val <= maxvalue)
        except:
            val = None
            ok = False

        if ok:
            self.value = val
            return True
        else:
            self.value = None
            msg = [_('an integer')]
            conj = ""
            if minvalue is not None:
                msg.append(_("no less than {0}".format(minvalue)))
                conj = _("and ")
            if maxvalue is not None:
                msg.append(_("{0}no greater than {0}").format(conj, maxvalue))
            msg.append(_("is required"))
            self.error_message = "\n".join(msg)
            return False


class GetDateTime(DialogWindow):
    def validate(self):
        res = self.entry.get()
        ok = False
        if not res.strip():
            # return the current time if ok is pressed with no entry
            val = get_current_time()
            ok = True
        else:
            try:
                val = parse(parse_datetime(res))
                ok = True
            except:
                val = None
        if ok:
            self.value = val
            return True
        else:
            self.value = False
            self.error_message = _('could not parse "{0}"').format(res)
            return False


class GetString(DialogWindow):
    def validate(self):
        notnull = False
        if 'notnull' in self.options and self.options['notnull']:
            notnull = True
            # an entry is required
        val = self.entry.get()
        ok = False
        if val.strip():
            self.value = val
            return True
        elif notnull:
            self.error_message = _('an entry is required')
            return False
        else:  # null and null is ok
            self.value = None
            return True


class App(Tk):
    def __init__(self, path=None):
        Tk.__init__(self)
        # minsize: width, height
        self.minsize(430, 450)
        self.uuidSelected = None
        self.timerItem = None
        self.actionTimer = Timer()
        self.loop = loop
        self.configure(background=bgclr)
        menubar = Menu(self)

        # File menu
        filemenu = Menu(menubar, tearoff=0)

        ## open file

        # openmenu = Menu(filemenu, tearoff=0)

        # filemenu.add_command(label=_("Recently changed ..."),
        #                      underline=0, command=self.donothing)

        filemenu.add_command(label=_("Data files ..."),
                             underline=0, command=self.editData)

        l, c = platformShortcut('O')
        filemenu.add_command(label=loop.options['config'], underline=0, command=lambda x=loop.options['config']: self.editFile(file=x), accelerator=l)
        # self.bind_all(c, lambda event: self.after(after, self.donothing))

        l, c = platformShortcut('C')
        filemenu.add_command(label=loop.options['auto_completions'], underline=0, command=lambda x=loop.options['auto_completions']: self.editFile(file=x), accelerator=l)

        l, c = platformShortcut('R')
        filemenu.add_command(label=loop.options['report_specifications'], underline=0, command=lambda x=loop.options['report_specifications']: self.editFile(file=x), accelerator=l)

        l, c = platformShortcut('S')
        filemenu.add_command(label=loop.options['scratchfile'], underline=0, command=lambda x=loop.options['scratchfile']: self.editFile(file=x), accelerator=l)

        filemenu.add_separator()

        # report
        l, c = platformShortcut('m')
        filemenu.add_command(label=_("Make report"), accelerator=l, underline=1,
                             command=self.donothing)
        self.bind(c, self.donothing)  # m

        ## export
        l, c = platformShortcut('x')
        filemenu.add_command(label="Export ...", underline=1, command=self.donothing, accelerator=l)
        self.bind(c, self.donothing)  # x

        filemenu.add_separator()

        ## quit
        l, c = platformShortcut('w')
        filemenu.add_command(label="Quit", underline=0, command=self.quit)
        self.bind(c, self.quit)  # w
        menubar.add_cascade(label="File", underline=0, menu=filemenu)

        # view menu
        viewmenu = Menu(menubar, tearoff=0)

        calendarmenu = Menu(viewmenu, tearoff=0)
        self.calendars = deepcopy(loop.options['calendars'])

        logger.debug('Calendars: {0}'.format([x[:2] for x in self.calendars]))
        self.calendarValues = []
        for i in range(len(self.calendars)):
            # logger.debug('Adding calendar: {0}'.format(self.calendars[i][:2]))
            self.calendarValues.append(BooleanVar())
            self.calendarValues[i].set(self.calendars[i][1])
            self.calendarValues[i].trace_variable("w", self.updateCalendars)
            calendarmenu.add_checkbutton(label=self.calendars[i][0], onvalue=True,
                                         offvalue=False, variable=self.calendarValues[i])

        if self.calendars:
            viewmenu.add_cascade(label=_("Choose active calendars"), menu=calendarmenu)
        else:
            viewmenu.add_cascade(label=_("Choose active calendars"), menu=calendarmenu,
                                 state="disabled")

        # go to date
        l, c = platformShortcut('g')
        viewmenu.add_command(
            label=_("Go to date"), underline=1, accelerator=l,
            command=self.goToDate)
        # needed for os x to prevent dialog hanging
        self.bind_all(c, lambda event: self.after(AFTER, self.goToDate))

        # expand to depth
        l, c = platformShortcut('o')
        viewmenu.add_command(
            label=_("Set outline depth"), underline=1, accelerator=l,
            command=self.expand2Depth)
        # needed for os x to prevent dialog hanging
        self.bind_all(c, lambda event: self.after(AFTER, self.expand2Depth))

        # busy times
        l, c = platformShortcut('b')
        viewmenu.add_command(label=_("Show busy times"), underline=1, accelerator=l,
                             command=self.showBusyTimes)
        self.bind_all(c, lambda event: self.after(AFTER, self.showBusyTimes))

        l, c = platformShortcut('y')
        viewmenu.add_command(label=_("Show yearly calendar"), underline=1, accelerator=l,
                             command=self.showCalendar)
        self.bind_all(c, lambda event: self.after(AFTER, self.showCalendar))

        # date calculator
        l, c = platformShortcut('c')
        viewmenu.add_command(label=_("Open date calculator"), underline=1,
                             command=self.donothing)
        self.bind(c, self.donothing)  # c

        # check for updates
        viewmenu.add_command(label=_("Check for update"), underline=1, command=self
        .checkForUpdate)

        # changes
        viewmenu.add_command(label=_("Show change log"), underline=1, command=self
        .showChanges)

        viewmenu.add_command(label="Show error log", underline=1, command=self.donothing)

        menubar.add_cascade(label="View", menu=viewmenu, underline=0)

        helpmenu = Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.about)
        # helpmenu.add_command(label="Help Index", command=self.donothing)

        # accelerator doesn't seem to work in the help menu
        l, c = platformShortcut('?')
        helpmenu.add_command(label="Help", command=self.help)
        self.bind(c, self.help)

        menubar.add_cascade(label="Help", menu=helpmenu)

        self.config(menu=menubar)

        # self.configure(background="lightgrey")

        self.history = []
        self.index = 0
        self.count = 0
        self.count2id = {}
        self.now = get_current_time()
        self.today = self.now.date()
        self.options = loop.options
        self.popup = ''
        self.value = ''
        self.firsttime = True
        self.mode = 'command'   # or edit or delete
        self.item_hsh = {}
        self.depth2id = {}
        self.prev_week = None
        self.next_week = None
        self.curr_week = None
        self.week_beg = None
        self.itemSelected = None
        self.uuidSelected = None
        self.dtSelected = None
        self.rowSelected = None

        self.title("etm tk")
        if sys_platform == 'Linux':
            self.wm_iconbitmap('@' + 'etmlogo-4.xbm')
            # self.wm_iconbitmap('etmlogo-4.xbm')
            # self.call('wm', 'iconbitmap', self._w, '/Users/dag/etm-tk/etmlogo_128x128x32.ico')
            # self.iconbitmap(ICON_PATH)

        self.columnconfigure(0, minsize=300, weight=1)
        self.rowconfigure(1, weight=2)

        toolbar = Frame(self)

        panedwindow = PanedWindow(self, orient="vertical",
                         # showhandle=True,
                         sashwidth=6, sashrelief='flat',
        )

        self.tree = ttk.Treeview(panedwindow, show='tree', columns=["#1"], selectmode='browse',
                                 # padding=(3, 2, 3, 2)
        )
        self.tree.column('#0', minwidth=200, width=260, stretch=1)
        self.tree.column('#1', minwidth=80, width=140, stretch=0, anchor='center')
        self.tree.bind('<<TreeviewSelect>>', self.OnSelect)
        self.tree.bind('<Double-1>', self.OnDoubleClick)
        self.tree.bind('<Return>', self.OnActivate)
        self.tree.bind('<Escape>', self.cleartext)
        self.tree.bind('<space>', self.goHome)
        # self.tree.bind('<j>', self.jumpToDate)

        self.date2id = {}
        # padx = 2

        self.root = (u'', u'_')

        toolbar.grid(row=0, column=0, sticky='ew', padx=3, pady=2)

        menuwidth = 8

        self.vm_options = [[AGENDA, 'a'],
                           [SCHEDULE, 's'],
                           [PATHS, 'p'],
                           [KEYWORDS, 'k'],
                           [TAGS, 't']]

        self.view2cmd = {'a': self.agendaView,
                         's': self.scheduleView,
                         'p': self.pathView,
                         'k': self.keywordView,
                         't': self.tagView}

        self.vm_opts = [x[0] for x in self.vm_options]
        vm_keys = [x[1] for x in self.vm_options]
        self.viewLabel = _("show")
        self.view = self.vm_options[0][0]
        self.viewValue = StringVar(self)
        self.currentView = StringVar(self)
        self.currentView.set(self.view)
        self.viewValue.set(self.viewLabel)
        self.vm = OptionMenu(toolbar, self.viewValue, *self.vm_opts, command=self.setView)
        self.vm.configure(width=menuwidth)
        for k in self.view2cmd:
            l, c = platformShortcut(k)
            self.bind(c, self.view2cmd[k])  # a, s, p, k, t
            i = vm_keys.index(k)
            self.vm["menu"].entryconfig(i, accelerator=l)

        self.vm.pack(side="left")
        self.vm.configure(width=menuwidth, background=bgclr)

        self.newValue = StringVar(self)
        self.newLabel = _("make")
        self.newValue.set(self.newLabel)
        self.nm_options = [[_('item'), 'n'],
                           [_('timer'), '+'],
        ]
        self.nm_opts = [x[0] for x in self.nm_options]
        self.nm = OptionMenu(toolbar, self.newValue, *self.nm_opts)

        l, c = platformShortcut('n')
        self.nm["menu"].entryconfig(0, accelerator=l, command=self.newItem)
        self.bind(c, self.newItem)  # n

        l, c = platformShortcut('+')
        self.nm["menu"].entryconfig(1, accelerator=l, command=self.startTimer)
        self.bind(c, self.startTimer)  # +

        self.nm.pack(side="left")
        self.nm.configure(width=menuwidth, background=bgclr)

        self.editValue = StringVar(self)
        self.editLabel = _("edit")
        self.editValue.set(self.editLabel)
        self.em_options = [[_('delete'), 'd'],
                           [_('edit'), 'e'],
                           [_('finish'), 'f'],
                           [_('reschedule'), 'r'],
        ]
        self.edit2cmd = {'d': self.deleteItem,
                         'e': self.editItem,
                         'f': self.finishItem,
                         'r': self.rescheduleItem}
        self.em_opts = [x[0] for x in self.em_options]
        em_cmds = [x[1] for x in self.em_options]
        self.em = OptionMenu(toolbar, self.editValue, *self.em_opts)
        for i in range(len(em_cmds)):
            k = em_cmds[i]
            l, c = platformShortcut(k)
            self.em["menu"].entryconfig(i, accelerator=l, command=self.edit2cmd[k])
            # self.bind(c, self.edit2cmd[k])  # c, d, e, f
            self.bind_all(c, lambda event, x=k: self.after(AFTER, self.edit2cmd[x]))

        self.em.pack(side="left")
        self.em.configure(width=menuwidth, background=bgclr)

        self.helpBtn = Button(toolbar, bd=0, text="?", command=self.help)
        self.helpBtn.pack(side="right")
        self.helpBtn.configure(highlightbackground=bgclr, highlightthickness=0)

        self.filterValue = StringVar(self)
        self.filterValue.set('')
        self.filterValue.trace_variable("w", self.filterView)
        self.e = Entry(toolbar, width=8, textvariable=self.filterValue,
                       # relief="raised",
                       # highlightcolor=bgclr,
                       # bd=4
                      )
        self.e.bind('<Return>', self.showView)
        self.e.bind('<Escape>', self.cleartext)
        self.e.bind('<Up>', self.prev_history)
        self.e.bind('<Down>', self.next_history)
        self.e.pack(side="left", fill=tkinter.BOTH, expand=1, padx=2)
        self.e.configure(width=menuwidth, highlightthickness=0)

        panedwindow.add(self.tree, padx=3, pady=0, stretch="first")

        self.l = ReadOnlyText(panedwindow, wrap="word", padx=3, bd=2, relief="sunken",
                              font=tkFont.Font(family="Lucida Sans Typewriter"), height=6,
                              width=46, takefocus=False)
        self.l.bind('<Escape>', self.cleartext)
        self.l.bind('<space>', self.goHome)
        self.l.bind('<Tab>', self.focus_next_window)

        panedwindow.add(self.l, padx=3, pady=0, stretch="never")

        panedwindow.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        panedwindow.configure(background=bgclr)

        self.sf = Frame(self)
        toolbar.configure(background=bgclr)
        # self.pendingAlerts = StringVar(self)
        # self.pendingAlerts.set("")

        showing = Label(self.sf, textvariable=self.currentView, bd=1, relief="flat",
                        anchor="w", padx=0, pady=0)
        showing.pack(side="left")
        showing.configure(width=menuwidth, background=bgclr,
                          highlightthickness=0)

        self.nonDefaultCalendars = StringVar(self)
        self.nonDefaultCalendars.set("")
        nonDefCal = Label(self.sf, textvariable=self.nonDefaultCalendars, bd=0,
                          relief="flat", anchor="center", padx=0, pady=0)
        nonDefCal.pack(side="left")
        nonDefCal.configure(background=bgclr)

        self.timerStatus = StringVar(self)
        self.timerStatus.set("")
        timer_status = Label(self.sf, textvariable=self.timerStatus, bd=0, relief="flat",
                             anchor="center", padx=4, pady=0)
        timer_status.pack(side="left", expand=1)
        timer_status.configure(background=bgclr, highlightthickness=0)

        self.pendingAlerts = IntVar(self)
        self.pendingAlerts.set(0)
        self.pending = Button(self.sf, bd=0, width=1, textvariable=self.pendingAlerts, command=self.showAlerts)
        self.pending.pack(side="right")
        self.pending.configure(highlightbackground=bgclr, highlightthickness=0)
        self.showPending = True

        self.currentTime = StringVar(self)
        currenttime = Label(self.sf, textvariable=self.currentTime, bd=1, relief="flat",
                            anchor="e", padx=4, pady=0)
        currenttime.pack(side="right")
        currenttime.configure(background=bgclr)

        self.sf.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        self.sf.configure(background=bgclr)

        self.grid()

        # self.e.select_range(0, END)

        # start clock
        self.updateClock()

        # show default view
        self.showView()

    def updateCalendars(self, *args):
        for i in range(len(loop.calendars)):
            loop.calendars[i][1] = self.calendarValues[i].get()
        if loop.calendars != loop.options['calendars']:
            cal_pattern = r'^%s' % '|'.join(
                [x[2] for x in loop.calendars if x[1]])
            loop.cal_regex = re.compile(cal_pattern)
            self.nonDefaultCalendars.set("*")
        else:
            cal_pattern = ''
            loop.cal_regex = None
            self.nonDefaultCalendars.set("")
            # print('updateCalendars', loop.calendars, cal_pattern, loop.cal_regex)
        self.showView()


    def quit(self, e=None):
        ans = askokcancel(
            _('Quit'),
            _("Do you really want to quit?"),
            parent=self)
        if ans:
            self.destroy()

    def donothing(self, e=None):
        """For testing"""
        logger.debug('donothing')

    def newItem(self, e=None):
        logger.debug('newItem')
        changed = SimpleEditor(parent=self, options=loop.options).changed
        if changed:
            logger.debug('changed, reloading data')
            loop.loadData()
            self.showView()

    def cloneItem(self, e=None):
        logger.debug('cloneItem')

    def deleteItem(self, e=None):
        logger.debug('{0}: {1}'.format(self.itemSelected['_summary'], self.dtSelected))
        indx = 3
        if 'r' in self.itemSelected:
            indx, value = self.deleteWhich(self.dtSelected)
            logger.debug("{0}: {1}".format(indx, value))
            if not indx:
                return
            self.itemSelected['_dt'] = parse(self.dtSelected)
        else:
            ans = askokcancel('Verify deletion', "Delete this item?", parent=self.tree)
            if not ans:
                return
        loop.item_hsh = self.itemSelected
        loop.cmd_do_delete(indx)
        loop.loadData()
        self.showView(row=self.topSelected)


    def deleteWhich(self, instance="xyz"):
        prompt = "\n".join([
            _("You have selected an instance of a repeating"),
            _("item. What do you want to delete?")])
        opt_lst = [
            _("this instance"),
            _("this and all subsequent instances"),
            _("all instances")]
        indx, value = OptionsDialog(parent=self, title=_("instance: {0}").format(instance), prompt=prompt, opts=opt_lst).getValue()
        return indx, value

    def editItem(self, e=None):
        logger.debug('{0}: {1}'.format(self.itemSelected['_summary'], self.dtSelected))
        choice = 3
        title = "etm tk"
        if 'r' in self.itemSelected:
            choice, value = self.editWhich(self.dtSelected)
            logger.debug("{0}: {1}".format(choice, value))
            if not choice:
                self.tree.focus_set()
                return
            self.itemSelected['_dt'] = parse(self.dtSelected)
        if choice in [1, 2]:
            title = _("new item")
            hsh_cpy = deepcopy(self.itemSelected)
            hsh_rev = deepcopy(self.itemSelected)
            # we will be editing and adding hsh_cpy and replacing hsh_rev
            hsh_cpy['i'] = uniqueId()
            self.mode = 'append'
            # remove the line number info to indicate that hsh_cpy is to be appended
            # hsh_cpy['fileinfo'][1] = hsh_cpy['fileinfo'][2] = 0

            dt = hsh_cpy['_dt'].replace(
                tzinfo=tzlocal()).astimezone(gettz(hsh_cpy['z']))
            dtn = dt.replace(tzinfo=None)

            if choice == 1:
                # this instance
                # remove this instance by adding it to @-
                # open a non-repeating copy with this instance as @s
                if '+' in hsh_rev and dtn in hsh_rev['+']:
                    hsh_rev['+'].remove(dtn)
                    if not hsh_rev['+'] and hsh_rev['r'] == 'l':
                        del hsh_rev['r']
                        del hsh_rev['_r']
                else:
                    hsh_rev.setdefault('-', []).append(dt)
                for k in ['_r', 'o', '+', '-']:
                    if k in hsh_cpy:
                        del hsh_cpy[k]
                hsh_cpy['s'] = dt
                rev_str = hsh2str(hsh_rev, loop.options)
                self.mode = 'changed instance'
                edit_str = hsh2str(hsh_cpy, loop.options)
                self.mode = 'append'

            elif choice == 2:
                # this and all subsequent instances
                # add this instance minus one minute as &u to each @r entry
                # open a copy with with this instance as @s
                tmp = []
                for h in hsh_rev['_r']:
                    if 'f' in h and h['f'] != u'l':
                        h['u'] = dt - ONEMINUTE
                    tmp.append(h)
                hsh_rev['_r'] = tmp
                if u'+' in hsh:
                    tmp_rev = []
                    tmp_cpy = []
                    for d in hsh_rev['+']:
                        if d < dt:
                            tmp_rev.append(d)
                        else:
                            tmp_cpy.append(d)
                    hsh_rev['+'] = tmp_rev
                    hsh_cpy['+'] = tmp_cpy
                if u'-' in hsh:
                    tmp_rev = []
                    tmp_cpy = []
                    for d in hsh_rev['-']:
                        if d < dt:
                            tmp_rev.append(d)
                        else:
                            tmp_cpy.append(d)
                    hsh_rev['-'] = tmp_rev
                    hsh_cpy['-'] = tmp_cpy
                hsh_cpy['s'] = dt
                rev_str = hsh2str(hsh_rev, loop.options)
                edit_str = hsh2str(hsh_cpy, loop.options)

            changed = SimpleEditor(parent=self, newhsh=hsh_cpy, rephsh=hsh_rev,
                         options=loop.options, title=title).changed

        else:
            changed = SimpleEditor(parent=self, newhsh=self.itemSelected,
                         options=loop.options, title=self.filetext).changed
        if changed:
            loop.loadData()
            self.showView(row=self.topSelected)
        else:
            self.tree.focus_set()

    def editFile(self, e=None, file=None):
        relfile = os.path.relpath(file, self.options['datadir'])
        logger.debug('file: {0}'.format(file))
        changed = SimpleEditor(parent=self, newhsh=None, rephsh=None,  file=file, options=loop.options, title=relfile).changed
        if changed:
            loop.loadData()
            self.showView()

    def editData(self, e=None):
        initdir = self.options['datadir']
        fileops = {'defaultextension': '.txt',
                   'filetypes': [('text files', '.txt')],
                   'initialdir': initdir,
                   'initialfile': "",
                   'title': 'etmtk data files',
                   'parent': self}
        filename = askopenfilename(**fileops)
        if not (filename and os.path.isfile(filename)):
            return False
        self.editFile(e, file=filename)


    def editWhich(self, instance="xyz"):
        prompt = "\n".join([
            _("You have selected an instance of a repeating"),
            _("item. What do you want to change?")])
        opt_lst = [
            # _("only the datetime of this instance"),
            _("this instance"),
            _("this and all subsequent instances"),
            _("all instances")]
        indx, value = OptionsDialog(parent=self, title=_("instance: {0}").format(instance), prompt=prompt, opts=opt_lst).getValue()
        # logger.debug(value)
        return indx, value


    def finishItem(self, e=None):
        prompt = _("""\
Enter the completion date for the item or return an empty string to
use the current date. Relative dates and fuzzy parsing are supported.""")
        d = GetDateTime(parent=self, title=_('date'), prompt=prompt)
        chosen_day = d.value
        if chosen_day is None:
            return ()
        logger.debug('completion date: {0}'.format(chosen_day))
        loop.item_hsh = self.itemSelected
        loop.cmd_do_finish(chosen_day)
        loop.loadData()
        self.showView(row=self.topSelected)


    def rescheduleItem(self, e=None):
        loop.item_hsh = item_hsh = self.itemSelected
        if self.dtSelected:
            loop.old_dt = old_dt = parse(self.dtSelected)
            title = _('rescheduling {0}').format(old_dt.strftime(
                rrulefmt))
        else:
            loop.old_dt = None
            title = _('scheduling an undated item')
        logger.debug('dtSelected: {0}'.format(self.dtSelected))
        prompt = _("""\
Enter the new date and time for the item or return an empty string to
use the current time. Relative dates and fuzzy parsing are supported.""")
        dt = GetDateTime(parent=self, title=title,
                         prompt=prompt)
        new_dt = dt.value
        if new_dt is None:
            return
        new_dtn = new_dt.astimezone(gettz(self.itemSelected['z'])).replace(tzinfo=None)
        logger.debug('rescheduled from {0} to {1}'.format(self.dtSelected, new_dtn))
        loop.cmd_do_reschedule(new_dtn)
        loop.loadData()
        self.showView(row=self.topSelected)


    def showAlerts(self, e=None):
        t = _('remaining alerts for today')
        header = "{0:^7}\t{1:^7}\t{2:<8}{3:<26}".format(
            _('alert'),
            _('event'),
            _('type'),
            _('summary'))
        divider = '-' * 52
        if loop.alerts:
            # for alert in loop.alerts:
            s = '%s\n%s\n%s' % (
                header, divider, "\n".join(
                    ["{0:^7}\t{1:^7}\t{2:<8}{3:<26}".format(
                        x[1]['alert_time'], x[1]['_event_time'],
                        ", ".join(x[1]['_alert_action']),
                        str(x[1]['summary'][:26])) for x in loop.alerts]))
        else:
            s = _("none")
        self.textWindow(self, t, s)



    def agendaView(self, e=None):
        self.setView(AGENDA)

    def scheduleView(self, e=None):
        self.setView(SCHEDULE)

    def pathView(self, e=None):
        self.setView(PATHS)

    def keywordView(self, e=None):
        self.setView(KEYWORDS)

    def tagView(self, e=None):
        self.setView(TAGS)

    def setView(self, view, row=None):
        self.rowSelected = None
        logger.debug("view: {0}".format(view))
        self.view = view
        self.showView(row=row)

    def filterView(self, e=None):
        self.depth2id = {}
        fltr = self.filterValue.get()
        cmd = "{0} {1}".format(
            self.vm_options[self.vm_opts.index(self.view)][1], fltr)
        self.mode = 'command'
        self.process_input(event=e, cmd=cmd)
        self.e.focus_set()


    def showView(self, e=None, row=None):
        self.depth2id = {}
        self.currentView.set(self.view)
        self.viewValue.set(self.viewLabel)
        fltr = self.filterValue.get()
        cmd = "{0} {1}".format(
            self.vm_options[self.vm_opts.index(self.view)][1], fltr)
        self.mode = 'command'
        self.process_input(event=e, cmd=cmd)
        if row:
            logger.debug("row: {0}".format(row))
            # self.tree.see(max(0, self.rowSelected))
            self.tree.yview(max(0, row - 1))
        # else:
        #     self.goHome()

    def showBusyTimes(self, event=None, chosen_day=None):
        prompt = _("""\
Busy times will be shown for the week containing the date you select.
Return an empty string for the current week. Relative dates and fuzzy
parsing are supported.""")
        d = GetDateTime(parent=self, title=_('date'), prompt=prompt)
        chosen_day = d.value
        logger.debug('chosen_day: {0}'.format(chosen_day))

        if chosen_day is None:
            return ()
            # chosen_day = self.today

        yn, wn, dn = chosen_day.isocalendar()
        self.prev_week = chosen_day - 7 * ONEDAY
        self.next_week = chosen_day + 7 * ONEDAY
        self.curr_week = chosen_day
        if dn > 1:
            days = dn - 1
        else:
            days = 0
        self.week_beg = weekbeg = chosen_day - days * ONEDAY
        weekend = chosen_day + (6 - days) * ONEDAY
        weekdays = []

        day = weekbeg
        busy_lst = []
        occasion_lst = []
        # matching = self.cal_regex is not None and self.default_regex is not None
        while day <= weekend:
            weekdays.append(fmt_weekday(day))
            isokey = day.isocalendar()
            # if isokey == iso_today:
            #     self.today_col = col_num

            if isokey in loop.occasions:
                bt = []
                for item in loop.occasions[isokey]:
                    it = list(item)
                    # if matching:
                    #     if not self.cal_regex.match(item[-1]):
                    #         continue
                    #     mtch = (
                    #         self.default_regex.match(it[-1]) is not None)
                    # else:
                    #     mtch = True
                    # it.append(mtch)
                    item = tuple(it)
                    bt.append(item)
                occasion_lst.append(bt)
            else:
                occasion_lst.append([])

            if isokey in loop.busytimes:
                bt = []
                for item in loop.busytimes[isokey][1]:
                    it = list(item)
                    # if matching:
                    #     if not self.cal_regex.match(item[-1]):
                    #         continue
                    #     mtch = (
                    #         self.default_regex.match(it[-1]) is not None)
                    # else:
                    #     mtch = True
                    # it.append(mtch)
                    item = tuple(it)
                    bt.append(item)
                busy_lst.append(bt)
            else:
                busy_lst.append([])
            day = day + ONEDAY

        ybeg = weekbeg.year
        yend = weekend.year
        mbeg = weekbeg.month
        mend = weekend.month
        if mbeg == mend:
            header = "{0} - {1}".format(
                fmt_dt(weekbeg, '%b %d'), fmt_dt(weekend, '%d, %Y'))
        elif ybeg == yend:
            header = "{0} - {1}".format(
                fmt_dt(weekbeg, '%b %d'), fmt_dt(weekend, '%b %d, %Y'))
        else:
            header = "{0} - {1}".format(
                fmt_dt(weekbeg, '%b %d, %Y'), fmt_dt(weekend, '%b %d, %Y'))
        header = leadingzero.sub('', header)

        lines = [_("Scheduled times for week {0}: {1}").format(wn, header)]
        ampm = loop.options['ampm']
        s1 = s2 = ''
        for i in range(7):
            times = []
            for tup in busy_lst[i]:
                t1 = max(7 * 60, tup[0])
                t2 = min(23 * 60, max(420, tup[1]))
                if t1 != t2:
                    t1h, t1m = (t1 // 60, t1 % 60)
                    t2h, t2m = (t2 // 60, t2 % 60)
                    if ampm:
                        if t1h == 12:
                            s1 = 'pm'
                        elif t1h > 12:
                            t1h -= 12
                            s1 = 'pm'
                        else:
                            s1 = 'am'
                        if t2h == 12:
                            s2 = 'pm'
                        elif t2h > 12:
                            t2h -= 12
                            s2 = 'pm'
                        else:
                            s2 = 'am'

                    T1 = "%d:%02d%s" % (t1h, t1m, s1)
                    T2 = "%d:%02d%s" % (t2h, t2m, s2)

                    times.append("%s-%s" % (T1, T2))
            if times:
                lines.append("   %s: %s" % (weekdays[i], "; ".join(times)))
        s = "\n".join(lines)
        self.textWindow(parent=self, title=_('busy times'), prompt=s)
        # print(s)

    # noinspection PyShadowingNames
    def showCalendar(self, e=None):
        cal_year = 0
        opts = loop.options
        cal_pastcolor = '#FFCCCC'
        cal_currentcolor = '#FFFFCC'
        cal_futurecolor = '#99CCFF'

        def showYear(x=0):
            global cal_year
            if x:
                cal_year += x
            else:
                cal_year = 0
            cal = "\n".join(calyear(cal_year, options=opts))
            if cal_year > 0:
                col = cal_futurecolor
            elif cal_year < 0:
                col = cal_pastcolor
            else:
                col = cal_currentcolor
            t.configure(bg=col)
            t.delete("0.0", END)
            t.insert("0.0", cal)

        win = Toplevel()
        win.title(_("Calendar"))
        f = Frame(win)
        # pack the button first so that it doesn't disappear with resizing
        b = Button(win, text=_('OK'), width=10, command=win.destroy, default='active')
        b.pack(side='bottom', fill=tkinter.NONE, expand=0, pady=0)
        win.bind('<Return>', (lambda e, b=b: b.invoke()))
        win.bind('<Escape>', (lambda e, b=b: b.invoke()))

        t = ReadOnlyText(f, wrap="word", padx=2, pady=2, bd=2, relief="sunken",
                         font=tkFont.Font(family="Lucida Sans Typewriter"),
                         # height=14,
                         # width=52,
                         takefocus=False)
        win.bind('<Left>', (lambda e: showYear(-1)))
        win.bind('<Right>', (lambda e: showYear(1)))
        win.bind('<space>', (lambda e: showYear()))
        showYear()
        t.pack(side='left', fill=tkinter.BOTH, expand=1, padx=0, pady=0)
        ysb = ttk.Scrollbar(f, orient='vertical', command=t.yview, width=8)
        ysb.pack(side='right', fill=tkinter.Y, expand=0, padx=0, pady=0)
        # t.configure(state="disabled", yscroll=ysb.set)
        t.configure(yscroll=ysb.set)
        f.pack(padx=2, pady=2, fill=tkinter.BOTH, expand=1)
        win.focus_set()
        win.grab_set()
        win.transient(self)
        win.wait_window(win)

    def newCommand(self, e=None):
        newcommand = self.newValue.get()
        self.newValue.set(self.newLabel)
        print('newCommand', newcommand)

    def help(self, event=None):
        res = loop.help_help()
        self.textWindow(parent=self, title='etm', prompt=res)

    def about(self, event=None):
        res = loop.do_v("")
        self.textWindow(parent=self, title='etm', prompt=res)

    def checkForUpdate(self, event=None):
        res = checkForNewerVersion()[1]
        self.textWindow(parent=self, title='etm', prompt=res)

    def showChanges(self, event=None):
        if self.itemSelected:
            f = self.itemSelected['fileinfo'][0]
            fn = os.path.join(self.options['datadir'], f)
            title = _("Showing changes for {0}.").format(f)

        else:
            fn = ""
            title = _("Showing changes for all files.")

        prompt = _("""\
{0}

If an item is selected, changes will be shown for the file containing
the item. Otherwise, changes will be shown for all files.

Enter an integer number of changes to display
or 0 to display all changes.""").format(title)
        depth = GetInteger(
            parent=self,
            title=_("Changes"),
            prompt=prompt, opts=[0], default=10).value
        if depth is None:
            return ()
        if depth == 0:
            # all changes
            numstr = ""
        else:
            numstr = "-l {0}".format(depth)


        command = loop.options['hg_history'].format(
            repo=loop.options['datadir'],
            file=fn, numchanges=numstr, rev="{rev}", desc="{desc}")
        logger.debug('history command: {0}'.format(command))
        p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True,
                             universal_newlines=True).stdout.read()
        self.textWindow(parent=self, title=title, prompt=str(p))

    def focus_next_window(self, event):
        event.widget.tk_focusNext().focus()
        return "break"

    def goHome(self, event=None):
        if self.view == SCHEDULE:
            today = get_current_time().date()
            self.scrollToDate(today)
        else:
            self.tree.focus_set()
            self.tree.focus(1)
            self.tree.selection_set(1)
            self.tree.yview(0)
        return 'break'

    def OnSelect(self, event=None):
        """
        Tree row has gained selection.
        """
        item = self.tree.selection()[0]
        self.rowSelected = int(item)
        type_chr = self.tree.item(item)['text'][0]
        uuid, dt, hsh = self.getInstance(item)
        # self.l.configure(state="normal")
        self.l.delete("0.0", END)
        if uuid is not None:
            self.em.configure(state="normal")
            isRepeating = ('r' in hsh and dt)
            if isRepeating:
                item = "{0} {1}".format(_('selected'), dt)
                self.em["menu"].entryconfig(1, label="{0} ...".format(self.em_opts[1]))
                self.em["menu"].entryconfig(2, label="{0} ...".format(self.em_opts[2]))
            else:
                self.em["menu"].entryconfig(1, label=self.em_opts[1])
                self.em["menu"].entryconfig(2, label=self.em_opts[2])
                item = _('selected')
            isUnfinished = (type_chr in ['-', '+', '%'])
            l1 = hsh['fileinfo'][1]
            l2 = hsh['fileinfo'][2]
            if l1 == l2:
                lines = "{0} {1}".format(_('line'), l1)
            else:
                lines = "{0} {1}-{2}".format(_('lines'), l1, l2)
            self.filetext = filetext = "{0}, {1}".format(hsh['fileinfo'][0],
                                                      lines)
            text = "{1}\n\n{2}: {3}".format(item, hsh['entry'].lstrip(), _("file"), filetext)
            for i in [0, 1, 3]: # everything except finish
                self.em["menu"].entryconfig(i, state='normal')
                # self.em.configure(state="normal")
            if isUnfinished:
                self.em["menu"].entryconfig(2, state='normal')
            else:
                self.em["menu"].entryconfig(2, state='disabled')
            self.uuidSelected = uuid
            self.itemSelected = hsh
            self.dtSelected = dt
        else:
            self.em.configure(state="disabled")
            text = ""
            for i in range(4):
                self.em["menu"].entryconfig(i, state='disabled')
            self.itemSelected = None
            self.uuidSelected = None
            self.dtSelected = None
        r = self.tree.identify_row(1)
        logger.debug("top row: '{0}' {1}".format(r, type(r)))
        if r:
            self.topSelected = int(r)
        else:
            self.topSelected = 1

        logger.debug("top: {3}; row: '{0}'; uuid: '{1}'; instance: '{2}'".format(self.rowSelected, self.uuidSelected, self.dtSelected,  self.topSelected)); self.l.insert(INSERT, text)
        return "break"

    def OnActivate(self, event):
        """
        Return pressed with tree row selected
        """
        item = self.tree.selection()[0]
        uuid, dt, hsh = self.getInstance(item)
        if uuid is not None:
            self.editItem()
            # print("you pressed <Return> on", item, uuid, dt, hsh['_summary'])
            # print(hsh)
        # else:
        #     print("you pressed <Return> on", item)
        return "break"

    def OnDoubleClick(self, event):
        """
        Double click on tree row
        """
        # print( self.tree.selection(), event.x, event.y)
        # print(self.tree.identify('item',event.x,event.y))
        self.update_idletasks()

        item = self.tree.identify('item', event.x, event.y)
        uuid, dt, hsh = self.getInstance(item)
        if uuid is not None:
            self.editItem()
            # print("you double clicked on", item, uuid, dt, hsh['_summary'])
        # else:
        #     print("you double clicked on", item)
        return "break"

    def getInstance(self, item):
        instance = self.count2id[item]
        if instance is None:
            return None, None, None
        uuid, dt = self.count2id[item].split("::")
        hsh = loop.uuid2hash[uuid]
        logger.debug('item: {0}; uuid: {1}, dt: {2}'.format(item, uuid, dt))
        return uuid, dt, hsh

    def updateClock(self):
        # print('updateClock', loop.options)
        self.now = get_current_time()
        nxt = (60 - self.now.second) * 1000 - self.now.microsecond // 1000
        self.after(nxt, self.updateClock)
        nowfmt = "{0} {1}".format(
            s2or3(self.now.strftime(loop.options['reprtimefmt']).lower()),
            s2or3(self.now.strftime("%a %b %d %Z")))
        nowfmt = leadingzero.sub("", nowfmt)
        self.currentTime.set("{0}".format(nowfmt))
        today = self.now.date()
        newday = (today != self.today)
        self.today = today

        new, modified, deleted = get_changes(
            self.options, loop.file2lastmodified)
        if newday or new or modified or deleted:
            logger.debug('refreshing view: newday or changed')
            loop.loadData()
            self.showView()

        if self.actionTimer.timer_status != STOPPED:
            self.timerStatus.set(self.actionTimer.get_time())
            if self.actionTimer.timer_minutes >= 1:
                if (self.options['action_interval'] and self.actionTimer.timer_minutes % loop.options['action_interval'] == 0):
                    logger.debug('action_minutes trigger: {0} {1}'.format(self.actionTimer.timer_minutes, self.actionTimer.timer_status))
                    if self.actionTimer.timer_status == 'running':
                        if ('running' in loop.options['action_timer'] and
                                loop.options['action_timer']['running']):
                            tcmd = loop.options['action_timer']['running']
                            logger.debug('running: {0}'.format(tcmd))
                            # process.startDetached(tcmd)
                            subprocess.call(tcmd, shell=True)

                    elif self.actionTimer.timer_status == 'paused':
                        if ('paused' in loop.options['action_timer'] and
                                loop.options['action_timer']['paused']):
                            tcmd = loop.options['action_timer']['paused']
                            # process.startDetached(tcmd)
                            logger.debug('running: {0}'.format(tcmd))
                            subprocess.call(tcmd, shell=True)


        self.updateAlerts()

        logger.debug("next update in {0} milliseconds".format(nxt))

    def updateAlerts(self):
        # print('updateAlerts', len(loop.alerts), self.showPending)
        if loop.alerts:
            curr_minutes = datetime2minutes(self.now)
            td = -1
            while td < 0 and loop.alerts:
                td = loop.alerts[0][0] - curr_minutes
                if td < 0:
                    loop.alerts.pop(0)
            if td == 0:
                if ('alert_wakecmd' in loop.options and
                        loop.options['alert_wakecmd']):
                    cmd = loop.options['alert_wakecmd']
                    subprocess.call(cmd, shell=True)
                while td == 0:
                    hsh = loop.alerts[0][1]
                    loop.alerts.pop(0)
                    actions = hsh['_alert_action']
                    if 's' in actions:
                        if ('alert_soundcmd' in self.options and
                                self.options['alert_soundcmd']):
                            scmd = expand_template(
                                self.options['alert_soundcmd'], hsh)
                            subprocess.call(scmd, shell=True)
                        else:
                            self.textWindow(self,
                                "etm", _("""\
A sound alert failed. The setting for 'alert_soundcmd' is missing from \
your etmtk.cfg."""))
                    if 'd' in actions:
                        if ('alert_displaycmd' in self.options and
                                self.options['alert_displaycmd']):
                            dcmd = expand_template(
                                self.options['alert_displaycmd'], hsh)
                            subprocess.call(dcmd, shell=True)
                        else:
                            self.textWindow(self,
                                "etm", _("""\
A display alert failed. The setting for 'alert_displaycmd' is missing \
from your etmtk.cfg."""))
                    if 'v' in actions:
                        if ('alert_voicecmd' in self.options and
                                self.options['alert_voicecmd']):
                            vcmd = expand_template(
                                self.options['alert_voicecmd'], hsh)
                            subprocess.call(vcmd, shell=True)
                        else:
                            self.textWindow(self,
                                "etm", _("""\
An email alert failed. The setting for 'alert_voicecmd' is missing from \
your etmtk.cfg."""))
                    if 'e' in actions:
                        missing = []
                        for field in [
                            'smtp_from',
                            'smtp_id',
                            'smtp_pw',
                            'smtp_server',
                            'smtp_to']:
                            if not self.options[field]:
                                missing.append(field)
                        if missing:
                            self.textWindow(self,
                                "etm", _("""\
An email alert failed. Settings for the following variables are missing \
from your etmtk.cfg: %s.""" % ", ".join(["'%s'" % x for x in missing])))
                        else:
                            subject = hsh['summary']
                            message = expand_template(
                                self.options['email_template'], hsh)
                            arguments = hsh['_alert_argument']
                            recipients = [str(x).strip() for x in arguments[0]]
                            if len(arguments) > 1:
                                attachments = [str(x).strip()
                                               for x in arguments[1]]
                            else:
                                attachments = []
                            if subject and message and recipients:
                                send_mail(
                                    smtp_to=recipients,
                                    subject=subject,
                                    message=message,
                                    files=attachments,
                                    smtp_from=self.options['smtp_from'],
                                    smtp_server=self.options['smtp_server'],
                                    smtp_id=self.options['smtp_id'],
                                    smtp_pw=self.options['smtp_pw'])
                    if 'm' in actions:
                        MessageWindow(
                            self,
                            title=expand_template('!summary!', hsh),
                            prompt=expand_template(
                                self.options['alert_template'], hsh))

                    if 't' in actions:
                        missing = []
                        for field in [
                            'sms_from',
                            'sms_message',
                            'sms_phone',
                            'sms_pw',
                            'sms_server',
                            'sms_subject']:
                            if not self.options[field]:
                                missing.append(field)
                        if missing:
                            self.textWindow(self,
                                "etm", _("""\
A text alert failed. Settings for the following variables are missing \
from your 'emt.cfg': %s.""" % ", ".join(["'%s'" % x for x in missing])))
                        else:
                            message = expand_template(
                                self.options['sms_message'], hsh)
                            subject = expand_template(
                                self.options['sms_subject'], hsh)
                            arguments = hsh['_alert_argument']
                            if arguments:
                                sms_phone = ",".join([str(x).strip() for x in
                                                      arguments[0]])
                            else:
                                sms_phone = self.options['sms_phone']
                            if message:
                                send_text(
                                    sms_phone=sms_phone,
                                    subject=subject,
                                    message=message,
                                    sms_from=self.options['sms_from'],
                                    sms_server=self.options['sms_server'],
                                    sms_pw=self.options['sms_pw'])
                    if 'p' in actions:
                        arguments = hsh['_alert_argument']
                        proc = str(arguments[0][0]).strip()
                        cmd = expand_template(proc, hsh)
                        subprocess.call(cmd, shell=True)

                    if not loop.alerts:
                        break
                    td = loop.alerts[0][0] - curr_minutes

        if loop.alerts:
            self.pendingAlerts.set("{0}".format(len(loop.alerts)))
            self.pending.configure(state="normal")
            if not self.showPending:
                self.pending.pack(side="right")
                self.showPending = True
        else:
            self.pendingAlerts.set("")
            self.pending.configure(state="disabled")
            if self.showPending:
                self.pending.pack_forget()
                self.showPending = False

    # FIXME: is this needed?
    def prev_history(self, event):
        """
        Replace input with the previous history item.
        """
        print('up')
        if self.index >= 1:
            self.index -= 1
            self.e.delete(0, END)
            self.e.insert(0, self.history[self.index])
        return 'break'

    # FIXME: is this needed?
    def next_history(self, event):
        """
        Replace input with the next history item.
        """
        print('down')
        if self.index + 1 < len(self.history):
            self.index += 1
            self.e.delete(0, END)
            self.e.insert(0, self.history[self.index])
        return 'break'

    def textWindow(self, parent, title=None, prompt=None):
        d = TextDialog(parent, title=title, prompt=prompt)

    # noinspection PyShadowingNames
    # def textWindow(self, title, prompt, modal=True):
    #     win = Toplevel()
    #     win.title(title)
    #     # win.minsize(444, 430)
    #     # win.minsize(450, 450)
    #     f = Frame(win)
    #     # pack the button first so that it doesn't disappear with resizing
    #     b = Button(win, text=_('OK'), width=10, command=win.destroy, default='active')
    #     b.pack(side='bottom', fill=tkinter.NONE, expand=0, pady=0)
    #     win.bind('<Return>', (lambda e, b=b: b.invoke()))
    #     win.bind('<Escape>', (lambda e, b=b: b.invoke()))
    #
    #     t = ReadOnlyText(
    #         f, wrap="word", padx=2, pady=2, bd=2, relief="sunken",
    #         font=tkFont.Font(family="Lucida Sans Typewriter"),
    #         height=14,
    #         width=52,
    #         takefocus=False)
    #     t.insert("0.0", prompt)
    #     t.pack(side='left', fill=tkinter.BOTH, expand=1, padx=0, pady=0)
    #     ysb = ttk.Scrollbar(f, orient='vertical', command=t.yview, width=8)
    #     ysb.pack(side='right', fill=tkinter.Y, expand=0, padx=0, pady=0)
    #     # t.configure(state="disabled", yscroll=ysb.set)
    #     t.configure(yscroll=ysb.set)
    #     f.pack(padx=2, pady=2, fill=tkinter.BOTH, expand=1)
    #
    #     win.focus_set()
    #     if modal:
    #         win.grab_set()
    #         win.transient(self)
    #         win.wait_window(win)

    def goToDate(self, e=None):
        """


        :param e:
        :return:
        """
        prompt = _("""\
Return an empty string for the current date or a date to be parsed.
Relative dates and fuzzy parsing are supported.""")
        if self.view != self.vm_options[1][0]:
            self.view = self.vm_options[1][0]
            self.showView()
        d = GetDateTime(parent=self, title=_('date'), prompt=prompt)
        value = d.value
        logger.debug('value: {0}'.format(value))
        if value is not None:
            self.scrollToDate(value.date())
        return "break"

    def startTimer(self, event=None):
        """

        :param event:
        :return:
        """
        if self.actionTimer.timer_status == 'stopped':
            if self.uuidSelected:
                notnull = False
                options = {'notnull': False}
                prompt = _("""\
    Enter a summary for the new action timer or return an empty string
    to create a timer based on the selected item.""")
            else:
                notnull = True
                options = {'notnull': True}
                prompt = _("""\
    Enter a summary for the new action timer.""")
            options = {'notnull': notnull}
            d = GetString(parent=self, title=_('action timer'), prompt=prompt,
                          opts=options)
            value = d.value
            logger.debug('value: {0}'.format(value))
            if notnull and value is None:
                return "break"
            if value is None:
                self.timerItem = self.uuidSelected
                # Based on item, 'entry' will be in hsh
                hsh = loop.uuid2hash[self.uuidSelected]
                if hsh['itemtype'] == '~' and hsh['s'].date() == datetime.today():
                    logger.debug('an action recorded today')
            else:
                # new, 'entry will not be in hsh
                self.timerItem = None
                hsh = {'_summary': value}
            logger.debug('item: {0}'.format(hsh))
            self.nm["menu"].entryconfig(1, label=_("toggle timer"))
            self.actionTimer.timer_start(hsh)
            if ('running' in loop.options['action_timer'] and
                    loop.options['action_timer']['running']):
                tcmd = loop.options['action_timer']['running']
                logger.debug('command: {0}'.format(tcmd))
                # process.startDetached(tcmd)
                subprocess.call(tcmd, shell=True)
        elif self.actionTimer.timer_status in [PAUSED, RUNNING]:
            self.actionTimer.timer_toggle()
            if (self.actionTimer.timer_status == RUNNING and 'running' in loop.options['action_timer'] and loop.options['action_timer']['running']):
                tcmd = loop.options['action_timer']['running']
                logger.debug('command: {0}'.format(tcmd))
                # process.startDetached(tcmd)
                subprocess.call(tcmd, shell=True)
            elif (self.actionTimer.timer_status == PAUSED and 'paused' in loop.options['action_timer'] and loop.options['action_timer']['paused']):
                tcmd = loop.options['action_timer']['paused']
                logger.debug('command: {0}'.format(tcmd))
                # process.startDetached(tcmd)
                subprocess.call(tcmd, shell=True)

        self.timerStatus.set(self.actionTimer.get_time())
        return "break"

    def stopTimer(self, event=None):
        if self.actionTimer.timer_status not in [RUNNING, PAUSED]:
            logger.info('stopping already stopped timer')
            return "break"
        self.timerStatus.set(self.actionTimer.get_time())


    def gettext(self, event=None):
        s = self.e.get()
        if s is not None:
            return s
        else:
            return ''

    def cleartext(self, event=None):
        if self.e.get():
            self.e.delete(0, END)
            self.showView()
        return 'break'

    def process_input(self, event=None, cmd=None):
        """
        This is called whenever enter is pressed in the input field.
        Action depends upon comand_mode.
        Append input to history, process it and show the result in output.
        :param event:
        :param cmd:
        """
        # if not cmd:
        #     cmd = self.e.get().strip()

        if not cmd:
            return True

        if self.mode == 'command':
            cmd = cmd.strip()
            if cmd[0] == 'w':
                self.editWhich()
                return ()
            elif cmd[0] in ['r', 't']:
                # simple command history for report commands
                if cmd in self.history:
                    self.history.remove(cmd)
                self.history.append(cmd)
                self.index = len(self.history) - 1
            else:
                parts = cmd.split(' ')
                if len(parts) == 2:
                    try:
                        i = int(parts[0])
                    except:
                        i = None
                    if i:
                        parts.pop(0)
                        parts.append(str(i))
                        cmd = " ".join(parts)
            try:
                res = loop.do_command(cmd)
            except:
                return _('could not process command "{0}"').format(cmd)

        elif self.mode == 'edit':
            print('edit', cmd)
            res = loop.cmd_do_edit(cmd)

        elif self.mode == 'delete':
            print('deleted', cmd)
            loop.cmd_do_delete(cmd)
            res = ''

        elif self.mode == 'finish':
            print('finish', cmd)
            loop.cmd_do_finish(cmd)
            res = ''

        elif self.mode == 'new_date':
            print('date', cmd)
            res = loop.new_date(cmd)

        if not res:
            res = _('command "{0}" returned no output').format(cmd)
            # MessageWindow(self, 'info', res)
            self.deleteItems()
            return ()

        if type(res) == dict:
            self.showTree(res, event=event)
        else:
            # not a hash => not a tree
            self.textWindow(self, title='etm', prompt=res)
            return 0

    def expand2Depth(self, event=None):
        prompt = _("""\
Enter an integer depth to expand branches
or 0 to expand all branches completely.""")
        depth = GetInteger(
            parent=self,
            title=_("depth"), prompt=prompt, opts=[0], default=0).value
        if depth is None:
            return ()
        maxdepth = max([k for k in self.depth2id])
        logger.debug('expand2Depth: {0}/{1}'.format(depth, maxdepth))
        if depth == 0:
            # expand all
            for k in self.depth2id:
                for item in self.depth2id[k]:
                    self.tree.item(item, open=True)
        else:
            depth -= 1
            for i in range(depth):
                for item in self.depth2id[i]:
                    self.tree.item(item, open=True)
            for i in range(depth, maxdepth+1):
                for item in self.depth2id[i]:
                    self.tree.item(item, open=False)
                # return('break')

    def scrollToDate(self, date):
        # only makes sense for schedule
        logger.debug("SCHEDULE: {0}; date: {1}".format(self.view == SCHEDULE, date))
        if self.view != SCHEDULE or date not in loop.prevnext:
            return ()
        active_date = loop.prevnext[date][1]
        if active_date not in self.date2id:
            return ()
        uid = self.date2id[active_date]
        self.scrollToId(uid)

    def scrollToId(self, uid):
        self.update_idletasks()
        self.tree.focus_set()
        self.tree.focus(uid)
        self.tree.selection_set(uid)
        self.tree.yview(int(uid) - 1)

    def showTree(self, tree, event=None):
        self.date2id = {}
        self.deleteItems()
        self.count = 0
        self.count2id = {}
        self.addItems(u'', tree[self.root], tree)
        loop.count2id = self.count2id
        # self.l.configure(state="normal")
        self.l.delete("0.0", END)
        # self.l.configure(state="disabled")
        if event is None:
            # view selected from menu
            self.goHome()

    def deleteItems(self):
        """
        Remove all items from the tree
        """
        for child in self.tree.get_children():
            self.tree.delete(child)

    def addItems(self, parent, elements, tree, depth=0):
        max_depth = 100
        for text in elements:
            self.count += 1
            # print('text', text)
            # text is a key in the element (tree) hash
            # these keys are (parent, item) tuples
            if text in tree:
                # this is a branch
                item = " " + text[1]  # this is the label of the parent
                children = tree[text]  # this are the children tuples of item
                oid = self.tree.insert(parent, 'end', iid=self.count, text=item,
                                       open=(depth <= max_depth))
                # oid = self.tree.insert(parent, 'end', text=item, open=True)
                # print(self.count, oid, depth, item)
                self.depth2id.setdefault(depth, set([])).add(oid)
                # recurse to get children
                self.count2id[oid] = None
                self.addItems(oid, children, tree, depth=depth + 1)
            else:
                # this is a leaf
                if len(text[1]) == 4:
                    uuid, item_type, col1, col2 = text[1]
                    dt = ''
                else:  # len 5 day view with datetime appended
                    uuid, item_type, col1, col2, dt = text[1]

                # This hack avoids encoding issues under python 2
                col1 = "{0} ".format(id2Type[item_type]) + col1

                if type(col2) == int:
                    col2 = '%s' % col2
                else:
                    col2 = s2or3(col2)

                oid = self.tree.insert(parent, 'end', iid=self.count, text=col1,
                                       open=(depth <= max_depth), value=[col2])
                # oid = self.tree.insert(parent, 'end', text=col1, open=True, value=[col2])
                # print(self.count, oid)
                # print(self.count, oid, depth, col1, depth<=max_depth)
                self.count2id[oid] = "{0}::{1}".format(uuid, dt)
                if dt:
                    # print('trying to parse', dt)
                    try:
                        d = parse(dt[:10]).date()
                        if d not in self.date2id:
                            self.date2id[d] = parent
                    except:
                        print('could not parse', dt)
                        print(text)


loop = None

log_levels = {
    1: logging.DEBUG,
    2: logging.INFO,
    3: logging.WARN,
    4: logging.ERROR,
    5: logging.CRITICAL
}

def main(level=3):  # debug, info, warn, error, critical
    global loop
    if level in log_levels:
        loglevel = log_levels[level]
    else:
        loglevel = log_levels[3]

    setup_logging(default_level=loglevel)
    # setup_logging(default_level=logging.INFO)
    etmdir = ''
    # For testing override etmdir:
    etmdir = '/Users/dag/etm-tk/etm-sample'
    init_localization()
    (user_options, options, use_locale) = data.get_options(etmdir)
    loop = data.ETMCmd(options=options)
    loop.tkversion = tkversion
    # app = App(path='/Users/dag/etm-tk')
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
