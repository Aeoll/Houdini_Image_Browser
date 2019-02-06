from __future__ import print_function
import sys
import time
import os
import json
import time
from collections import defaultdict
import functools
from pathlib import Path
# PySide2
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2 import QtUiTools
# Wand
from wand.image import Image
from wand.display import display
import time
import traceback
import random



# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = SCRIPT_DIR + "/red/ROOT_REDUCED"
THUMBDIR = SCRIPT_DIR + "/red/thumbs_reduced"
DB = SCRIPT_DIR + "/red/thumbdb_reduced.json"


def getImages(p, recurse=False):
    all_files = []
    for a in p.glob("*"):
        all_files.append(a)
    return all_files

class HImageReduced(QWidget):
    def __init__(self):
        super(HImageReduced, self).__init__()
        self.thumbdb = defaultdict(str)

        self.btn = QPushButton("Hello", self)
        self.btn.pressed.connect(self.updateThumbList)
        self.thumblist = QListWidget(self)
        self.thumblist.setIconSize(QSize(100, 100))
        self.thumblist.setViewMode(QListWidget.IconMode)
        # set main layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.btn)
        mainLayout.addWidget(self.thumblist)
        self.setLayout(mainLayout)
        self.setGeometry(QRect(0, 0, 500, 500))

    # ===========================

    def updateThumbList(self):
        start = time.time()
        self.thumblist.clear()
        dirImages = getImages(Path(ROOT))
        if dirImages:
            for p in dirImages:
                self.generateThumbnail(str(p))

        # # create the thumnbail list widget
        for idx, im in enumerate(dirImages):
            thumbpath = self.thumbdb[str(im)]
            th = QPixmap(thumbpath).scaled(150, 150, aspectMode=Qt.KeepAspectRatio)
            item = QListWidgetItem(QIcon(th), str(Path(im).name))
            item.setSizeHint(QSize(150, 150 + 25))
            self.thumblist.addItem(item)
        end = time.time()
        print(end-start)

    def generateThumbnail(self, filepath):
        random
        time.sleep(2*random.random())
        with Image(filename=filepath) as img:
            thumbdir = THUMBDIR + "/" + Path(filepath).parent.name + "_" + Path(filepath).stem + "_thumb.jpg"
            with img.convert('jpg') as i:
                i.transform(resize=str(150) + 'x' + str(150) + '>')
                i.save(filename=thumbdir)
            key = filepath
            self.thumbdb[key] = str(thumbdir)
        print(str(key))
        return str(key)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HImageReduced()
    window.show()
    sys.exit(app.exec_())



# ALSO SEE http://euanfreeman.co.uk/pyqt-qpixmap-and-threads/
# AND https://stackoverflow.com/questions/45157006/python-pyqt-pulsing-progress-bar-with-multithreading OR https://stackoverflow.com/questions/20657753/python-pyside-and-progress-bar-threading

# https://stackoverflow.com/questions/42673010/how-to-correctly-load-images-asynchronously-in-pyqt5

# https://www.twobitarcade.net/article/multithreading-pyqt-applications-with-qthreadpool/
# https://www.twobitarcade.net/article/qt-transmit-extra-data-with-signals/