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

class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object, int)
    progress = Signal(int)

class Worker(QRunnable):
    def __init__(self, fn, idx, path, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.idx = idx
        self.path = path
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    @Slot()
    def run(self):
        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(self.path, self.idx)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # Return the result of the processing
            self.signals.result.emit(result, self.idx)
        finally:
            self.signals.finished.emit()


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

        # THREADING
        self.counter = 0
        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

    # CALLBACKS

    def thread_complete(self):
        end = time.time()
        print(end-self.start)
        print("THREAD COMPLETE!")

    # ===========================

    def setSingleThumb(self, path, idx):
        # print(self.thumblist.items())
        thumbpath = self.thumbdb[str(path)]
        th = QPixmap(thumbpath).scaled(150, 150, aspectMode=Qt.KeepAspectRatio)
        item = self.updateDict[idx]
        # item = self.thumblist.findItems(str(path), Qt.MatchExactly)[0]
        # item = QListWidgetItem(QIcon(th), str(Path(path).name))
        item.setIcon(QIcon(th))
        # item.setSizeHint(QSize(150, 150 + 25))
        self.thumblist.update()
        # self.thumblist.addItem(item)
        pass

    def updateThumbList(self):
        self.start = time.time()
        self.thumblist.clear()
        dirImages = getImages(Path(ROOT))
        self.updateDict = defaultdict(QListWidget)
        # # create the thumnbail list widget
        for idx, im in enumerate(dirImages):
            # thumbpath = self.thumbdb[str(im)]
            # qim = QImage(thumbpath)
            qim = QImage(150, 150, QImage.Format_RGB16)
            qim.fill(QColor(0,0,0))
            th = QPixmap.fromImage(qim).scaled(150, 150, aspectMode=Qt.KeepAspectRatio)
            # # th = QPixmap(thumbpath).scaled(150, 150, aspectMode=Qt.KeepAspectRatio)
            item = QListWidgetItem(QIcon(th), str(Path(im).name))
            self.updateDict[idx] = item
            item.setSizeHint(QSize(150, 150 + 25))
            self.thumblist.addItem(item)
            # pass

        # if dirImages:
            # for p in dirImages:
            # self.generateThumbnail(str(p))
            # Pass the function to execute
            # Any other args, kwargs are passed to the run function
            worker = Worker(self.generateThumbnail, idx, str(im))
            worker.signals.result.connect(self.setSingleThumb)
            worker.signals.finished.connect(self.thread_complete)
            self.threadpool.start(worker)

    def generateThumbnail(self, filepath, idx):
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