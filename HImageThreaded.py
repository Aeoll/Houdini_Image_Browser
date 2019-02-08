from __future__ import print_function
import sys
import time
import os
import json
import time
from collections import defaultdict
import functools

try:
    from pathlib import *
except ImportError:
    from pathlib2 import *
# https://www.sidefx.com/forum/topic/59279/?page=1#post-265525
try:
    import hou
except:
    pass

# PySide2
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2 import QtUiTools
# Wand
from wand.image import Image
from wand.display import display
import traceback

# ========================
# TODO
# ========================
'''
Check for thumb regeneration by date modified on the file?
Thumb menub: Clean db?
context menu for qlistwidget? https://stackoverflow.com/questions/48890473/how-do-i-make-a-context-menu-for-each-item-in-a-qlistwidget Open in file browser? Delete?

Profiling: python -m cProfile .\HImage.py
'''

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBDIR = SCRIPT_DIR + "/thumbs"
DB = SCRIPT_DIR + "/thumbdb.json"
imExts = ["png", "jpg", "jpeg", "tga", "tiff", "exr", "hdr", "bmp", "tif"]
parmNames = ["file", "filename", "map", "tex0", "ar_light_color_texture", "env_map"]

'''
Multithreading Thumbnail creation and insertion
'''

class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object, int)


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

    @Slot()
    def run(self):
        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(self.path)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result, self.idx)
        finally:
            self.signals.finished.emit()


def getImages(p, recurse=False):
    all_files = []
    if recurse:
        for a in p.rglob("*"):
            if a.suffix[1:] in imExts:
                all_files.append(a)
    else:
        for a in p.glob("*"):
            if a.suffix[1:] in imExts:
                all_files.append(a)
    return all_files


'''
QMainWindow
'''

