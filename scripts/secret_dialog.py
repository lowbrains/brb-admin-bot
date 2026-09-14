"""Local masked entry; no secret files or console output."""
import re
import tkinter as tk
from tkinter import ttk

def ask_keys():
    window = tk.Tk()
    window.title('Администратор БРБ — ключи подключения')
    window.geometry('650x330')
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=20)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Вставьте два ключа. Символы отображаются точками.').pack(anchor='w')
    fields = []
    status = tk.StringVar(value='Ключи не сохраняются в файлах.')
    result = {}
    for label in ('Токен Telegram из BotFather', 'API-ключ Яндекс AI Studio'):
        ttk.Label(frame, text=label).pack(anchor='w', pady=(16, 4))
        row = ttk.Frame(frame)
        row.pack(fill='x')
        entry = ttk.Entry(row, show='*', width=65)
        entry.pack(side='left', fill='x', expand=True)
        fields.append(entry)
        def paste(target=entry):
            try:
                value = window.clipboard_get().strip()
                target.delete(0, 'end')
                target.insert(0, value)
                status.set('Вставлено символов: ' + str(len(value)))
            except tk.TclError:
                status.set('В буфере нет текста. Сначала скопируйте ключ.')
            target.focus_set()
        ttk.Button(row, text='Вставить', command=paste).pack(side='right', padx=(8, 0))
        def keyboard_paste(event, action=paste):
            action()
            return 'break'
        entry.bind('<<Paste>>', keyboard_paste)
    ttk.Label(frame, textvariable=status).pack(anchor='w', pady=12)
    def submit(event=None):
        token, key = (field.get().strip() for field in fields)
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token):
            status.set('Проверьте токен Telegram: нужна вся строка из BotFather.')
            return
        if not key or any(ch.isspace() for ch in key):
            status.set('Вставьте API-ключ Яндекса без пробелов.')
            return
        result.update(TELEGRAM_BOT_TOKEN=token, MODEL_API_KEY=key)
        window.destroy()
    buttons = ttk.Frame(frame)
    buttons.pack(fill='x')
    ttk.Button(buttons, text='Подключить', command=submit).pack(side='left')
    ttk.Button(buttons, text='Отмена', command=window.destroy).pack(side='left', padx=8)
    window.bind('<Return>', submit)
    window.after(100, lambda: (window.lift(), fields[0].focus_force()))
    window.mainloop()
    return result or None
