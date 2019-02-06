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

# ========================
# TODO
# ========================
'''
Check for thumb regeneration by date modified on file?

Profiling: python -m cProfile .\HImage.py

context menu for qlistwidget? https://stackoverflow.com/questions/48890473/how-do-i-make-a-context-menu-for-each-item-in-a-qlistwidget Open in file browser? Delete?
'''

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# default location to open
ROOT = SCRIPT_DIR + "/ROOT_B"
THUMBDIR = SCRIPT_DIR + "/thumbs"
DB = SCRIPT_DIR + "/thumbdb.json"
imExts = ["png", "jpg", "jpeg", "tga", "tiff", "exr", "hdr", "bmp", "tif"]
parmNames = ["file", "filename", "map", "tex0", "ar_light_color_texture", "env_map"]


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


def getGotoDirs():
    goto = None
    with open(SCRIPT_DIR + "/goto.json", 'r') as f:
        goto = json.load(f)
    f.close()
    return goto


'''
QMainWindow
'''


class HImage(QWidget):
    def __init__(self):
        super(HImage, self).__init__()
        scriptpath = os.path.dirname(os.path.realpath(__file__))

        # load thumbnail database
        load = self.readThumbDatabase()
        self.thumbdb = defaultdict(dict, load)

        self.thSize = [600, 600]
        self.thListSize = [100, 100]

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

        # Add GoTo's - add goto actions from json file for other paths? not working but no errors??
        self.gotoDirs = getGotoDirs()
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

        # TREE
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.currentPath())
        self.model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs)
        self.tree = self.ui.findChild(QTreeView, 'dirtree')
        self.tree.setModel(self.model)
        self.tree.setIndentation(15)
        self.tree.setColumnWidth(0, 250)  # get widget width to set..
        for c in range(1, 5):
            self.tree.hideColumn(c)  # hide all columns except name..

        # navigate to root filepath
        idx = self.model.index(QDir(ROOT).absolutePath())
        self.tree.collapseAll()
        self.expandTree(idx)  # doesnt scroll properly on initial load?
        self.tree.pressed.connect(self.treeSignal)  # prevents this firing twice on double click

        self.dirLineEdit = self.ui.findChild(QLineEdit, 'dirLineEdit')
        self.dirLineEdit.setText(QDir(ROOT).absolutePath())
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
        self.thumblist.setSpacing(6)
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

    '''
    Signals for menu bar actions
    '''

    def expandTree(self, idx):
        self.tree.collapseAll()
        self.tree.scrollTo(idx, hint=QAbstractItemView.PositionAtTop)
        self.tree.expand(idx)
        self.tree.setCurrentIndex(idx)

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

    def dirLineEditUpdate(self, path):
        self.tree.setCurrentIndex(self.model.index(QDir(path).absolutePath()))
        self.updateThumbList(QDir(path).absolutePath())  # also force the listwidget to update

    '''
    Signals for thumb list and preview
    '''

    def updateThumbList(self, path):
        self.thumblist.clear()
        self.thumblistdict.clear()
        self.thumbGenNonRecursive(path)  # generate thumbs if needed

        dirImages = getImages(Path(path))
        self.dir_info.setText("Images in Folder: " + str(len(dirImages)))
        # if none, clear the label
        if not dirImages:
            self.thumblargepreview.clear()

        # create the thumnbail list widget
        for idx, im in enumerate(dirImages):
            thumbpath = self.thumbdb[str(im)]['thumb']
            th = QPixmap(thumbpath).scaled(self.thListSize[0], self.thListSize[1], aspectMode=Qt.KeepAspectRatio)

            # get image name for label and create dict mapping name back to full path
            imname = str(Path(im).name)
            self.thumblistdict[imname] = str(im)

            item = QListWidgetItem(QIcon(th), str(imname))
            item.setToolTip(str(imname))  # show full name on hover
            item.setSizeHint(QSize(self.thListSize[0], self.thListSize[1] + 25))  # prevent overrun of text
            self.thumblist.addItem(item)
            # Set large preview image to first item thumb
            if idx == 0:
                w = self.thumblargepreview.frameGeometry().width()
                h = self.thumblargepreview.frameGeometry().height()
                s = min(w, h)
                mainPrev = QPixmap(thumbpath).scaled(s, s, aspectMode=Qt.KeepAspectRatio)
                self.thumblargepreview.setPixmap(mainPrev)
                self.image_info.setText("Image Size: " + self.thumbdb[str(im)]['res'].replace(" ", " x "))  # set image size info

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
        thumbname = self.thumbdb[texpath]['thumb']
        jpg = QPixmap(thumbname)

        w = self.thumblargepreview.geometry().width()
        h = self.thumblargepreview.geometry().height()
        size = jpg.size()
        jpg = self.fitFrame(jpg, size.width(), size.height(), w, h)
        self.thumblargepreview.setPixmap(jpg)
        self.image_info.setText("Image Size: " + self.thumbdb[texpath]['res'].replace(" ", " x "))  # set image size info

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
        QApplication.clipboard().setText(str(texpath))  # add to clipboard
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
    Thumbnail generation and db handling
    '''

    def generateThumbnail(self, filepath):
        with Image(filename=filepath) as img:
            thumbdir = THUMBDIR + "/" + Path(filepath).parent.name + "_" + Path(filepath).stem + "_thumb.jpg"
            imsize = img.size
            mx = max(imsize)

            with img.convert('jpg') as i:
                i.compression_quality = 60
                # i.sample(self.thSize[0], self.thSize[1])  # faster than resize but horrible quality
                i.transform(resize=str(self.thSize[0]) + 'x' + str(self.thSize[1]) + '>')  # faster than resize
                i.save(filename=thumbdir)

            key = filepath
            # use nested defaultdict to store osme metadata
            self.thumbdb[key]['thumb'] = str(thumbdir)
            self.thumbdb[key]['thumbres'] = str(self.thSize[0]) + " " + str(self.thSize[1])  #also add thumb size?
            self.thumbdb[key]['res'] = str(imsize[0]) + " " + str(imsize[1])

    def thumbFolderGen(self, imagelist, force=False):
        if not force:
            imagelist = [p for p in imagelist if not str(p) in self.thumbdb]

        if imagelist:
            # progress bar
            pbar = QProgressDialog("Generating Thumbnails", "Abort", 0, len(imagelist))
            pbar.setWindowTitle("Thumbnail Generation Progress")
            pbar.setMinimumSize(QSize(600, 0))
            pbar.setWindowModality(Qt.WindowModal)
            try:
                pbar.setStyleSheet(hou.qt.styleSheet())
                # pbar.setWindowFlags(Qt.FramelessWindowHint)
            except:
                print("hou not imported")

            pbar.setValue(0)
            pbar.forceShow()

            start = time.time()
            for p in imagelist:
                if pbar.wasCanceled():
                    break
                if not p.is_dir() and p.suffix[1:] in imExts:
                    # if not p in self.thumbdb:
                    if not any(p in d.values() for d in self.thumbdb.values()):
                        self.generateThumbnail(str(p))
                    else:
                        print("thumb exists")
                # progress bar
                pbar.setValue(pbar.value() + 1)
                pbar.setLabelText(str(p))
            end = time.time()
            print(end - start)
            self.writeThumbDatabase()

    def thumbGenNonRecursive(self, folder, force=False):
        images = getImages(Path(folder))
        self.thumbFolderGen(images)

    def thumbGenRecursive(self, force=False):
        path = Path(self.dirLineEdit.text())
        images = getImages(path, recurse=True)
        self.thumbFolderGen(images)

    def reset(self):
        self.treeSignal(self.tree.currentIndex())

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
        self.reset()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HImage()
    window.show()
    sys.exit(app.exec_())