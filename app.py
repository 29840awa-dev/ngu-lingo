# -*- coding: utf-8 -*-
"""
NGU Lingo Companion - 启动入口与全局快捷键监听 (Alt+Q)
"""
import sys
import threading
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal
from pynput import keyboard

from main_window import MainWindow

class HotkeyBridge(QObject):
    hotkey_triggered = pyqtSignal()

def start_hotkey_listener(bridge):
    """全局热键监听线程：按下 Alt+Q 触发截屏取词"""
    def on_activate():
        bridge.hotkey_triggered.emit()

    hotkeys = keyboard.GlobalHotKeys({
        '<alt>+q': on_activate
    })
    hotkeys.start()
    hotkeys.join()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NGU Lingo Companion")

    window = MainWindow()
    window.show()

    # 全局快捷键桥接
    bridge = HotkeyBridge()
    bridge.hotkey_triggered.connect(window.start_snip_capture)

    listener_thread = threading.Thread(target=start_hotkey_listener, args=(bridge,), daemon=True)
    listener_thread.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
