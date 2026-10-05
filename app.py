# -*- coding: utf-8 -*-
"""
NGU Lingo Companion - 启动入口 (支持 Windows 单实例运行互斥锁)
"""
import sys
import os
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow

def acquire_single_instance_lock():
    """使用文件排它锁确保同一时刻全局仅运行一个伴侣实例，彻底杜绝多进程热键冲突"""
    try:
        import msvcrt
        lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".app.lock")
        f = open(lock_path, "w")
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        return f
    except Exception:
        # 如果已经有运行中的伴侣实例，直接安静退出，绝不多开重复进程抢占热键
        sys.exit(0)

def main():
    lock_file = acquire_single_instance_lock()

    app = QApplication(sys.argv)
    app.setApplicationName("NGU Lingo Companion")

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    try:
        if lock_file:
            lock_file.close()
    except Exception:
        pass
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
