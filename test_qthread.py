# !/usr/bin/env python3

import os
from PyQt5.QtCore import pyqtSignal, QObject, QThread
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

class ImageLoader(QObject):
    loaded = pyqtSignal(str, QImage)

    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def on_load_signal(self):
        img = QImage(self.filename)
        self.loaded.emit(self.filename, img)

class LoaderManager(QObject):
    request_img_load = pyqtSignal()

    def __init__(self):
        super().__init__()
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        ROOT = SCRIPT_DIR + "/red/ROOT_REDUCED"
        self.loaders = list(map(ImageLoader, filter(lambda f: f.endswith('.png'), os.listdir(ROOT))))
        self.bg_thread = QThread()

        for loader in self.loaders:
            self.request_img_load.connect(loader.on_load_signal)
            loader.loaded.connect(self.handle_img_loaded)
            loader.moveToThread(self.bg_thread)

        self.bg_thread.start()

    def __del__(self):
        self.bg_thread.quit()

    def load_all(self):
        self.request_img_load.emit()

    def handle_img_loaded(self, name, img):
        print('File {} of size {} loaded'.format(name, img.byteCount()))

if __name__ == '__main__':
    app = QApplication([])
    manager = LoaderManager()
    manager.load_all()