class HImageThreaded(QWidget):
    def __init__(self):
        super(HImageThreaded, self).__init__()
        scriptpath = os.path.dirname(os.path.realpath(__file__))

        # load thumbnail database
        load = self.readThumbDatabase()
        self.thumbdb = defaultdict(dict, load)

        self.thSize = [700, 700]
        self.thListSize = [150, 150]

        # load UI
        loader = QtUiTools.QUiLoader()
        self.ui = loader.load(scriptpath + '/himage.ui')

        # Menu bar
        self.menu = self.ui.findChild(QMenuBar, 'menubar')
        self.menuGoto = self.ui.findChild(QMenu, 'menuGoTo')
        self.actionThumbRecursive = self.ui.findChild(QAction, 'actionCreate_Thumbs_for_Directory')
        self.actionThumbRecursive.triggered.connect(self.thumbGenRecursive)
        self.actionClearThumb = self.ui.findChild(QAction, 'actionClear_Thumb_Database')
        self.actionClearThumb.triggered.connect(self.clearThumbDatabase)
        self.actionRecreateThumbs = self.ui.findChild(QAction, 'actionRefresh_Current_Dir')
        self.actionRecreateThumbs.triggered.connect(self.thumbGenNonRecursive)

        self.fromNodeBtn = self.ui.findChild(QPushButton, 'fromNodeBtn')
        self.fromNodeBtn.clicked.connect(self.pathFromNode)

        self.actionAddFav = self.ui.findChild(QAction, 'actionAddFavourite')
        self.actionAddFav.triggered.connect(self.addFav)
        self.actionSetStartupPath = self.ui.findChild(QAction, 'actionStartup')
        self.actionSetStartupPath.triggered.connect(self.setStartupPath)

        # Add GoTo's - add goto actions from json file for other paths? not working but no errors??
        self.gotoDirs = self.getGotoDirs()
        actions = []
        for key, val in self.gotoDirs.items():
            action = QAction(str(key), self)  # needs a parent object in order to work in hou?
            action.setData(str(val))
            actions.append(action)
            action.triggered.connect(functools.partial(self.goto, action.data()))
            self.menuGoto.addAction(action)

        # Add thumb size options
        self.menuThumbSizes = self.ui.findChild(QMenu, 'menuThumbnail_Size')
        sizes = [50, 100, 150, 200]
        for s in sizes:
            action = QAction(str(s), self)  # needs a parent object in order to work in hou?
            action.setData(s)
            action.triggered.connect(functools.partial(self.thumbSizing, action.data()))
            self.menuThumbSizes.addAction(action)

        # TREE VIEW AND FILESYSTEM MODEL
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs)
        self.tree = self.ui.findChild(QTreeView, 'dirtree')
        self.tree.setModel(self.model)
        self.tree.setIndentation(15)
        self.tree.setColumnWidth(0, 250)  # get widget width to set..
        for c in range(1, 5):
            self.tree.hideColumn(c)  # hide all columns except name..?

        # navigate to the startup/ROOT filepath
        with open(SCRIPT_DIR + "/config.json", 'r') as f:
            self.config = json.load(f)
            self.ROOT = self.config['StartupPath']
            try:
                idx = self.model.index(QDir(self.ROOT).absolutePath())
            except:
                print("statup path not found")
        f.close()

        self.model.setRootPath(str(Path(self.ROOT).drive))  # seems to be required for proper sorting
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.tree.collapseAll()
        self.expandTree(idx)  # doesnt scroll properly on initial load?
        self.tree.pressed.connect(self.treeSignal)  # prevents this firing twice on double click

        # Directory path Line edit
        self.dirLineEdit = self.ui.findChild(QLineEdit, 'dirLineEdit')
        self.dirLineEdit.setText(QDir(self.ROOT).absolutePath())
        self.dirLineEdit.textChanged.connect(self.dirLineEditUpdate)

        # info labels
        self.dir_info = self.ui.findChild(QLabel, 'dir_info')
        self.image_info = self.ui.findChild(QLabel, 'image_info')

        # Large image preview
        self.thumblargepreview = self.ui.findChild(QLabel, 'thumblargepreview')
        self.thumblargepreview.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        # Thumbnail list view
        self.thumblist = self.ui.findChild(QListWidget, 'thumblist')
        self.thumblist.setIconSize(QSize(self.thSize[0], self.thSize[1]))
        self.thumblist.setSpacing(2)
        self.thumblist.doubleClicked.connect(self.setTexture)
        self.thumblist.clicked.connect(self.setLargePreview)
        # self.thumblist.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        self.thumblistdict = {}  # Dict mapping full path to image basename

        # remove margins and status bar
        self.centralWidget = self.ui.centralWidget()
        self.centralWidget.layout().setContentsMargins(0, 0, 0, 0)
        self.ui.statusBar().hide()

        # set main layout
        mainLayout = QVBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)  # REMOVE SHITTY WHITE MARGIN
        mainLayout.addWidget(self.ui)
        self.setLayout(mainLayout)

        # Multithreading
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(self.threadpool.maxThreadCount() - 2)  # don't use all threads?
        print("Multithreading thumbnail generation with maximum %d threads" % self.threadpool.maxThreadCount())

        def reset(self):
            self.treeSignal(self.tree.currentIndex())


    '''
    Signals for menu bar actions
    '''

    def setStartupPath(self):
        path = self.dirLineEdit.text()
        self.config['StartupPath'] = path
        with open(SCRIPT_DIR + "/config.json", 'w') as f:
            json.dump(self.config, f, indent=4, sort_keys=True)
        f.close()

    def addFav(self):
        path = self.dirLineEdit.text()
        favname, ok = QInputDialog.getText(self, "Add Favourite", "Name:", QLineEdit.Normal, "")
        if ok and favname:
            self.gotoDict[str(favname)] = str(path)
            action = QAction(str(favname), self)  # needs a parent object in order to work in hou?
            action.setData(str(path))
            action.triggered.connect(functools.partial(self.goto, action.data()))
            self.menuGoto.addAction(action)
            self.writeGotoDirs()
        pass

    def getGotoDirs(self):
        self.gotoDict = None
        with open(SCRIPT_DIR + "/goto.json", 'r') as f:
            self.gotoDict = json.load(f)
        f.close()
        return self.gotoDict

    def writeGotoDirs(self):
        with open(SCRIPT_DIR + "/goto.json", 'w') as f:
            json.dump(self.gotoDict, f, indent=4, sort_keys=True)
        f.close()

    def goto(self, path):
        if path.startswith('$'):
            try:
                path = hou.expandString(path)
            except:
                print("expand failed")
        try:
            idx = self.model.index(QDir(path).absolutePath())
            self.expandTree(idx)
            self.dirLineEdit.setText(path)
        except:
            pass

    def thumbSizing(self, size):
        self.thListSize = [size, size]
        self.reset()

    '''
    Signals for tree view and url bar
    '''

    def treeSignal(self, index):
        path = self.model.fileInfo(index).absoluteFilePath()
        self.dirLineEdit.setText(path)
        if path is not THUMBDIR:
            self.updateThumbList(path)

    def expandTree(self, idx):
        self.tree.collapseAll()
        self.tree.scrollTo(idx, hint=QAbstractItemView.PositionAtTop)
        self.tree.expand(idx)
        self.tree.setCurrentIndex(idx)

    def dirLineEditUpdate(self, path):
        self.tree.setCurrentIndex(self.model.index(QDir(path).absolutePath()))
        self.updateThumbList(QDir(path).absolutePath())  # also force the listwidget to update

    '''
    Signals for thumb list and large preview
    '''

    def setSingleThumb(self, path, idx):
        thumbpath = self.thumbdb[str(path)]['thumb']
        try:
            qim = QImage(thumbpath)
            th = QPixmap.fromImage(qim).scaled(self.thListSize[0], self.thListSize[1], aspectMode=Qt.KeepAspectRatio)
            # th = QPixmap(thumbpath).scaled(self.thListSize[0], self.thListSize[1], aspectMode=Qt.KeepAspectRatio) # do we need to use QImage here instead of QPixmap???
            item = self.updateDict[idx]
            item.setIcon(QIcon(th))
            self.writeThumbDatabase()  # write the json to disk immediately?
        except:
            print("error setting thumbnail or writing to database")

    def updateThumbList(self, path, force=False):
        self.thumblist.clear()
        self.thumblistdict.clear()
        self.updateDict = defaultdict(QListWidget)  # update dict for threadpool

        dirImages = getImages(Path(path))
        self.dir_info.setText("Images in Folder: " + str(len(dirImages)))
        self.thumblargepreview.clear()  # always clear this?

        # get paths to generate thumbs for
        imagelist = []
        for p in dirImages:
            if not p.is_dir() and p.suffix[1:] in imExts:
                if not str(p) in self.thumbdb or force:
                    imagelist.append(p)

        self.threadpool.clear()

        for idx, im in enumerate(dirImages):
            # For images which need thumbs to be generated
            if im in imagelist:
                qim = QImage(150, 150, QImage.Format_RGB16)
                qim.fill(QColor(0, 0, 0))
                th = QPixmap.fromImage(qim).scaled(self.thListSize[0], self.thListSize[1], aspectMode=Qt.KeepAspectRatio)
                imname = str(Path(im).name)
                item = QListWidgetItem(QIcon(th), str(imname))
                item.setToolTip(str(imname))
                item.setSizeHint(QSize(self.thListSize[0], self.thListSize[1] + 25))
                self.thumblist.addItem(item)
                self.thumblistdict[imname] = str(im)
                self.updateDict[idx] = item  # add the queued listitem to a widget so it can be updated properly

                worker = Worker(self.generateThumbnail, idx, str(im))
                worker.signals.result.connect(self.setSingleThumb)
                self.threadpool.start(worker)
            else:
                # For images with existing thumbnails just create the item
                thumbpath = self.thumbdb[str(im)]['thumb']
                th = QPixmap(thumbpath).scaled(self.thListSize[0], self.thListSize[1], aspectMode=Qt.KeepAspectRatio)
                imname = str(Path(im).name)
                item = QListWidgetItem(QIcon(th), str(imname))
                item.setToolTip(str(imname))
                item.setSizeHint(QSize(self.thListSize[0], self.thListSize[1] + 25))
                self.thumblist.addItem(item)
                self.thumblistdict[imname] = str(im)

    # return size to fill frame with aspect on
    def fitFrame(self, pixmap, x, y, w, h):
        fasp = w / (h * 1.0)
        imasp = x / (y * 1.0)
        sz = 0
        if imasp >= fasp:
            pixmap = pixmap.scaled(min(w, x), 10000, aspectMode=Qt.KeepAspectRatio, transformMode=Qt.SmoothTransformation)
        else:
            pixmap = pixmap.scaled(10000, min(h, y), aspectMode=Qt.KeepAspectRatio, transformMode=Qt.SmoothTransformation)
        return pixmap

    def setLargePreview(self, item):
        texname = item.data()
        texpath = self.thumblistdict[texname]
        try:
            thumbname = self.thumbdb[texpath]['thumb']
            jpg = QPixmap(thumbname)
            w = self.thumblargepreview.geometry().width()
            h = self.thumblargepreview.geometry().height()
            size = jpg.size()
            jpg = self.fitFrame(jpg, size.width(), size.height(), w, h)
            self.thumblargepreview.setPixmap(jpg)
            self.image_info.setText("Image Size: " + self.thumbdb[texpath]['res'].replace(" ", " x "))  # set image size info
        except:
            print("thumbnail not yet generated")

    '''
    Thumbnail generation and db handling
    '''

    def generateThumbnail(self, filepath):
        with Image(filename=filepath) as img:
            thumbdir = THUMBDIR + "/" + Path(filepath).parent.name + "_" + Path(filepath).stem + "_thumb.jpg"
            imsize = img.size
            with img.convert('jpg') as i:
                i.compression_quality = 55
                i.transform(resize=str(self.thSize[0]) + 'x' + str(self.thSize[1]) + '>')  # faster than resize
                i.save(filename=thumbdir)
            key = filepath
            # use nested defaultdict to store osme metadata
            self.thumbdb[key]['thumb'] = str(thumbdir)
            self.thumbdb[key]['thumbres'] = str(self.thSize[0]) + " " + str(self.thSize[1])  #also add thumb size?
            self.thumbdb[key]['res'] = str(imsize[0]) + " " + str(imsize[1])
            return str(key)

    def thumbGenNonRecursive(self):
        path = Path(self.dirLineEdit.text())
        self.updateThumbList(path, True)

    def thumbGenRecursive(self, force=False):
        path = Path(self.dirLineEdit.text())
        imagelist = getImages(path, recurse=True)
        imagelist = [p for p in imagelist if not str(p) in self.thumbdb]  # don't force re-create

        # progress bar
        self.pbar = QProgressDialog("Generating Thumbnails", "Abort", 0, len(imagelist))
        self.pbar.setWindowTitle("Thumbnail Generation Progress")
        self.pbar.setMinimumSize(QSize(600, 0))
        # self.pbar.setMinimum(0)
        # self.pbar.setMaximum(0)
        self.pbar.setValue(0)
        self.pbar.setWindowModality(Qt.WindowModal)
        try:
            self.pbar.setStyleSheet(hou.qt.styleSheet())
        except:
            print("hou not imported")
        self.pbar.forceShow()

        for idx, im in enumerate(imagelist):
            imname = str(Path(im).name)
            worker = Worker(self.generateThumbnail, idx, str(im))
            worker.signals.result.connect(self.updateProgressBar)
            self.threadpool.start(worker)

        # will this do anything called here..?
        if self.pbar.wasCanceled():
            self.threadpool.cancel()
        # self.threadpool.waitForDone()
        # self.writeThumbDatabase() # write the json to disk

    def updateProgressBar(self, path, idx):
        try:
            self.pbar.setValue(self.pbar.value() + 1)
            self.pbar.setLabelText(str(path))
            self.writeThumbDatabase()  # write the json to disk
        except:
            print("progress bar not found or thumb database write failed")

    '''
    Thumbnail Database methods - move these out...?
    '''

    def readThumbDatabase(self):
        db = None
        with open(DB, 'r') as f:
            db = json.load(f)
        f.close()
        return db

    def writeThumbDatabase(self):
        with open(DB, 'w') as f:
            json.dump(self.thumbdb, f, indent=4, sort_keys=True)
        f.close()

    def cleanThumbDatabase(self):
        pass

    def clearThumbDatabase(self):
        for key, value in self.thumbdb.iteritems():  #this wont work in python3 which uses items(S)
            try:
                os.remove(value)
            except:
                print("item not found - already deleted?")
        self.thumbdb.clear()
        with open(DB, 'w') as f:
            json.dump(self.thumbdb, f)
        f.close()

        for f in Path(THUMBDIR).glob("*"):
            os.remove(str(f))
        self.reset()

    '''
    Interaction with Houdini nodes
    '''

    def pathFromNode(self):
        if hou.selectedNodes():
            node = hou.selectedNodes()[0]
            parms = node.parms()
            for p in parms:
                if p.name() in parmNames:
                    dir = Path(p.evalAsString()).parent
                    self.dirLineEditUpdate(str(dir))
                    self.setLargePreview(p.evalAsString())

    def setTexture(self, item):
        texname = item.data()
        texpath = self.thumblistdict[texname]
        QApplication.clipboard().setText(str(texpath).replace("\\", "/"))  # add to clipboard
        if hou.selectedNodes():
            node = hou.selectedNodes()[0]
            parms = node.parms()
            for p in parms:
                if p.name() in parmNames:
                    # if HIP in pathname, replace
                    hip = hou.expandString("$HIP")
                    texpath = texpath.replace(hip, "$HIP")
                    p.set(texpath)
                    break


    '''
    Cleanup on Close
    '''
    def closeEvent(self, event):
        # print(self.threadpool.activeThreadCount())
        self.threadpool.waitForDone()
        self.threadpool.clear()
        print("closing and clearing threadpool")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HImageThreaded()
    window.show()
    sys.exit(app.exec_())